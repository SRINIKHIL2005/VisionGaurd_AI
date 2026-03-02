import { useState, useRef, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Camera, Video, Play, Square, AlertCircle, Activity, Target, MessageCircle, Settings, Mic } from 'lucide-react'
import Webcam from 'react-webcam'
import authService from '../services/authService'
import { Link } from 'react-router-dom'

export default function LiveCCTV() {
  const [isMonitoring, setIsMonitoring] = useState(false)
  const [currentFrame, setCurrentFrame] = useState(null)
  const [annotatedFrame, setAnnotatedFrame] = useState(null)
  const [result, setResult] = useState(null)
  const [cameraIndex, setCameraIndex] = useState(0)
  const [frameSkip, setFrameSkip] = useState(2)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const webcamRef = useRef(null)
  const overlayCanvasRef = useRef(null)
  const feedContainerRef = useRef(null)
  const intervalRef = useRef(null)
  const isMonitoringRef = useRef(false)  // stable ref for event handlers

  const startMonitoring = () => {
    if (isMonitoringRef.current) return  // already running
    isMonitoringRef.current = true
    setIsMonitoring(true)
    // Inform Jarvis that live CCTV is now active
    window.dispatchEvent(new CustomEvent('visionguard:page-state-update', { detail: { live_cctv_active: true } }))
    
    // Process frames periodically
    intervalRef.current = setInterval(async () => {
      // Skip if already analyzing
      if (isAnalyzing) {
        console.log('⏭️ Skipping frame - analysis in progress')
        return
      }
      
      if (webcamRef.current) {
        const imageSrc = webcamRef.current.getScreenshot()
        if (imageSrc) {
          setCurrentFrame(imageSrc)
          // Convert base64 to blob and send to backend
          await analyzeFrame(imageSrc)
        }
      }
    }, frameSkip * 500) // Adjust based on frame skip
  }

  const stopMonitoring = () => {
    isMonitoringRef.current = false
    setIsMonitoring(false)
    // Inform Jarvis that live CCTV is now inactive
    window.dispatchEvent(new CustomEvent('visionguard:page-state-update', { detail: { live_cctv_active: false } }))
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
    }
    setResult(null)
    setAnnotatedFrame(null)
  }

  // Listen for Jarvis voice commands to start/stop live monitoring
  // Also broadcast initial state on mount so JarvisAssistant stays in sync
  useEffect(() => {
    // Broadcast current state immediately so Jarvis knows if feed is on/off
    window.dispatchEvent(new CustomEvent('visionguard:page-state-update', { detail: { live_cctv_active: isMonitoringRef.current } }))

    const onJarvisStart = () => { if (!isMonitoringRef.current) startMonitoring() }
    const onJarvisStop  = () => { if (isMonitoringRef.current)  stopMonitoring()  }
    window.addEventListener('visionguard:jarvis-start-live', onJarvisStart)
    window.addEventListener('visionguard:jarvis-stop-live',  onJarvisStop)
    return () => {
      window.removeEventListener('visionguard:jarvis-start-live', onJarvisStart)
      window.removeEventListener('visionguard:jarvis-stop-live',  onJarvisStop)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])


  const analyzeFrame = async (imageBase64) => {
    setIsAnalyzing(true)
    try {
      // Convert base64 to blob
      const response = await fetch(imageBase64)
      const blob = await response.blob()
      
      const formData = new FormData()
        formData.append("file", blob, "frame.jpg");
        formData.append("camera_id", "livecctv");
      formData.append('return_annotated', 'true')

      const axios = authService.getAuthAxios()
      const apiResponse = await axios.post('/analyze/image', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })

      if (apiResponse.data) {
        setResult(apiResponse.data)
        // Set annotated image if available
        if (apiResponse.data.annotated_image) {
          setAnnotatedFrame(`data:image/jpeg;base64,${apiResponse.data.annotated_image}`)
        }
      }
    } catch (err) {
      console.error('Frame analysis error:', err)
    } finally {
      setIsAnalyzing(false)
    }
  }

  // --- Draw tracking overlay on canvas whenever result changes ---
  useEffect(() => {
    const canvas = overlayCanvasRef.current
    const container = feedContainerRef.current
    if (!canvas || !container) return

    const ctx = canvas.getContext('2d')
    // Match canvas size to displayed video container
    const rect = container.getBoundingClientRect()
    canvas.width = rect.width
    canvas.height = rect.height
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    if (!result || !result.objects || !isMonitoring) return

    // We need the original image dimensions to scale bboxes.
    // The backend works on the raw webcam frame (usually 640x480).
    const srcW = 640
    const srcH = 480
    const scaleX = canvas.width / srcW
    const scaleY = canvas.height / srcH

    result.objects.forEach((obj) => {
      if (!obj.bbox || obj.bbox.length < 4) return
      const [x1, y1, x2, y2] = obj.bbox
      const sx = x1 * scaleX
      const sy = y1 * scaleY
      const sw = (x2 - x1) * scaleX
      const sh = (y2 - y1) * scaleY

      const isPerson = (obj.label || '').toLowerCase() === 'person'
      const isSuspicious = (result.suspicious_objects || []).includes(obj.label)

      // Box color
      ctx.strokeStyle = isSuspicious ? '#ef4444' : isPerson ? '#3b82f6' : '#22c55e'
      ctx.lineWidth = 2
      ctx.strokeRect(sx, sy, sw, sh)

      // Label text
      let label = obj.label || 'object'
      if (obj.track_id != null) label = `#${obj.track_id} ${label}`
      label += ` ${(obj.confidence * 100).toFixed(0)}%`

      ctx.font = 'bold 13px Inter, system-ui, sans-serif'
      const tm = ctx.measureText(label)
      const pad = 3
      const lblH = 18
      ctx.fillStyle = isSuspicious ? '#ef4444' : isPerson ? '#3b82f6' : '#22c55e'
      ctx.fillRect(sx, sy - lblH - pad, tm.width + pad * 2, lblH + pad)
      ctx.fillStyle = '#fff'
      ctx.fillText(label, sx + pad, sy - pad - 2)
    })
  }, [result, isMonitoring])

  // Broadcast latest analysis to the global JarvisAssistant
  useEffect(() => {
    if (!result) return
    try {
      window.dispatchEvent(new CustomEvent('visionguard:live-analysis', { detail: result }))
    } catch {}
  }, [result])

  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="space-y-6">
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1 className="text-4xl font-bold bg-gradient-primary bg-clip-text text-transparent mb-2">
          Live CCTV Monitoring
        </h1>
        <p className="text-gray-600">Real-time surveillance and threat detection</p>
      </motion.div>

      {/* Telegram Notification Reminder */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="bg-blue-50 border-l-4 border-blue-500 p-4 rounded-lg"
      >
        <div className="flex items-start gap-3">
          <MessageCircle className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-sm text-blue-900">
              <strong>💡 Tip:</strong> Enable Telegram notifications to receive instant alerts when unknown faces are detected - 
              even when you're away from your computer!
            </p>
            <Link
              to="/settings"
              className="inline-flex items-center gap-1 text-sm text-blue-700 hover:text-blue-800 font-medium mt-2"
            >
              <Settings className="w-4 h-4" />
              Configure in Settings →
            </Link>
          </div>
        </div>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Camera Feed */}
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-100">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-gray-900 flex items-center">
                <Video className="w-6 h-6 mr-2 text-primary-500" />
                Live Feed {annotatedFrame && '(Annotated)'}
              </h2>
              <div className="flex items-center space-x-2">
                {isMonitoring && (
                  <span className="flex items-center text-red-600 font-semibold">
                    <span className="w-3 h-3 bg-red-600 rounded-full mr-2 animate-pulse"></span>
                    LIVE
                  </span>
                )}
              </div>
            </div>

            <div className="bg-black rounded-xl overflow-hidden aspect-video relative" ref={feedContainerRef}>
              {isMonitoring ? (
                annotatedFrame ? (
                  <img src={annotatedFrame} alt="Annotated Feed" className="w-full h-full object-cover" />
                ) : (
                  <Webcam
                    ref={webcamRef}
                    audio={false}
                    screenshotFormat="image/jpeg"
                    videoConstraints={{ deviceId: cameraIndex }}
                    className="w-full h-full object-cover"
                  />
                )
              ) : (
                <div className="w-full h-full flex items-center justify-center text-gray-400">
                  <div className="text-center">
                    <Camera className="w-16 h-16 mx-auto mb-4" />
                    <p>Camera feed will appear here</p>
                  </div>
                </div>
              )}
              {/* Tracking / bbox overlay */}
              <canvas
                ref={overlayCanvasRef}
                className="absolute inset-0 w-full h-full pointer-events-none"
                style={{ zIndex: 10 }}
              />
            </div>
          </div>

          {/* Object Detection Details */}
          {result && isMonitoring && result.objects && result.objects.length > 0 && (
            <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-100">
              <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                <Target className="w-5 h-5 mr-2 text-blue-600" />
                Detected Objects ({result.objects.length})
              </h3>
              <div className="space-y-2 max-h-60 overflow-y-auto">
                {result.objects.map((obj, idx) => {
                  const isSuspicious = result.suspicious_objects.includes(obj.label || obj.class)
                  return (
                    <div
                      key={idx}
                      className={`p-3 rounded-lg border-2 transition-all ${
                        isSuspicious
                          ? 'bg-red-50 border-red-300'
                          : 'bg-gray-50 border-gray-200'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-3">
                          {isSuspicious && (
                            <AlertCircle className="w-5 h-5 text-red-600" />
                          )}
                          <div>
                            <span className={`font-semibold text-lg ${
                              isSuspicious ? 'text-red-900' : 'text-gray-900'
                            }`}>
                              {obj.track_id != null && (
                              <span className="mr-1 px-1.5 py-0.5 bg-blue-100 text-blue-700 text-xs rounded font-mono">
                                #{obj.track_id}
                              </span>
                            )}
                            {obj.label || obj.class || 'Unknown'}
                            </span>
                            {isSuspicious && (
                              <span className="ml-2 px-2 py-0.5 bg-red-600 text-white text-xs rounded-full font-bold">
                                SUSPICIOUS
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="text-right">
                          <div className={`text-lg font-bold ${
                            isSuspicious ? 'text-red-700' : 'text-gray-700'
                          }`}>
                            {(obj.confidence * 100).toFixed(1)}%
                          </div>
                          <div className="text-xs text-gray-500">confidence</div>
                        </div>
                      </div>
                      {obj.bbox && (
                        <div className="mt-2 text-xs text-gray-600">
                          Position: [{obj.bbox.map(v => Math.round(v)).join(', ')}]
                        </div>
                      )}
                    </div>
                  )
                })}
                   

              </div>
            </div>
          )}

          {/* Controls */}
          <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-100">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Controls</h3>
            
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Camera Source
                </label>
                <select
                  value={cameraIndex}
                  onChange={(e) => setCameraIndex(parseInt(e.target.value))}
                  disabled={isMonitoring}
                  className="w-full px-4 py-2 border-2 border-gray-200 rounded-xl focus:border-primary-500 outline-none disabled:opacity-50"
                >
                  <option value={0}>Default Camera (0)</option>
                  <option value={1}>External Camera (1)</option>
                  <option value={2}>Camera 2</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Processing Speed
                </label>
                <select
                  value={frameSkip}
                  onChange={(e) => setFrameSkip(parseInt(e.target.value))}
                  className="w-full px-4 py-2 border-2 border-gray-200 rounded-xl focus:border-primary-500 outline-none"
                >
                  <option value={1}>Very Detailed (Slow)</option>
                  <option value={2}>Balanced (Recommended)</option>
                  <option value={5}>Fast</option>
                  <option value={10}>Very Fast</option>
                </select>
              </div>
            </div>

            <div className="flex space-x-3">
              <button
                onClick={startMonitoring}
                disabled={isMonitoring}
                className="flex-1 bg-gradient-to-r from-green-500 to-emerald-600 text-white py-3 rounded-xl font-semibold flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-lg transition-all"
              >
                <Play className="w-5 h-5 mr-2" />
                Start Monitoring
              </button>
              
              <button
                onClick={stopMonitoring}
                disabled={!isMonitoring}
                className="flex-1 bg-gradient-danger text-white py-3 rounded-xl font-semibold flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-lg transition-all"
              >
                <Square className="w-5 h-5 mr-2" />
                Stop
              </button>
            </div>

            {/* Assistant Call — opens the global Siri-style overlay */}
            <div className="mt-4 pt-4 border-t border-gray-100">
              <button
                onClick={() => {
                  try { window.dispatchEvent(new CustomEvent('visionguard:jarvis-open')) } catch {}
                }}
                className="w-full bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 text-white py-3 rounded-xl font-semibold flex items-center justify-center hover:shadow-lg hover:shadow-purple-500/30 transition-all gap-2"
              >
                <Mic className="w-5 h-5" />
                Talk to Jarvis
              </button>
              <p className="text-xs text-gray-500 mt-2 text-center">
                Or say <span className="font-semibold text-gray-700">"Hey Jarvis"</span> anytime
              </p>
            </div>
          </div>
        </div>

        {/* Real-time Metrics */}
        <div className="space-y-4">
          {result && isMonitoring && (
            <>
              {/* Risk Level */}
              <div className={`rounded-2xl p-6 shadow-lg text-white ${
                result.risk_assessment.risk_level === 'CRITICAL' ? 'bg-gradient-danger animate-pulse-slow' :
                result.risk_assessment.risk_level === 'HIGH' ? 'bg-gradient-to-r from-orange-500 to-red-500' :
                result.risk_assessment.risk_level === 'MEDIUM' ? 'bg-gradient-warning' :
                'bg-gradient-success'
              }`}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm opacity-90">Risk Level</span>
                  <Activity className="w-5 h-5" />
                </div>
                <p className="text-3xl font-bold">{result.risk_assessment.risk_level}</p>
                <p className="text-sm opacity-90 mt-1">
                  Score: {(result.risk_assessment.overall_score * 100).toFixed(1)}%
                </p>
              </div>

              {/* Threat Category */}
              <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-100">
                <h3 className="text-sm font-semibold text-gray-600 mb-2">Threat Type</h3>
                <p className="text-xl font-bold text-gray-900">
                  {result.risk_assessment.threat_category || 'NONE'}
                </p>
              </div>

              {/* Detection Stats */}
              <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-100">
                <h3 className="text-sm font-semibold text-gray-600 mb-4">Live Detection</h3>
                
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-700">Deepfake</span>
                    <span className={`px-3 py-1 rounded-full text-xs font-bold ${
                      result.deepfake.status === 'fake' ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'
                    }`}>
                      {result.deepfake.status.toUpperCase()}
                    </span>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-700">Identity</span>
                    <span className="text-sm font-semibold text-gray-900">
                      {result.face_recognition.identity}
                    </span>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-700">Objects</span>
                    <span className="text-sm font-semibold text-gray-900">
                      {result.objects.length}
                    </span>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-700">Suspicious</span>
                    <span className={`text-sm font-semibold ${
                      result.suspicious_objects.length > 0 ? 'text-red-600' : 'text-green-600'
                    }`}>
                      {result.suspicious_objects.length}
                    </span>
                  </div>

                  {result.tracking && result.tracking.tracks && (
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-700">Tracked IDs</span>
                      <span className="text-sm font-semibold text-blue-600">
                        {result.tracking.tracks.filter(t => t.missed === 0).length}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* Active Alerts */}
              {result.risk_assessment.threats && (
                <div className="space-y-2">
                  {result.risk_assessment.threats.has_weapon && (
                    <div className="bg-gradient-danger text-white p-4 rounded-xl">
                      <p className="font-bold text-sm">🚨 WEAPON DETECTED</p>
                      <p className="text-xs opacity-90 mt-1">
                        {result.risk_assessment.threats.weapons_detected?.join(', ')}
                      </p>
                    </div>
                  )}

                  {result.risk_assessment.threats.is_unknown_person && (
                    <div className="bg-gradient-warning text-gray-900 p-4 rounded-xl">
                      <p className="font-bold text-sm">⚠️ UNKNOWN PERSON</p>
                    </div>
                  )}

                  {result.risk_assessment.threats.has_mask && (
                    <div className="bg-blue-500 text-white p-4 rounded-xl">
                      <p className="font-bold text-sm">😷 MASK DETECTED</p>
                    </div>
                  )}
                </div>
              )}

              {/* Risk Reasons */}
              <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-100">
                <h3 className="text-sm font-semibold text-gray-600 mb-3">Reasons</h3>
                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {result.risk_assessment.reasons.map((reason, idx) => (
                    <div key={idx} className="flex items-start space-x-2">
                      <div className="w-2 h-2 bg-primary-500 rounded-full mt-1.5 flex-shrink-0"></div>
                      <p className="text-xs text-gray-700">{reason}</p>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {!isMonitoring && (
            <div className="bg-blue-50 rounded-2xl p-6 border border-blue-200">
              <AlertCircle className="w-8 h-8 text-blue-600 mb-3" />
              <h3 className="font-semibold text-blue-900 mb-2">Start Monitoring</h3>
              <p className="text-sm text-blue-800">
                Click "Start Monitoring" to begin real-time threat detection
              </p>
            </div>
          )}
        </div>
      </div>

    </div>
  )
}
