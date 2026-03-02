import { useEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import authService from '../services/authService'

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

  const settingsRef    = useRef({ enabled: false, name: 'Jarvis', voice: 'male' })
  const recognitionRef = useRef(null)
  const shouldRunRef   = useRef(false)
  const pausedUntilRef = useRef(0)
  const lastWakeRef    = useRef(0)
  const startingRef    = useRef(false)

  const loadSettings = async () => {
    try {
      const axios = authService.getAuthAxios()
      const res   = await axios.get('/user/assistant-settings')
      if (res.data?.settings) {
        settingsRef.current = {
          enabled: !!res.data.settings.enabled,
          name:    res.data.settings.name  || 'Jarvis',
          voice:   res.data.settings.voice || 'male',
        }
        // Auto-start listening if assistant is enabled
        if (settingsRef.current.enabled) {
          setTimeout(() => startRecognition(), 800)
        }
      }
    } catch { /* ignore */ }
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

        try { window.dispatchEvent(new CustomEvent('visionguard:wake', { detail: { command: inlineCommand } })) } catch {}
        try { recognition.stop() } catch {}
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
        enabled: !!e.detail.enabled,
        name:    e.detail.name  || settingsRef.current.name  || 'Jarvis',
        voice:   e.detail.voice || settingsRef.current.voice || 'male',
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
        // Jarvis stopped speaking — RESET (not max) so wake word is available quickly
        pausedUntilRef.current = Date.now() + 800
        setTimeout(() => { if (settingsRef.current.enabled) startRecognition() }, 900)
      }
    }

    const onJarvisClosed = () => {
      // Panel closed manually — clear any lingering pause and restart immediately
      pausedUntilRef.current = Date.now() - 1
      setTimeout(() => { if (settingsRef.current.enabled) startRecognition() }, 400)
    }

    window.addEventListener('pointerdown',                         onGesture)
    window.addEventListener('visionguard:assistant-settings',      onSettings)
    window.addEventListener('visionguard:assistant-speaking',      onSpeaking)
    window.addEventListener('visionguard:jarvis-closed',           onJarvisClosed)

    return () => {
      window.removeEventListener('pointerdown',                    onGesture)
      window.removeEventListener('visionguard:assistant-settings', onSettings)
      window.removeEventListener('visionguard:assistant-speaking', onSpeaking)
      window.removeEventListener('visionguard:jarvis-closed',      onJarvisClosed)
      stopRecognition()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return null
}
