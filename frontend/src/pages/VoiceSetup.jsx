import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Mic, CheckCircle, AlertCircle, ChevronRight, SkipForward } from 'lucide-react'
import authService from '../services/authService'
import { blobToWavBase64 } from '../utils/audioUtils'

export default function VoiceSetup() {
  const navigate = useNavigate()
  const [phase, setPhase]         = useState('intro')   // intro | recording | processing | done | error
  const [countdown, setCountdown] = useState(5)
  const [errorMsg, setErrorMsg]   = useState('')
  const mediaRecorderRef          = useRef(null)
  const chunksRef                 = useRef([])

  const startRecording = async () => {
    setPhase('recording')
    setCountdown(5)
    setErrorMsg('')
    chunksRef.current = []

    let stream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      setErrorMsg('Microphone access denied. Please allow microphone and try again.')
      setPhase('error')
      return
    }

    const mr = new MediaRecorder(stream)
    mediaRecorderRef.current = mr
    mr.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data) }
    mr.start(200)

    let remaining = 5
    const tick = setInterval(() => {
      remaining -= 1
      setCountdown(remaining)
      if (remaining <= 0) {
        clearInterval(tick)
        mr.stop()
        stream.getTracks().forEach(t => t.stop())
      }
    }, 1000)

    mr.onstop = async () => {
      setPhase('processing')
      const blob = new Blob(chunksRef.current, { type: mr.mimeType || 'audio/webm' })
      try {
        const b64 = await blobToWavBase64(blob)

        const axios = authService.getAuthAxios()
        await axios.post('/user/enroll-voice', { audio_base64: b64 })
        setPhase('done')
      } catch (err) {
        setErrorMsg(err?.response?.data?.detail || 'Enrollment failed. Please try again.')
        setPhase('error')
      }
    }
  }

  return (
    <div className="min-h-screen bg-[#04080f] flex items-center justify-center p-6">
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md bg-[#060c18] rounded-2xl border border-slate-800/60 p-8 text-center"
      >
        {/* Header */}
        <div className="mb-8">
          <div className="w-16 h-16 bg-purple-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
            <Mic className="w-8 h-8 text-purple-400" />
          </div>
          <h1 className="text-2xl font-bold text-white mb-2">Register Your Voice</h1>
          <p className="text-slate-400 text-sm leading-relaxed">
            This lets Jarvis recognize only you &mdash; like Google Voice Match.
            Speak naturally when prompted.
          </p>
        </div>

        <AnimatePresence mode="wait">
          {phase === 'intro' && (
            <motion.div key="intro" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-4">
              <div className="bg-slate-800/30 rounded-xl p-4 text-left space-y-2">
                <p className="text-slate-300 text-sm font-medium">What to say (any 1–2 sentences):</p>
                <p className="text-slate-400 text-sm italic">"Hey Jarvis, show me the latest alerts"</p>
                <p className="text-slate-400 text-sm italic">"VisionGuard, what happened at the entrance?"</p>
              </div>
              <button
                onClick={startRecording}
                className="w-full py-3 rounded-xl bg-gradient-to-r from-purple-600 to-pink-600 text-white font-semibold hover:from-purple-700 hover:to-pink-700 transition-all flex items-center justify-center gap-2"
              >
                <Mic className="w-5 h-5" /> Start Recording (5 seconds)
              </button>
              <button
                onClick={() => navigate('/')}
                className="w-full py-3 rounded-xl border border-slate-700 text-slate-400 hover:text-white hover:border-slate-600 transition-all flex items-center justify-center gap-2 text-sm"
              >
                <SkipForward className="w-4 h-4" /> Skip for now
              </button>
            </motion.div>
          )}

          {phase === 'recording' && (
            <motion.div key="recording" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-6 py-4">
              <div className="relative w-28 h-28 mx-auto">
                {[1, 2, 3].map(i => (
                  <motion.div
                    key={i}
                    className="absolute inset-0 rounded-full border-2 border-purple-500/40"
                    animate={{ scale: [1, 1.4 + i * 0.2], opacity: [0.6, 0] }}
                    transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.4 }}
                  />
                ))}
                <div className="absolute inset-0 bg-purple-600/20 rounded-full flex items-center justify-center">
                  <Mic className="w-10 h-10 text-purple-400" />
                </div>
              </div>
              <div>
                <p className="text-red-400 font-semibold text-lg">● Recording</p>
                <p className="text-slate-400 text-sm mt-1">
                  Speak naturally&hellip; <span className="text-white font-bold text-2xl">{countdown}s</span>
                </p>
              </div>
            </motion.div>
          )}

          {phase === 'processing' && (
            <motion.div key="processing" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-4 py-8">
              <div className="w-12 h-12 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto" />
              <p className="text-slate-300">Analyzing your voice fingerprint&hellip;</p>
            </motion.div>
          )}

          {phase === 'done' && (
            <motion.div key="done" initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }} className="space-y-6">
              <div className="w-20 h-20 bg-green-900/30 rounded-full flex items-center justify-center mx-auto">
                <CheckCircle className="w-10 h-10 text-green-400" />
              </div>
              <div>
                <p className="text-white font-semibold text-xl">Voice Registered!</p>
                <p className="text-slate-400 text-sm mt-2 leading-relaxed">
                  Your voice fingerprint has been saved. Go to{' '}
                  <span className="text-purple-400">Settings → AI Assistant</span> and enable{' '}
                  <span className="text-purple-400">Voice Lock</span> to activate owner-only access.
                </p>
              </div>
              <button
                onClick={() => navigate('/')}
                className="w-full py-3 rounded-xl bg-gradient-to-r from-purple-600 to-pink-600 text-white font-semibold hover:from-purple-700 hover:to-pink-700 transition-all flex items-center justify-center gap-2"
              >
                Continue to Dashboard <ChevronRight className="w-5 h-5" />
              </button>
            </motion.div>
          )}

          {phase === 'error' && (
            <motion.div key="error" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-4">
              <div className="w-16 h-16 bg-red-900/30 rounded-full flex items-center justify-center mx-auto">
                <AlertCircle className="w-8 h-8 text-red-400" />
              </div>
              <p className="text-red-300 text-sm">{errorMsg}</p>
              <button
                onClick={() => setPhase('intro')}
                className="w-full py-3 rounded-xl border border-slate-700 text-slate-300 hover:border-slate-600 transition-all"
              >
                Try Again
              </button>
              <button
                onClick={() => navigate('/')}
                className="w-full py-2 text-slate-500 hover:text-slate-400 text-sm transition-all"
              >
                Skip for now
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  )
}
