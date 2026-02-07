import { useState, useCallback } from 'react'
import { motion } from 'framer-motion'
import { Video, Upload, Loader, AlertCircle, BarChart3, Clock } from 'lucide-react'
import { useDropzone } from 'react-dropzone'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import axios from 'axios'
import RiskBadge from '../components/RiskBadge'

export default function VideoAnalysis() {
  const [video, setVideo] = useState(null)
  const [videoPreview, setVideoPreview] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)
  const [frameSkip, setFrameSkip] = useState(5)

  const onDrop = useCallback((acceptedFiles) => {
    const file = acceptedFiles[0]
    if (file) {
      setVideo(file)
      setVideoPreview(URL.createObjectURL(file))
      setResults(null)
      setError(null)
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'video/*': ['.mp4', '.avi', '.mov'] },
    multiple: false,
  })

  const analyzeVideo = async () => {
    if (!video) return

    setAnalyzing(true)
    setError(null)

    const formData = new FormData()
    formData.append('file', video)
    formData.append('frame_skip', frameSkip.toString())

    try {
      const response = await axios.post('http://localhost:8000/analyze/video', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setResults(response.data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to analyze video. Make sure backend is running')
      console.error('Analysis error:', err)
    } finally {
      setAnalyzing(false)
    }
  }

  // Prepare chart data
  const chartData = results?.results?.map((r, idx) => ({
    frame: r.frame_number || idx,
    riskScore: r.risk_assessment.overall_score * 100,
    level: r.risk_assessment.risk_level
  })) || []

  // Calculate statistics
  const stats = results ? {
    totalFrames: results.num_frames_processed,
    highRisk: results.results.filter(r => ['HIGH', 'CRITICAL'].includes(r.risk_assessment.risk_level)).length,
    deepfakes: results.results.filter(r => r.deepfake.status === 'fake').length,
    avgRisk: (results.results.reduce((sum, r) => sum + r.risk_assessment.overall_score, 0) / results.results.length * 100).toFixed(1)
  } : null

  return (
    <div className="space-y-6">
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1 className="text-4xl font-bold bg-gradient-primary bg-clip-text text-transparent mb-2">
          Video Analysis
        </h1>
        <p className="text-gray-600">Upload videos for frame-by-frame security analysis</p>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Upload Section */}
        <div className="space-y-6">
          <div
            {...getRootProps()}
            className={`border-3 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all ${
              isDragActive
                ? 'border-primary-500 bg-primary-50 scale-105'
                : 'border-gray-300 hover:border-primary-400 hover:bg-gray-50'
            }`}
          >
            <input {...getInputProps()} />
            <Video className="w-16 h-16 text-gray-400 mx-auto mb-4" />
            <p className="text-lg font-semibold text-gray-700 mb-2">
              {isDragActive ? 'Drop video here' : 'Drag & drop video'}
            </p>
            <p className="text-sm text-gray-500">or click to browse</p>
            <p className="text-xs text-gray-400 mt-2">Supports: MP4, AVI, MOV</p>
          </div>

          {videoPreview && (
            <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-100">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Video Preview</h3>
              <video src={videoPreview} controls className="w-full rounded-xl shadow-md mb-4" />
              
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Frame Skip (process every {frameSkip} frames)
                </label>
                <input
                  type="range"
                  min="1"
                  max="30"
                  value={frameSkip}
                  onChange={(e) => setFrameSkip(parseInt(e.target.value))}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-gray-500 mt-1">
                  <span>Detailed (1)</span>
                  <span>Fast (30)</span>
                </div>
              </div>

              <button
                onClick={analyzeVideo}
                disabled={analyzing}
                className="w-full bg-gradient-primary text-white py-4 rounded-xl font-semibold text-lg shadow-lg hover:shadow-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
              >
                {analyzing ? (
                  <>
                    <Loader className="w-5 h-5 mr-2 animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    <BarChart3 className="w-5 h-5 mr-2" />
                    Analyze Video
                  </>
                )}
              </button>
            </div>
          )}
        </div>

        {/* Results Section */}
        <div className="space-y-6">
          {error && (
            <div className="bg-red-50 border-2 border-red-200 rounded-2xl p-6">
              <div className="flex items-start space-x-3">
                <AlertCircle className="w-6 h-6 text-red-600 flex-shrink-0" />
                <div>
                  <h3 className="text-red-900 font-semibold mb-1">Analysis Failed</h3>
                  <p className="text-red-700 text-sm">{error}</p>
                </div>
              </div>
            </div>
          )}

          {stats && (
            <>
              {/* Statistics */}
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-white rounded-2xl shadow-lg p-6 text-center border border-gray-100">
                  <Clock className="w-8 h-8 text-blue-600 mx-auto mb-2" />
                  <p className="text-3xl font-bold text-gray-900">{stats.totalFrames}</p>
                  <p className="text-sm text-gray-600 mt-1">Frames Processed</p>
                </div>
                
                <div className="bg-white rounded-2xl shadow-lg p-6 text-center border border-gray-100">
                  <AlertCircle className="w-8 h-8 text-red-600 mx-auto mb-2" />
                  <p className="text-3xl font-bold text-red-600">{stats.highRisk}</p>
                  <p className="text-sm text-gray-600 mt-1">High Risk Frames</p>
                </div>
                
                <div className="bg-white rounded-2xl shadow-lg p-6 text-center border border-gray-100">
                  <Video className="w-8 h-8 text-purple-600 mx-auto mb-2" />
                  <p className="text-3xl font-bold text-purple-600">{stats.deepfakes}</p>
                  <p className="text-sm text-gray-600 mt-1">Deepfake Frames</p>
                </div>
                
                <div className="bg-white rounded-2xl shadow-lg p-6 text-center border border-gray-100">
                  <BarChart3 className="w-8 h-8 text-green-600 mx-auto mb-2" />
                  <p className="text-3xl font-bold text-gray-900">{stats.avgRisk}%</p>
                  <p className="text-sm text-gray-600 mt-1">Avg Risk Score</p>
                </div>
              </div>

              {/* Risk Timeline Chart */}
              <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-100">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Risk Timeline</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="frame" label={{ value: 'Frame', position: 'insideBottom', offset: -5 }} />
                    <YAxis label={{ value: 'Risk %', angle: -90, position: 'insideLeft' }} />
                    <Tooltip />
                    <Line type="monotone" dataKey="riskScore" stroke="#667eea" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* Frame Results */}
              <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-100 max-h-96 overflow-y-auto">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Frame Analysis</h3>
                <div className="space-y-3">
                  {results.results.filter(r => ['HIGH', 'CRITICAL'].includes(r.risk_assessment.risk_level)).map((result, idx) => (
                    <div key={idx} className="p-4 bg-gradient-to-r from-red-50 to-pink-50 rounded-xl border-l-4 border-red-500">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-bold text-gray-900">Frame #{result.frame_number || idx}</span>
                        <span className={`px-3 py-1 rounded-full text-xs font-bold ${
                          result.risk_assessment.risk_level === 'CRITICAL' ? 'bg-red-600 text-white' : 'bg-orange-500 text-white'
                        }`}>
                          {result.risk_assessment.risk_level}
                        </span>
                      </div>
                      <p className="text-sm text-gray-700">{result.summary}</p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {result.risk_assessment.reasons.map((reason, ridx) => (
                          <span key={ridx} className="text-xs bg-white px-2 py-1 rounded-full text-gray-700">
                            {reason}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
