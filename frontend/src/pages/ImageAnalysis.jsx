import { useState, useCallback, useRef } from 'react'
import { motion } from 'framer-motion'
import { Upload, Camera, Loader, Image as ImageIcon, AlertCircle, Shield, Eye, Target, X, MessageCircle, Settings } from 'lucide-react'
import { useDropzone } from 'react-dropzone'
import Webcam from 'react-webcam'
import RiskBadge from '../components/RiskBadge'
import authService from '../services/authService'
import { Link } from 'react-router-dom'

export default function ImageAnalysis() {
  const [image, setImage] = useState(null)
  const [imagePreview, setImagePreview] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [showWebcam, setShowWebcam] = useState(false)
  const webcamRef = useRef(null)

  const onDrop = useCallback((acceptedFiles) => {
    const file = acceptedFiles[0]
    if (file) {
      setImage(file)
      setImagePreview(URL.createObjectURL(file))
      setResult(null)
      setError(null)
      setShowWebcam(false)
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/*': ['.png', '.jpg', '.jpeg'] },
    multiple: false,
  })

  const captureFromWebcam = useCallback(() => {
    const imageSrc = webcamRef.current.getScreenshot()
    if (imageSrc) {
      // Convert base64 to blob
      fetch(imageSrc)
        .then(res => res.blob())
        .then(blob => {
          const file = new File([blob], 'webcam-capture.jpg', { type: 'image/jpeg' })
          setImage(file)
          setImagePreview(imageSrc)
          setResult(null)
          setError(null)
          setShowWebcam(false)
        })
    }
  }, [])

  const analyzeImage = async () => {
    if (!image) return

    setAnalyzing(true)
    setError(null)

    const formData = new FormData()
    formData.append('file', image)
    // DON'T send return_annotated - let backend use its default (True)
    // Backend API default is already return_annotated=True

    try {
      const axios = authService.getAuthAxios()
      const response = await axios.post('/analyze/image', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      
      // DEBUG: Log what we received
      console.log('🔍 Backend Response:', {
        hasAnnotatedImage: !!response.data.annotated_image,
        annotatedImageLength: response.data.annotated_image?.length || 0,
        allKeys: Object.keys(response.data),
        riskLevel: response.data.risk_assessment?.risk_level
      })
      
      setResult(response.data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to analyze image. Make sure backend is running on port 8000')
      console.error('Analysis error:', err)
    } finally {
      setAnalyzing(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent mb-2">
          Image Analysis
        </h1>
        <p className="text-slate-400">Upload or capture an image for AI-powered security analysis</p>
      </motion.div>

      {/* Telegram Notification Reminder */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="bg-blue-900/20 border-l-4 border-blue-500 p-4 rounded-lg"
      >
        <div className="flex items-start gap-3">
          <MessageCircle className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-sm text-blue-200">
              <strong>💡 Tip:</strong> Enable Telegram notifications to receive instant alerts when unknown faces are detected in your images!
            </p>
            <Link
              to="/settings"
              className="inline-flex items-center gap-1 text-sm text-blue-400 hover:text-blue-300 font-medium mt-2"
            >
              <Settings className="w-4 h-4" />
              Configure in Settings →
            </Link>
          </div>
        </div>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Upload Section */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.1 }}
          className="space-y-6"
        >
          {/* Camera/Upload Toggle */}
          <div className="flex space-x-3">
            <button
              onClick={() => setShowWebcam(!showWebcam)}
              className={`flex-1 py-3 rounded-xl font-semibold transition-all flex items-center justify-center ${
                showWebcam
                  ? 'bg-blue-600 text-white shadow-lg'
                  : 'bg-slate-800/50 text-slate-300 hover:bg-slate-700/50'
              }`}
            >
              <Camera className="w-5 h-5 mr-2" />
              Live Camera
            </button>
            <button
              onClick={() => setShowWebcam(false)}
              className={`flex-1 py-3 rounded-xl font-semibold transition-all flex items-center justify-center ${
                !showWebcam
                  ? 'bg-blue-600 text-white shadow-lg'
                  : 'bg-slate-800/50 text-slate-300 hover:bg-slate-700/50'
              }`}
            >
              <Upload className="w-5 h-5 mr-2" />
              Upload File
            </button>
          </div>

          {/* Webcam Capture */}
          {showWebcam && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className="bg-[#060c18] rounded-2xl border border-slate-800/60 p-6"
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-white flex items-center">
                  <Camera className="w-5 h-5 mr-2" />
                  Live Camera Feed
                </h3>
                <button
                  onClick={() => setShowWebcam(false)}
                  className="p-2 hover:bg-slate-800/60 rounded-lg transition-colors"
                >
                  <X className="w-5 h-5 text-slate-400" />
                </button>
              </div>
              <div className="bg-black rounded-xl overflow-hidden mb-4">
                <Webcam
                  ref={webcamRef}
                  audio={false}
                  screenshotFormat="image/jpeg"
                  className="w-full"
                />
              </div>
              <button
                onClick={captureFromWebcam}
                className="w-full bg-gradient-to-r from-blue-500 to-purple-600 text-white py-3 rounded-xl font-semibold hover:shadow-lg transition-all flex items-center justify-center"
              >
                <Camera className="w-5 h-5 mr-2" />
                Capture Photo
              </button>
            </motion.div>
          )}

          {/* Dropzone */}
          {!showWebcam && (
            <div
              {...getRootProps()}
              className={`border-3 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all ${
                isDragActive
                  ? 'border-blue-500 bg-blue-900/20 scale-105'
                  : 'border-slate-700/50 hover:border-blue-500 hover:bg-slate-800/30'
              }`}
            >
              <input {...getInputProps()} />
              <Upload className="w-16 h-16 text-slate-500 mx-auto mb-4" />
              <p className="text-lg font-semibold text-slate-300 mb-2">
                {isDragActive ? 'Drop image here' : 'Drag & drop image'}
              </p>
              <p className="text-sm text-slate-400">or click to browse</p>
              <p className="text-xs text-slate-500 mt-2">Supports: JPG, PNG (Max 10MB)</p>
            </div>
          )}

          {/* Image Preview */}
          {imagePreview && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className="bg-[#060c18] rounded-2xl border border-slate-800/60 p-6"
            >
              <h3 className="text-lg font-semibold text-white mb-4 flex items-center">
                <ImageIcon className="w-5 h-5 mr-2" />
                Original Image
              </h3>
              <img
                src={imagePreview}
                alt="Preview"
                className="w-full rounded-xl shadow-md"
              />
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={analyzeImage}
                disabled={analyzing}
                className="w-full mt-4 bg-blue-600 hover:bg-blue-500 text-white py-4 rounded-xl font-semibold text-lg shadow-lg hover:shadow-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
              >
                {analyzing ? (
                  <>
                    <Loader className="w-5 h-5 mr-2 animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  'Analyze Image'
                )}
              </motion.button>
            </motion.div>
          )}
        </motion.div>

        {/* Results Section */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2 }}
          className="space-y-6"
        >
          {error && (
            <div className="bg-red-900/20 border border-red-500/30 rounded-2xl p-6">
              <div className="flex items-start space-x-3">
                <AlertCircle className="w-6 h-6 text-red-400 flex-shrink-0" />
                <div>
                  <h3 className="text-red-300 font-semibold mb-1">Analysis Failed</h3>
                  <p className="text-red-400 text-sm">{error}</p>
                </div>
              </div>
            </div>
          )}

          {result && (
            <>
              <RiskBadge
                level={result.risk_assessment.risk_level}
                score={result.risk_assessment.overall_score}
              />

              {/* Visual Analysis Section */}
              {result.annotated_image ? (
                <div className="bg-[#060c18] rounded-2xl border-4 border-blue-500 p-4">
                  <h3 className="text-md font-bold text-blue-300 mb-3 flex items-center">
                    <Target className="w-5 h-5 mr-2 text-blue-400" />
                    AI Analysis — Detections Highlighted
                  </h3>
                  <img
                    src={`data:image/jpeg;base64,${result.annotated_image}`}
                    alt="AI Detections"
                    className="w-full rounded-xl shadow-lg border-2 border-blue-300"
                  />
                  <div className="mt-3 p-3 bg-blue-900/20 rounded-lg border border-blue-500/30">
                    <p className="text-xs font-bold text-white mb-2">Detection Legend:</p>
                    <div className="grid grid-cols-2 gap-2 text-xs text-slate-200">
                      <div>⭕ <span className="text-yellow-400 font-semibold">Yellow:</span> Known</div>
                      <div>⭕ <span className="text-purple-400 font-semibold">Magenta:</span> Unknown ⚠️</div>
                      <div>🔲 <span className="text-green-400 font-semibold">Green:</span> Normal</div>
                      <div>🔲 <span className="text-red-400 font-semibold">Red:</span> Weapon 🚨</div>
                    </div>
                  </div>
                </div>
              ) : null}

              {/* Threat Category */}
              <div className="bg-[#060c18] rounded-2xl border border-slate-800/60 p-6">
                <h3 className="text-lg font-semibold text-white mb-3">Threat Classification</h3>
                <div className="bg-purple-900/30 rounded-xl p-4">
                  <p className="text-2xl font-bold text-purple-200">
                    {result.risk_assessment.threat_category}
                  </p>
                </div>
              </div>

              {/* Threat Alerts */}
              {result.risk_assessment.threats && (
                <div className="space-y-3">
                  {result.risk_assessment.threats.has_weapon && (
                    <div className="bg-gradient-danger text-white p-4 rounded-xl shadow-lg">
                      <div className="flex items-center space-x-3">
                        <Shield className="w-6 h-6" />
                        <div>
                          <p className="font-bold">WEAPON DETECTED</p>
                          <p className="text-sm opacity-90">
                            {result.risk_assessment.threats.weapons_detected?.join(', ')}
                          </p>
                        </div>
                      </div>
                    </div>
                  )}
                  
                  {result.risk_assessment.threats.is_deepfake && (
                    <div className="bg-gradient-danger text-white p-4 rounded-xl shadow-lg">
                      <div className="flex items-center space-x-3">
                        <Eye className="w-6 h-6" />
                        <div>
                          <p className="font-bold">DEEPFAKE DETECTED</p>
                          <p className="text-sm opacity-90">Manipulated or synthetic image</p>
                        </div>
                      </div>
                    </div>
                  )}

                  {result.risk_assessment.threats.is_unknown_person && (
                    <div className="bg-gradient-warning text-white p-4 rounded-xl shadow-lg">
                      <div className="flex items-center space-x-3">
                        <Target className="w-6 h-6" />
                        <div>
                          <p className="font-bold">UNKNOWN PERSON</p>
                          <p className="text-sm opacity-90">Individual not in database</p>
                        </div>
                      </div>
                    </div>
                  )}

                  {result.risk_assessment.threats.has_mask && (
                    <div className="bg-gradient-warning text-white p-4 rounded-xl shadow-lg">
                      <div className="flex items-center space-x-3">
                        <Shield className="w-6 h-6" />
                        <div>
                          <p className="font-bold">MASK DETECTED</p>
                          <p className="text-sm opacity-90">Person wearing face covering</p>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Detection Results */}
              <div className="bg-[#060c18] rounded-2xl border border-slate-800/60 p-6">
                <h3 className="text-lg font-semibold text-white mb-4">Detection Results</h3>
                
                <div className="grid grid-cols-3 gap-4">
                  <div className="text-center p-4 bg-blue-900/30 rounded-xl">
                    <p className="text-3xl font-bold text-blue-300">
                      {result.deepfake.status === 'fake' ? '❌' : '✅'}
                    </p>
                    <p className="text-sm text-slate-400 mt-2">Deepfake Status</p>
                    <p className="text-xs text-slate-500 mt-1">{result.deepfake.status.toUpperCase()}</p>
                    <p className="text-xs text-slate-500">{(result.deepfake.confidence * 100).toFixed(1)}% confidence</p>
                  </div>
                  
                  <div className="text-center p-4 bg-purple-900/30 rounded-xl">
                    <p className="text-3xl font-bold text-purple-300">👤</p>
                    <p className="text-sm text-slate-400 mt-2">Identity</p>
                    <p className="text-xs font-semibold text-slate-300 mt-1">{result.face_recognition.identity}</p>
                    <p className="text-xs text-slate-500">{(result.face_recognition.confidence * 100).toFixed(1)}% match</p>
                    <p className="text-xs text-slate-500 mt-1">{result.face_recognition.num_faces} face(s)</p>
                  </div>
                  
                  <div className="text-center p-4 bg-pink-900/30 rounded-xl">
                    <p className="text-3xl font-bold text-pink-300">{result.objects.length}</p>
                    <p className="text-sm text-slate-400 mt-2">Objects Detected</p>
                    <p className="text-xs text-slate-500 mt-1">{result.suspicious_objects.length} suspicious</p>
                    {result.suspicious_objects.length > 0 && (
                      <p className="text-xs font-semibold text-red-600 mt-1">
                        {result.suspicious_objects.slice(0, 2).join(', ')}
                      </p>
                    )}
                  </div>
                </div>
              </div>

              {/* Detected Objects List */}
              {result.objects.length > 0 && (
                <div className="bg-[#060c18] rounded-2xl border border-slate-800/60 p-6">
                  <h3 className="text-lg font-semibold text-white mb-4">Detected Objects</h3>
                  <div className="space-y-2 max-h-60 overflow-y-auto">
                    {result.objects.map((obj, idx) => (
                      <div key={idx} className="flex items-center justify-between p-3 bg-slate-800/30 rounded-lg hover:bg-slate-800/60 transition-colors">
                        <div className="flex items-center space-x-3">
                          <div className={`w-3 h-3 rounded-full ${
                            result.suspicious_objects.includes(obj.label) ? 'bg-red-500' : 'bg-green-500'
                          }`}></div>
                          <span className="font-medium text-white">{obj.label}</span>
                        </div>
                        <span className="text-sm text-slate-400">{(obj.confidence * 100).toFixed(1)}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Risk Reasons */}
              <div className="bg-[#060c18] rounded-2xl border border-slate-800/60 p-6">
                <h3 className="text-lg font-semibold text-white mb-4">Risk Assessment</h3>
                <div className="space-y-2">
                  {result.risk_assessment.reasons.map((reason, idx) => (
                    <div key={idx} className="flex items-start space-x-2 p-3 bg-slate-800/30 rounded-lg">
                      <div className="w-2 h-2 bg-blue-500 rounded-full mt-1.5 flex-shrink-0"></div>
                      <p className="text-sm text-slate-300">{reason}</p>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </motion.div>
      </div>
    </div>
  )
}
