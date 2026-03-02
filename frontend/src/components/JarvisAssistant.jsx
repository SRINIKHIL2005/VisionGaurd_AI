import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Mic, MicOff, Send, ChevronDown } from 'lucide-react'
import JarvisOrb from './JarvisOrb'
import authService from '../services/authService'

/**
 * JarvisAssistant — Global Siri-style overlay.
 *
 * Mounts once in App.jsx and listens for:
 *   visionguard:wake           → open + auto-narrate if analysis available
 *   visionguard:jarvis-open    → open panel (e.g. from manual button)
 *   visionguard:assistant-settings → sync settings
 *   visionguard:live-analysis  → latest detection data for context
 */

const GREETINGS = [
  "Hey! What's up?",
  "I'm listening. Go ahead.",
  "At your service. What do you need?",
  "Yeah? What can I do for you?",
  "I'm here. Talk to me.",
  "Go ahead, I'm all ears.",
  "What's on your mind?",
  "Ready when you are.",
]
export default function JarvisAssistant() {
  const navigate = useNavigate()
  const location = useLocation()

  const [open, setOpen] = useState(false)
  const [orbState, setOrbState] = useState('idle')  // idle | listening | thinking | speaking
  const [messages, setMessages] = useState([])       // { role:'user'|'jarvis', text, time }
  const [transcript, setTranscript]   = useState('') // interim speech transcript
  const [textInput, setTextInput]     = useState('')
  const [status, setStatus]           = useState(null)  // { type:'info'|'error'|'success', message }
  const [micBlocked, setMicBlocked]   = useState(false)
  const [assistantSettings, setAssistantSettings] = useState({ enabled: false, name: 'Jarvis', voice: 'male', web_control_enabled: false })
  const [liveCctvActive, setLiveCctvActive] = useState(false)

  // Refs that don't need re-render
  const settingsRef        = useRef({ enabled: false, name: 'Jarvis', voice: 'male', web_control_enabled: false })
  const latestAnalysisRef  = useRef(null)
  const recognitionRef     = useRef(null)
  const orbStateRef        = useRef('idle')
  const chatEndRef         = useRef(null)
  const callNarrateRef     = useRef(null)
  const startListeningRef  = useRef(null)
  const liveCctvActiveRef  = useRef(false)
  const locationRef        = useRef('/')

  // Keep location ref in sync
  useEffect(() => { locationRef.current = location.pathname }, [location.pathname])
  // Keep liveCctvActive ref in sync
  useEffect(() => { liveCctvActiveRef.current = liveCctvActive }, [liveCctvActive])

  // ── Preload browser voices (Chrome lazy-loads them) ──────────────────────
  useEffect(() => {
    const load = () => window.speechSynthesis.getVoices()
    load()
    window.speechSynthesis.onvoiceschanged = load
    return () => { window.speechSynthesis.onvoiceschanged = null }
  }, [])

  // Keep ref in sync with state
  useEffect(() => { settingsRef.current = assistantSettings }, [assistantSettings])
  useEffect(() => { orbStateRef.current = orbState }, [orbState])

  // Auto-scroll history to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, transcript])

  // ── Listen for page state updates (e.g. live CCTV active/inactive) ───────
  useEffect(() => {
    const onPageState = (e) => {
      if (e?.detail?.live_cctv_active !== undefined) {
        setLiveCctvActive(!!e.detail.live_cctv_active)
        liveCctvActiveRef.current = !!e.detail.live_cctv_active
      }
    }
    window.addEventListener('visionguard:page-state-update', onPageState)
    return () => window.removeEventListener('visionguard:page-state-update', onPageState)
  }, [])

  // ── Load settings on mount ────────────────────────────────────────────────
  useEffect(() => {
    const load = async () => {
      try {
        const axios = authService.getAuthAxios()
        const res = await axios.get('/user/assistant-settings')
        if (res.data?.settings) {
          const s = {
            enabled:             !!res.data.settings.enabled,
            name:                res.data.settings.name  || 'Jarvis',
            voice:               res.data.settings.voice || 'male',
            web_control_enabled: !!res.data.settings.web_control_enabled,
          }
          setAssistantSettings(s)
          settingsRef.current = s
        }
      } catch { /* ignore — keep defaults */ }
    }
    load()
  }, [])

  // ── Audio helpers (kept for legacy safety) ───────────────────────────────
  const stopAudio = useCallback(() => { /* no-op: TTS is browser speechSynthesis */ }, [])

  const dispatchSpeaking = (speaking) => {
    try {
      window.dispatchEvent(new CustomEvent('visionguard:assistant-speaking', { detail: { speaking } }))
    } catch {}
  }

  // ── Browser TTS (speechSynthesis) ──────────────────────────────────────
  const speakText = useCallback((text) => {
    return new Promise((resolve) => {
      try { window.speechSynthesis.cancel() } catch {}

      const utter = new SpeechSynthesisUtterance(text)
      utter.lang   = 'en-US'
      utter.rate   = 0.97
      utter.pitch  = 0.88
      utter.volume = 1.0

      // Pick best available voice — explicit gender matching, avoid wrong-gender fallbacks
      const voices = window.speechSynthesis.getVoices()
      const pref   = (settingsRef.current.voice || 'male').toLowerCase()

      // Tier 1: neural/online voices by name
      const neuralMale   = voices.find(v => /microsoft.*(guy|ryan|brian)/i.test(v.name))
      const neuralFemale = voices.find(v => /microsoft.*(jenny|aria|sonia|natasha)/i.test(v.name))
      // Tier 2: Google voices
      const googleMale   = voices.find(v => /google.*us.*male|google us/i.test(v.name))
      const googleFemale = voices.find(v => /google.*us.*female/i.test(v.name))
      // Tier 3: Known Windows SAPI voice names (explicit — David=male, Zira=female)
      const sapiMale     = voices.find(v => /\bdavid\b|\bmark\b|\bgeorge\b|\bjames\b/i.test(v.name))
      const sapiFemale   = voices.find(v => /\bzira\b|\bhazel\b|\bhelena\b|\bsabina\b/i.test(v.name))
      // Tier 4: Any voice whose name contains the gender keyword
      const keyMale      = voices.find(v => /\bmale\b/i.test(v.name))
      const keyFemale    = voices.find(v => /\bfemale\b/i.test(v.name))
      // Tier 5: absolute last resort — first en-US but only if gender matches
      const allEnUS      = voices.filter(v => v.lang === 'en-US')
      const fallbackMale   = allEnUS.find(v => !/zira|female|woman/i.test(v.name)) || allEnUS[0] || voices[0]
      const fallbackFemale = allEnUS.find(v => /zira|female|woman|girl|aria|jenny/i.test(v.name)) ||
                             allEnUS.find(v => !/david|mark|male/i.test(v.name)) || allEnUS[0] || voices[0]

      if (pref === 'female') {
        utter.voice = neuralFemale || googleFemale || sapiFemale || keyFemale || fallbackFemale || null
      } else {
        utter.voice = neuralMale || googleMale || sapiMale || keyMale || fallbackMale || null
        utter.pitch = 0.80
      }

      // Chrome bug: silently pauses long utterances — keepalive resume every 10s
      const keepAlive = setInterval(() => {
        if (window.speechSynthesis.paused) window.speechSynthesis.resume()
      }, 10000)

      const done = () => {
        clearInterval(keepAlive)
        // Cancel to fully release Chrome’s audio context before mic starts
        try { window.speechSynthesis.cancel() } catch {}
        resolve()
      }
      utter.onend   = done
      utter.onerror = done

      window.speechSynthesis.speak(utter)
    })
  }, [])

  const stopSpeech = useCallback(() => {
    try { window.speechSynthesis.cancel() } catch {}
  }, [])

  // ── Execute a Jarvis action returned from the backend ─────────────────────
  const executeJarvisAction = useCallback((action) => {
    if (!action || action.type === 'none') return
    switch (action.type) {
      case 'navigate':
        navigate(action.path)
        break
      case 'navigate_and_start_live':
        navigate('/live')
        setTimeout(() => {
          window.dispatchEvent(new CustomEvent('visionguard:jarvis-start-live'))
        }, 700)
        break
      case 'stop_live_cctv':
        window.dispatchEvent(new CustomEvent('visionguard:jarvis-stop-live'))
        break
      default:
        break
    }
  }, [navigate])

  // ── Core: get text from backend → speak via browser TTS ──────────────────
  const callNarrate = useCallback(async (userQuery) => {
    orbStateRef.current = 'thinking'
    setOrbState('thinking')
    setStatus(null)
    stopSpeech()

    try {
      const axios = authService.getAuthAxios()
      const res   = await axios.post('/assistant/narrate', {
        analysis:     latestAnalysisRef.current || {},
        user_query:   userQuery || '',
        frame_base64: latestAnalysisRef.current?.annotated_image || null,
        page_context: {
          current_page:        locationRef.current,
          live_cctv_active:    liveCctvActiveRef.current,
          web_control_enabled: settingsRef.current.web_control_enabled,
        },
      })

      const text = res.data?.jarvis?.text || 'I have no analysis to report.'
      const name = settingsRef.current.name

      // Execute any UI action the backend determined
      const action = res.data?.jarvis?.action
      if (action && action.type !== 'none') executeJarvisAction(action)

      setMessages(prev => [...prev, {
        role: 'jarvis',
        text,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }])

      orbStateRef.current = 'speaking'
      setOrbState('speaking')
      dispatchSpeaking(true)
      setStatus({ type: 'success', message: `${name} is speaking` })

      await speakText(text)

      dispatchSpeaking(false)
      setStatus(null)

      // Chrome needs a moment to fully release audio context before mic opens
      await new Promise(r => setTimeout(r, 350))

      // Auto-reopen mic for follow-up so user can keep talking naturally
      if (orbStateRef.current !== 'listening') {
        orbStateRef.current = 'listening'
        setOrbState('listening')
        startListeningRef.current?.()
      }

    } catch (err) {
      orbStateRef.current = 'idle'
      setOrbState('idle')
      dispatchSpeaking(false)
      stopSpeech()
      const detail = err.response?.data?.detail
      if (detail === 'AI Assistant is disabled in Settings') {
        setStatus({ type: 'error', message: 'Enable AI Assistant in Settings first.' })
      } else {
        setStatus({ type: 'error', message: detail || 'Could not reach the assistant backend.' })
      }
    }
  }, [speakText, stopSpeech, executeJarvisAction])

  // Keep refs in sync so closures always have the latest version
  useEffect(() => { callNarrateRef.current   = callNarrate   }, [callNarrate])

  // ── Client-side instant keyword detection (fires BEFORE backend responds) ────
  // Mirrors the backend keyword lists so navigation is instant, no LLM wait.
  const _CLIENT_PAGES = {
    'live cctv': '/live', 'live cctv page': '/live',
    'image analysis': '/image', 'image analysis page': '/image',
    'video analysis': '/video', 'video analysis page': '/video',
    'face database': '/database', 'face database page': '/database',
    'settings': '/settings', 'setting': '/settings', 'settings page': '/settings',
    'dashboard': '/', 'home': '/', 'home page': '/',
    'cctv': '/live', 'live': '/live', 'camera': '/live',
    'image': '/image', 'video': '/video',
    'database': '/database', 'faces': '/database', 'face': '/database',
  }
  const _CLIENT_NAV_VERBS = ['go to', 'navigate to', 'open', 'show me', 'take me to', 'switch to', 'launch', 'visit', 'bring up']
  const _CLIENT_LIVE_ON   = [
    'start live', 'turn on live', 'on the live', 'enable live', 'activate live',
    'begin live', 'start cctv', 'start monitoring', 'turn on cctv', 'start camera',
    'start the live', 'on live', 'open live cctv',
    'on the cctv', 'on cctv', 'ok on the cctv', 'turn on the cctv', 'turn on the live',
    'open the live', 'start the cctv', 'open cctv', 'begin cctv', 'activate cctv',
    'enable cctv', 'on camera', 'start camera feed', 'start the camera',
  ]
  const _CLIENT_LIVE_OFF  = [
    'stop live', 'turn off live', 'off the live', 'disable live',
    'stop monitoring', 'stop cctv', 'turn off cctv', 'stop camera',
    'off the cctv', 'off cctv', 'turn off the cctv', 'close cctv',
    'close live', 'stop the live', 'stop the cctv', 'disable cctv',
  ]

  const detectAndActLocally = useCallback((query) => {
    if (!settingsRef.current.web_control_enabled) return false
    const q = (query || '').toLowerCase().trim()
    if (!q) return false

    if (_CLIENT_LIVE_ON.some(p => q.includes(p))) {
      navigate('/live')
      setTimeout(() => window.dispatchEvent(new CustomEvent('visionguard:jarvis-start-live')), 750)
      return true
    }
    if (_CLIENT_LIVE_OFF.some(p => q.includes(p))) {
      window.dispatchEvent(new CustomEvent('visionguard:jarvis-stop-live'))
      return true
    }
    const hasVerb = _CLIENT_NAV_VERBS.some(v => q.includes(v))
    if (hasVerb || q.split(' ').length <= 5) {
      // Longest keyword first to avoid 'image' matching before 'image analysis'
      const sorted = Object.keys(_CLIENT_PAGES).sort((a, b) => b.length - a.length)
      for (const kw of sorted) {
        if (q.includes(kw)) {
          navigate(_CLIENT_PAGES[kw])
          return true
        }
      }
    }
    return false
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navigate])

  const detectAndActLocallyRef = useRef(detectAndActLocally)
  useEffect(() => { detectAndActLocallyRef.current = detectAndActLocally }, [detectAndActLocally])

  // ── Voice command listener ────────────────────────────────────────────────
  const stopListening = useCallback(() => {
    try {
      if (recognitionRef.current) {
        recognitionRef.current.onresult = null
        recognitionRef.current.onerror  = null
        recognitionRef.current.onend    = null
        recognitionRef.current.stop()
      }
    } catch {}
    recognitionRef.current = null
  }, [])

  const startListening = useCallback(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) {
      setStatus({ type: 'error', message: 'Speech recognition not supported in this browser. Use Chrome or Edge.' })
      return
    }
    // Guard: don’t interrupt thinking/speaking (check ref directly — state may lag)
    if (orbStateRef.current === 'thinking' || orbStateRef.current === 'speaking') return

    stopListening()
    setTranscript('')
    setStatus(null)
    // Sync ref immediately — don’t wait for React re-render
    orbStateRef.current = 'listening'
    setOrbState('listening')
    setMicBlocked(false)

    const recognition = new SR()
    recognition.continuous     = false
    recognition.interimResults = true
    recognition.lang           = 'en-US'
    recognitionRef.current     = recognition

    recognition.onresult = (e) => {
      let interim = '', final = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) final  += e.results[i][0].transcript
        else                      interim += e.results[i][0].transcript
      }
      setTranscript(final || interim)

      if (final) {
        const text = final.trim()
        recognition.stop()
        setTranscript('')
        setMessages(prev => [...prev, {
          role: 'user', text,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        }])
        detectAndActLocallyRef.current?.(text)   // instant client-side action
        callNarrateRef.current?.(text)           // backend for verbal response
      }
    }

    recognition.onerror = (e) => {
      orbStateRef.current = 'idle'
      setOrbState('idle')
      if (e.error === 'not-allowed' || e.error === 'audio-capture') {
        setMicBlocked(true)
        setStatus({ type: 'error', message: 'Microphone access denied. Enable it in browser settings and try again.' })
      } else if (e.error === 'no-speech') {
        setStatus({ type: 'info', message: 'No speech detected. Tap the mic and try again.' })
      } else if (e.error !== 'aborted') {
        setStatus({ type: 'error', message: `Mic error: ${e.error}` })
      }
    }

    recognition.onend = () => {
      recognitionRef.current = null
      if (orbStateRef.current === 'listening') {
        orbStateRef.current = 'idle'
        setOrbState('idle')
      }
    }

    try { recognition.start() } catch { orbStateRef.current = 'idle'; setOrbState('idle') }
  }, [stopListening])

  // Wire startListeningRef after definition
  useEffect(() => { startListeningRef.current = startListening }, [startListening])

  // ── Wake: greet + listen (Siri-style) ──────────────────────────────────
  const greetAndListen = useCallback(async () => {
    const greeting = GREETINGS[Math.floor(Math.random() * GREETINGS.length)]
    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    setMessages(prev => [...prev, { role: 'jarvis', text: greeting, time: now }])
    orbStateRef.current = 'speaking'
    setOrbState('speaking')
    dispatchSpeaking(true)
    await speakText(greeting)
    dispatchSpeaking(false)
    // Give Chrome 350ms to release audio context before mic opens
    await new Promise(r => setTimeout(r, 350))
    orbStateRef.current = 'listening'
    setOrbState('listening')
    startListeningRef.current?.()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [speakText])

  // ── Handle opening/closing ────────────────────────────────────────────────
  const handleClose = useCallback(() => {
    stopAudio()
    stopSpeech()
    stopListening()
    setOpen(false)
    setOrbState('idle')
    setTranscript('')
    setStatus(null)
    dispatchSpeaking(false)
    // Tell WakeWordListener to restart immediately
    try { window.dispatchEvent(new CustomEvent('visionguard:jarvis-closed')) } catch {}
  }, [stopAudio, stopSpeech, stopListening])

  const handleOpen = useCallback((fromWake = false, inlineCommand = '') => {
    setOpen(true)
    setStatus(null)
    setTranscript('')

    if (fromWake) {
      if (inlineCommand) {
        // Inline command: skip greeting, run action immediately + call backend for verbal confirm
        const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        setMessages(prev => [...prev, { role: 'user', text: inlineCommand, time: now }])
        detectAndActLocallyRef.current?.(inlineCommand)  // instant nav, no wait
        setTimeout(() => callNarrateRef.current?.(inlineCommand), 80)  // backend for spoken confirmation
      } else {
        // Siri behaviour: greet + listen, don't auto-narrate immediately
        setTimeout(() => greetAndListen(), 320)
      }
    }
  }, [greetAndListen])

  // ── Text input ────────────────────────────────────────────────────────────
  const handleTextSubmit = () => {
    const text = textInput.trim()
    if (!text || orbState === 'thinking' || orbState === 'speaking') return
    setTextInput('')
    setMessages(prev => [...prev, {
      role: 'user', text,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }])
    detectAndActLocally(text)   // instant client-side action (if keyword match)
    callNarrate(text)           // backend for verbal response
  }

  // ── Global event listeners ────────────────────────────────────────────────
  useEffect(() => {
    const onWake        = (e) => handleOpen(true, e?.detail?.command || '')
    const onJarvisOpen  = () => handleOpen(false)
    const onSettings    = (e) => {
      if (!e?.detail) return
      const s = {
        enabled:             !!e.detail.enabled,
        name:                e.detail.name  || 'Jarvis',
        voice:               e.detail.voice || 'male',
        web_control_enabled: !!e.detail.web_control_enabled,
      }
      setAssistantSettings(s)
      settingsRef.current = s
    }
    const onAnalysis = (e) => {
      if (e?.detail) latestAnalysisRef.current = e.detail
    }

    window.addEventListener('visionguard:wake',               onWake)
    window.addEventListener('visionguard:jarvis-open',        onJarvisOpen)
    window.addEventListener('visionguard:assistant-settings', onSettings)
    window.addEventListener('visionguard:live-analysis',      onAnalysis)

    return () => {
      window.removeEventListener('visionguard:wake',               onWake)
      window.removeEventListener('visionguard:jarvis-open',        onJarvisOpen)
      window.removeEventListener('visionguard:assistant-settings', onSettings)
      window.removeEventListener('visionguard:live-analysis',      onAnalysis)
    }
  }, [handleOpen])

  const name = assistantSettings.name || 'Jarvis'

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            key="jarvis-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="fixed inset-0 z-50"
            style={{
              background: 'linear-gradient(to top, rgba(3,7,18,0.97) 0%, rgba(3,7,18,0.88) 60%, rgba(15,10,40,0.82) 100%)',
              backdropFilter: 'blur(22px)',
              WebkitBackdropFilter: 'blur(22px)',
            }}
          >
            {/* Top bar */}
            <div className="absolute top-0 left-0 right-0 flex items-center justify-between px-6 py-5">
              <div className="flex items-center gap-3">
                <motion.div
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ background: orbState === 'idle' ? '#6366f1' : orbState === 'listening' ? '#10b981' : orbState === 'thinking' ? '#ec4899' : '#3b82f6' }}
                  animate={{ opacity: [1, 0.4, 1] }}
                  transition={{ duration: 1.5, repeat: Infinity }}
                />
                <span className="text-white/70 text-sm font-medium tracking-wide">{name}</span>
                <span className="text-white/30 text-xs uppercase tracking-widest">
                  {orbState === 'idle' ? 'Ready' : orbState === 'listening' ? 'Listening' : orbState === 'thinking' ? 'Thinking' : 'Speaking'}
                </span>
              </div>
              <button
                onClick={handleClose}
                className="p-2.5 rounded-full hover:bg-white/10 transition-colors text-white/50 hover:text-white"
                aria-label="Close assistant"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Chat history — fills space between top bar and orb section */}
            <div className="absolute inset-x-0 top-16 bottom-[400px] overflow-y-auto px-4 sm:px-6">
              <div className="max-w-2xl mx-auto py-4 space-y-3">

                {/* Empty state */}
                {messages.length === 0 && !status && (
                  <div className="flex flex-col items-center justify-center h-32 gap-2">
                    <p className="text-white/25 text-sm text-center">
                      Tap the mic or type below to talk to {name}
                    </p>
                  </div>
                )}

                {/* Messages */}
                {messages.map((msg, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, y: 8, scale: 0.97 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    transition={{ duration: 0.25 }}
                    className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    {msg.role === 'jarvis' && (
                      <div
                        className="w-7 h-7 rounded-full flex-shrink-0 mr-2 mt-1 flex items-center justify-center text-white text-xs font-bold"
                        style={{ background: 'linear-gradient(135deg, #6366f1, #ec4899)' }}
                      >
                        J
                      </div>
                    )}
                    <div
                      className={`max-w-[80%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${
                        msg.role === 'user'
                          ? 'bg-indigo-600/70 text-white rounded-tr-sm'
                          : 'bg-white/8 text-white/90 rounded-tl-sm border border-white/10'
                      }`}
                    >
                      <p>{msg.text}</p>
                      <p className={`text-[10px] mt-1.5 ${msg.role === 'user' ? 'text-indigo-200/60' : 'text-white/30'}`}>
                        {msg.time}
                      </p>
                    </div>
                  </motion.div>
                ))}

                {/* Interim transcript bubble */}
                <AnimatePresence>
                  {transcript && (
                    <motion.div
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      className="flex justify-end"
                    >
                      <div className="max-w-[80%] px-4 py-3 rounded-2xl rounded-tr-sm text-sm bg-indigo-600/35 text-white/60 italic border border-indigo-500/20">
                        {transcript}…
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Thinking dots */}
                <AnimatePresence>
                  {orbState === 'thinking' && (
                    <motion.div
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      className="flex justify-start"
                    >
                      <div
                        className="w-7 h-7 rounded-full flex-shrink-0 mr-2 mt-1 flex items-center justify-center text-white text-xs font-bold"
                        style={{ background: 'linear-gradient(135deg, #6366f1, #ec4899)' }}
                      >
                        J
                      </div>
                      <div className="px-4 py-3 rounded-2xl rounded-tl-sm bg-white/8 border border-white/10 flex gap-1.5 items-center">
                        {[0, 0.2, 0.4].map((d) => (
                          <motion.div
                            key={d}
                            className="w-2 h-2 rounded-full bg-pink-400/80"
                            animate={{ opacity: [0.3, 1, 0.3], scale: [0.8, 1.2, 0.8] }}
                            transition={{ duration: 0.9, repeat: Infinity, delay: d }}
                          />
                        ))}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Status message */}
                <AnimatePresence>
                  {status && (
                    <motion.div
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -4 }}
                      className={`mx-auto max-w-sm px-4 py-2.5 rounded-xl text-xs text-center border ${
                        status.type === 'error'
                          ? 'bg-red-500/15 text-red-300 border-red-500/20'
                          : status.type === 'info'
                            ? 'bg-blue-500/15 text-blue-300 border-blue-500/20'
                            : 'bg-green-500/15 text-green-300 border-green-500/20'
                      }`}
                    >
                      {status.message}
                    </motion.div>
                  )}
                </AnimatePresence>

                <div ref={chatEndRef} />
              </div>
            </div>

            {/* Bottom orb section — fixed at bottom */}
            <div
              className="absolute inset-x-0 bottom-0 flex flex-col items-center"
              style={{
                background: 'linear-gradient(to top, rgba(3,7,18,1) 55%, transparent)',
                paddingBottom: 'env(safe-area-inset-bottom, 24px)',
              }}
            >
              {/* Scroll hint if history is long */}
              {messages.length > 3 && (
                <button
                  className="mb-2 p-1.5 rounded-full bg-white/10 text-white/40 hover:text-white/70 transition-colors"
                  onClick={() => chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })}
                >
                  <ChevronDown className="w-4 h-4" />
                </button>
              )}

              {/* State label */}
              <p className="text-white/35 text-xs tracking-[0.25em] uppercase mb-5">
                {orbState === 'idle'      && `${name} · Ready`}
                {orbState === 'listening' && 'Listening…'}
                {orbState === 'thinking'  && 'Thinking…'}
                {orbState === 'speaking'  && 'Speaking'}
              </p>

              {/* Orb */}
              <JarvisOrb state={orbState} size={174} />

              {/* Controls row */}
              <div className="flex items-center gap-3 mt-7 mb-8 px-6 w-full max-w-md">
                {/* Mic button */}
                <motion.button
                  onClick={orbState === 'listening' ? stopListening : startListening}
                  disabled={orbState === 'thinking' || orbState === 'speaking'}
                  whileTap={{ scale: 0.92 }}
                  className={`flex-shrink-0 w-12 h-12 rounded-full flex items-center justify-center transition-all ${
                    orbState === 'listening'
                      ? 'bg-green-500 text-white shadow-lg shadow-green-500/40'
                      : micBlocked
                        ? 'bg-red-500/25 text-red-400 border border-red-500/30'
                        : 'bg-white/10 text-white hover:bg-white/20 border border-white/10 disabled:opacity-30 disabled:cursor-not-allowed'
                  }`}
                  title={micBlocked ? 'Microphone blocked' : orbState === 'listening' ? 'Stop listening' : 'Start listening'}
                >
                  {micBlocked ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
                </motion.button>

                {/* Text input pill */}
                <div className="flex-1 flex items-center gap-2 bg-white/8 border border-white/12 rounded-full px-4 py-2.5 focus-within:border-indigo-500/50 transition-colors">
                  <input
                    type="text"
                    value={textInput}
                    onChange={e => setTextInput(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleTextSubmit()}
                    placeholder={`Ask ${name} anything…`}
                    className="flex-1 bg-transparent text-white placeholder-white/30 text-sm outline-none min-w-0"
                  />
                  <motion.button
                    onClick={handleTextSubmit}
                    disabled={!textInput.trim() || orbState === 'thinking' || orbState === 'speaking'}
                    whileTap={{ scale: 0.88 }}
                    className="text-indigo-400/80 hover:text-indigo-300 disabled:opacity-25 transition-colors flex-shrink-0"
                  >
                    <Send className="w-4 h-4" />
                  </motion.button>
                </div>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
