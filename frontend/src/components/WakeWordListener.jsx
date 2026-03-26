import { useEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import authService from '../services/authService'
import { blobToWavBase64 } from '../utils/audioUtils'

/**
 * WakeWordListener - background, always-on voice trigger.
 * Renders nothing. Listens for "hey <name>" (configurable from settings).
 * On match fires visionguard:wake (handled by JarvisAssistant globally).
 * Pauses while JarvisAssistant is speaking (visionguard:assistant-speaking).
 */
function getSR() {
  return window.SpeechRecognition || window.webkitSpeechRecognition || null
}

export default function WakeWordListener() {
  const navigate = useNavigate()
  const location = useLocation()

  const pathnameRef    = useRef(location.pathname)
  useEffect(() => { pathnameRef.current = location.pathname }, [location.pathname])

  const settingsRef    = useRef({ enabled: false, name: 'Jarvis', voice: 'male', voice_lock_enabled: false, voice_enrolled: false })
  const recognitionRef = useRef(null)
  const shouldRunRef   = useRef(false)
  const pausedUntilRef = useRef(0)
  const lastWakeRef    = useRef(0)
  const startingRef    = useRef(false)
  const jarvisOpenRef  = useRef(false)  // true while JarvisAssistant panel is open

  const loadSettings = async () => {
    try {
      const axios = authService.getAuthAxios()
      const res   = await axios.get('/user/assistant-settings')
      if (res.data?.settings) {
        settingsRef.current = {
          enabled:            !!res.data.settings.enabled,
          name:               res.data.settings.name  || 'Jarvis',
          voice:              res.data.settings.voice || 'male',
          voice_lock_enabled: !!res.data.settings.voice_lock_enabled,
          voice_enrolled:     !!res.data.settings.voice_enrolled,
        }
        if (settingsRef.current.enabled) {
          setTimeout(() => startRecognition(), 800)
        }
      }
    } catch { /* ignore */ }
  }

  // Verify owner voice. Called immediately inside onresult (mic is still warm from SR).
  // We open our MediaRecorder BEFORE stopping SR so Chrome's audio pipeline is already
  // active — this captures the user's trailing voice instead of silence.
  const verifyAndWake = async (inlineCommand, recognitionToStop) => {
    let stream = null
    let mr     = null
    try {
      // Open our own stream NOW while SR's internal stream is still warm
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      mr = new MediaRecorder(stream)
      const chunks = []
      mr.ondataavailable = e => { if (e.data.size > 0) chunks.push(e.data) }
      mr.start()

      // Now stop SR — our recorder keeps capturing the voice tail
      try { recognitionToStop?.stop() } catch {}

      // Record for 2 seconds (captures wake-phrase tail + any continuation)
      await new Promise(r => setTimeout(r, 2000))
      mr.stop()
      stream.getTracks().forEach(t => t.stop())
      await new Promise(r => { mr.onstop = r })

      const blob = new Blob(chunks, { type: mr.mimeType || 'audio/webm' })
      const b64  = await blobToWavBase64(blob)

      const axiosInst = authService.getAuthAxios()
      const resp = await axiosInst.post('/assistant/verify-voice', { audio_base64: b64 })

      if (!resp.data.enrolled || resp.data.authorized) {
        window.dispatchEvent(new CustomEvent('visionguard:wake', { detail: { command: inlineCommand } }))
      } else {
        window.dispatchEvent(new CustomEvent('visionguard:auth-failed'))
      }
    } catch {
      // On any error fail open — Jarvis still works
      try { recognitionToStop?.stop() } catch {}
      try { stream?.getTracks().forEach(t => t.stop()) } catch {}
      window.dispatchEvent(new CustomEvent('visionguard:wake', { detail: { command: inlineCommand } }))
    }
  }

  const stopRecognition = () => {
    try {
      if (recognitionRef.current) {
        recognitionRef.current.onresult = null
        recognitionRef.current.onerror  = null
        recognitionRef.current.onend    = null
        recognitionRef.current.stop()
      }
    } catch {}
    recognitionRef.current = null
    shouldRunRef.current   = false
  }

  const startRecognition = () => {
    const SR = getSR()
    if (!SR) return
    const user = authService.getCurrentUser()
    if (!user) return
    if (!settingsRef.current.enabled) return
    if (recognitionRef.current || startingRef.current) return
    if (Date.now() < pausedUntilRef.current) return

    shouldRunRef.current = true

    const recognition = new SR()
    recognition.continuous     = true
    recognition.interimResults = false
    recognition.lang           = 'en-US'

    recognition.onresult = (event) => {
      try {
        const idx        = event.results.length - 1
        const transcript = (event.results[idx]?.[0]?.transcript || '').trim().toLowerCase()

        const assistantName = (settingsRef.current.name || 'Jarvis').toLowerCase()
        const wakePhrases   = [
          'hey ' + assistantName,
          'ok ' + assistantName,
          assistantName,
        ]

        const matchedPhrase = wakePhrases.find(p => transcript.includes(p))
        const isWake = !!matchedPhrase
        if (!isWake) return

        if (Date.now() - lastWakeRef.current < 4000) return
        lastWakeRef.current    = Date.now()
        pausedUntilRef.current = Date.now() + 3000

        // Extract any inline command that followed the wake phrase
        let inlineCommand = ''
        if (matchedPhrase) {
          const afterWake = transcript.slice(transcript.indexOf(matchedPhrase) + matchedPhrase.length).trim()
          if (afterWake.length > 2) inlineCommand = afterWake
        }

        // Voice Lock: open mic immediately (mic is warm from SR) to capture voice tail,
        // then stop SR and record 2s before verifying speaker identity.
        if (settingsRef.current.voice_lock_enabled && settingsRef.current.voice_enrolled) {
          verifyAndWake(inlineCommand, recognition)  // recognition stopped inside verifyAndWake
        } else {
          try { recognition.stop() } catch {}
          try { window.dispatchEvent(new CustomEvent('visionguard:wake', { detail: { command: inlineCommand } })) } catch {}
        }
      } catch {}
    }

    recognition.onerror = (e) => {
      const backoff = (e.error === 'not-allowed' || e.error === 'audio-capture') ? 12000 : 5000
      pausedUntilRef.current = Date.now() + backoff
      try { recognition.stop() } catch {}
    }

    recognition.onend = () => {
      recognitionRef.current = null
      if (!shouldRunRef.current)        return
      if (!settingsRef.current.enabled) return
      const msLeft = pausedUntilRef.current - Date.now()
      if (msLeft > 0) {
        setTimeout(() => { if (settingsRef.current.enabled) startRecognition() }, Math.max(300, msLeft))
        return
      }
      setTimeout(() => { if (settingsRef.current.enabled) startRecognition() }, 300)
    }

    recognitionRef.current = recognition
    try { startingRef.current = true; recognition.start() } catch {} finally { startingRef.current = false }
  }

  useEffect(() => {
    loadSettings()

    const onGesture = async () => {
      if (!settingsRef.current.enabled) return
      if (recognitionRef.current)        return
      if (Date.now() < pausedUntilRef.current) return
      try {
        const stream = await navigator.mediaDevices?.getUserMedia?.({ audio: true })
        stream?.getTracks?.().forEach(t => t.stop())
      } catch {}
      startRecognition()
    }

    const onSettings = (e) => {
      if (!e?.detail) return
      const next = {
        enabled:            !!e.detail.enabled,
        name:               e.detail.name  || settingsRef.current.name  || 'Jarvis',
        voice:              e.detail.voice || settingsRef.current.voice || 'male',
        voice_lock_enabled: !!e.detail.voice_lock_enabled,
        voice_enrolled:     e.detail.voice_enrolled !== undefined ? !!e.detail.voice_enrolled : settingsRef.current.voice_enrolled,
      }
      settingsRef.current = next
      if (next.enabled) startRecognition()
      else stopRecognition()
    }

    const onSpeaking = (e) => {
      if (e?.detail?.speaking) {
        // Jarvis started speaking — pause wake-word listener for 14s
        pausedUntilRef.current = Date.now() + 14000
        try { recognitionRef.current?.stop() } catch {}
      } else {
        if (jarvisOpenRef.current) {
          // Panel still open (listen cycle) — keep SR paused so we don't compete with
          // JarvisAssistant's own SpeechRecognition which opens 350ms from now.
          pausedUntilRef.current = Date.now() + 30000
        } else {
          // Panel closed — restart wake-word detection normally
          pausedUntilRef.current = Date.now() + 800
          setTimeout(() => { if (settingsRef.current.enabled) startRecognition() }, 900)
        }
      }
    }

    const onJarvisOpened = () => {
      // Jarvis panel just opened — block wake-word SR until panel closes
      jarvisOpenRef.current  = true
      pausedUntilRef.current = Date.now() + 999999
      try { recognitionRef.current?.stop() } catch {}
    }

    const onJarvisClosed = () => {
      // Panel closed manually — unblock and restart
      jarvisOpenRef.current  = false
      pausedUntilRef.current = Date.now() - 1
      setTimeout(() => { if (settingsRef.current.enabled) startRecognition() }, 400)
    }

    window.addEventListener('pointerdown',                         onGesture)
    window.addEventListener('visionguard:assistant-settings',      onSettings)
    window.addEventListener('visionguard:assistant-speaking',      onSpeaking)
    window.addEventListener('visionguard:jarvis-opened',           onJarvisOpened)
    window.addEventListener('visionguard:jarvis-closed',           onJarvisClosed)

    return () => {
      window.removeEventListener('pointerdown',                    onGesture)
      window.removeEventListener('visionguard:assistant-settings', onSettings)
      window.removeEventListener('visionguard:assistant-speaking', onSpeaking)
      window.removeEventListener('visionguard:jarvis-opened',      onJarvisOpened)
      window.removeEventListener('visionguard:jarvis-closed',      onJarvisClosed)
      stopRecognition()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return null
}
