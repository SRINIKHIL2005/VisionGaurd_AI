import { useState, useCallback, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Video, Upload, Loader, AlertCircle, BarChart3, Clock, Settings2, X, ChevronLeft, ChevronRight, Eye, Image as ImageIcon } from 'lucide-react'
import { useDropzone } from 'react-dropzone'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import RiskBadge from '../components/RiskBadge'
import AdvancedAnalyticsDisplay from '../components/AdvancedAnalyticsDisplay'
import authService from '../services/authService'

export default function VideoAnalysis() {
  const [video, setVideo] = useState(null)
  const [videoPreview, setVideoPreview] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)
  const [frameSkip, setFrameSkip] = useState(5)
  const [generateReport, setGenerateReport] = useState(false)
  const [selectedFrame, setSelectedFrame] = useState(null)
  const [showFrameViewer, setShowFrameViewer] = useState(false)

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
    formData.append('generate_report', generateReport.toString())

    try {
      const axios = authService.getAuthAxios()
      const response = await axios.post('/analyze/video', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      console.log('Full API Response:', response.data)
      console.log('Advanced Analytics:', response.data.advanced_analytics)
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

  // Frame viewer handlers
  const openFrameViewer = (frame) => {
    setSelectedFrame(frame)
    setShowFrameViewer(true)
  }

  const closeFrameViewer = () => {
    setShowFrameViewer(false)
    setTimeout(() => setSelectedFrame(null), 300)
  }

  const navigateFrame = (direction) => {
    if (!selectedFrame || !results) return
    const highRiskFrames = results.results.filter(r => ['HIGH', 'CRITICAL'].includes(r.risk_assessment.risk_level))
    const currentIdx = highRiskFrames.findIndex(f => f.frame_number === selectedFrame.frame_number)
    
    if (direction === 'next' && currentIdx < highRiskFrames.length - 1) {
      setSelectedFrame(highRiskFrames[currentIdx + 1])
    } else if (direction === 'prev' && currentIdx > 0) {
      setSelectedFrame(highRiskFrames[currentIdx - 1])
    }
  }

  // Keyboard shortcuts for frame viewer
  useEffect(() => {
    const handleKeyPress = (e) => {
      if (!showFrameViewer) return

      if (e.key === 'Escape') {
        closeFrameViewer()
      } else if (e.key === 'ArrowLeft') {
        navigateFrame('prev')
      } else if (e.key === 'ArrowRight') {
        navigateFrame('next')
      }
    }

    window.addEventListener('keydown', handleKeyPress)
    return () => window.removeEventListener('keydown', handleKeyPress)
  }, [showFrameViewer, selectedFrame])

  return (
    <div className="space-y-6">
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent mb-2">
          Video Analysis
        </h1>
        <p className="text-slate-400">Upload videos for frame-by-frame security analysis</p>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Upload Section */}
        <div className="space-y-6">
          <div
            {...getRootProps()}
            className={`border-3 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all ${
              isDragActive
                ? 'border-blue-500 bg-blue-900/20 scale-105'
                : 'border-slate-700/50 hover:border-blue-500 hover:bg-slate-800/30'
          }`}
          >
            <input {...getInputProps()} />
            <Video className="w-16 h-16 text-slate-500 mx-auto mb-4" />
            <p className="text-lg font-semibold text-slate-300 mb-2">
              {isDragActive ? 'Drop video here' : 'Drag & drop video'}
            </p>
            <p className="text-sm text-slate-400">or click to browse</p>
            <p className="text-xs text-slate-500 mt-2">Supports: MP4, AVI, MOV</p>
          </div>

          {videoPreview && (
            <div className="bg-[#060c18] rounded-2xl border border-slate-800/60 p-4">
              <h3 className="text-lg font-semibold text-white mb-3">Video Preview</h3>
              <video src={videoPreview} controls className="w-full rounded-xl shadow-md mb-3" />
              
              <div className="mb-3">
                <label className="block text-sm font-medium text-slate-300 mb-2">
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
                <div className="flex justify-between text-xs text-slate-500 mt-1">
                  <span>Detailed (1)</span>
                  <span>Fast (30)</span>
                </div>
              </div>

              <div className="flex items-center space-x-3 mb-3 bg-slate-900/40 p-3 rounded-lg border border-slate-800/60">
                <input
                  type="checkbox"
                  id="generateReport"
                  checked={generateReport}
                  disabled={analyzing}
                  onChange={(e) => setGenerateReport(e.target.checked)}
                  className="w-4 h-4 rounded accent-blue-600 cursor-pointer disabled:cursor-not-allowed"
                />
                <label htmlFor="generateReport" className="text-sm text-slate-300 cursor-pointer disabled:cursor-not-allowed flex items-center space-x-2">
                  <Settings2 className="w-4 h-4" />
                  <span>Generate detailed analysis reports</span>
                </label>
              </div>

              <button
                onClick={analyzeVideo}
                disabled={analyzing}
                className="w-full bg-blue-600 hover:bg-blue-500 text-white py-3 rounded-xl font-semibold text-lg shadow-lg hover:shadow-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
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

              {/* Advanced Analytics (Moved to right corner) */}
              {results && results.advanced_analytics && (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="mb-4"
                >
                  <AdvancedAnalyticsDisplay
                    analytics={results.advanced_analytics}
                    reports={{
                      timeline_chart: results.timeline_chart,
                      statistics_chart: results.statistics_chart,
                      json_report: results.json_report,
                    }}
                  />
                </motion.div>
              )}
            </div>
          )}
        </div>

        {/* Results Section */}
        <div className="space-y-4">
          {error && (
            <div className="bg-red-900/20 border border-red-500/30 rounded-2xl p-4">
              <div className="flex items-start space-x-3">
                <AlertCircle className="w-6 h-6 text-red-400 flex-shrink-0" />
                <div>
                  <h3 className="text-red-300 font-semibold mb-1">Analysis Failed</h3>
                  <p className="text-red-400 text-sm">{error}</p>
                </div>
              </div>
            </div>
          )}

          {stats && (
            <>
              {/* Statistics */}
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-[#060c18] rounded-2xl border border-slate-800/60 p-4 text-center">
                  <Clock className="w-7 h-7 text-blue-400 mx-auto mb-2" />
                  <p className="text-2xl font-bold text-white">{stats.totalFrames}</p>
                  <p className="text-xs text-slate-400 mt-1">Frames Processed</p>
                </div>
                
                <div className="bg-[#060c18] rounded-2xl border border-slate-800/60 p-4 text-center">
                  <AlertCircle className="w-7 h-7 text-red-500 mx-auto mb-2" />
                  <p className="text-2xl font-bold text-red-400">{stats.highRisk}</p>
                  <p className="text-xs text-slate-400 mt-1">High Risk Frames</p>
                </div>
                
                <div className="bg-[#060c18] rounded-2xl border border-slate-800/60 p-4 text-center">
                  <Video className="w-7 h-7 text-purple-400 mx-auto mb-2" />
                  <p className="text-2xl font-bold text-purple-400">{stats.deepfakes}</p>
                  <p className="text-xs text-slate-400 mt-1">Deepfake Frames</p>
                </div>
                
                <div className="bg-[#060c18] rounded-2xl border border-slate-800/60 p-4 text-center">
                  <BarChart3 className="w-7 h-7 text-green-400 mx-auto mb-2" />
                  <p className="text-2xl font-bold text-white">{stats.avgRisk}%</p>
                  <p className="text-xs text-slate-400 mt-1">Avg Risk Score</p>
                </div>
              </div>

              {/* Risk Timeline Chart - Interactive */}
              <div className="bg-[#060c18] rounded-2xl border border-slate-800/60 p-4">
                <h3 className="text-lg font-semibold text-white mb-2">📊 Risk Timeline (Click Frame to Preview)</h3>
                <p className="text-xs text-slate-400 mb-3">Click any point on the graph to see the analyzed frame</p>
                <ResponsiveContainer width="100%" height={280}>
                  <LineChart data={chartData} onClick={(state) => {
                    if (state?.activeTooltipIndex !== undefined) {
                      const frameData = chartData[state.activeTooltipIndex]
                      const frameResult = results.results.find(r => r.frame_number === frameData.frame)
                      if (frameResult) setSelectedFrame(frameResult)
                    }
                  }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey="frame" label={{ value: 'Frame', position: 'insideBottom', offset: -5 }} stroke="#9ca3af" />
                    <YAxis label={{ value: 'Risk %', angle: -90, position: 'insideLeft' }} stroke="#9ca3af" />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #4b5563', borderRadius: '8px' }}
                      cursor={{ strokeDasharray: '3 3' }}
                    />
                    <Line type="monotone" dataKey="riskScore" stroke="#667eea" strokeWidth={2} dot={{ fill: '#667eea', r: 4 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* Frame Preview from Timeline */}
              {selectedFrame && !showFrameViewer && (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="bg-[#060c18] rounded-2xl border border-slate-800/60 p-4"
                >
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-lg font-semibold text-white">👁️ Frame Preview</h3>
                    <button
                      onClick={() => setSelectedFrame(null)}
                      className="text-slate-400 hover:text-white transition-colors"
                    >
                      <X className="w-5 h-5" />
                    </button>
                  </div>
                  
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                    {/* Frame Image */}
                    {selectedFrame.annotated_image && (
                      <div className="lg:col-span-2">
                        <img
                          src={`data:image/png;base64,${selectedFrame.annotated_image}`}
                          alt={`Frame ${selectedFrame.frame_number}`}
                          className="w-full h-auto rounded-xl border border-slate-700"
                        />
                      </div>
                    )}

                    {/* Frame Details */}
                    <div className="space-y-3">
                      <div className="bg-slate-900/50 rounded-lg p-3">
                        <p className="text-xs text-slate-400">Frame</p>
                        <p className="text-2xl font-bold text-white">#{selectedFrame.frame_number}</p>
                      </div>

                      <div className="bg-slate-900/50 rounded-lg p-3">
                        <p className="text-xs text-slate-400">Risk Level</p>
                        <p className={`text-xl font-bold ${selectedFrame.risk_assessment.risk_level === 'CRITICAL' ? 'text-red-400' : 'text-orange-400'}`}>
                          {selectedFrame.risk_assessment.risk_level}
                        </p>
                      </div>

                      <div className="bg-slate-900/50 rounded-lg p-3">
                        <p className="text-xs text-slate-400">Risk Score</p>
                        <p className="text-2xl font-bold text-white">{(selectedFrame.risk_assessment.overall_score * 100).toFixed(1)}%</p>
                        <div className="w-full bg-slate-700 rounded-full h-2 mt-2">
                          <div
                            className="bg-gradient-to-r from-red-500 to-orange-500 h-2 rounded-full"
                            style={{ width: `${selectedFrame.risk_assessment.overall_score * 100}%` }}
                          />
                        </div>
                      </div>

                      {selectedFrame.deepfake && (
                        <div className="bg-slate-900/50 rounded-lg p-3">
                          <p className="text-xs text-slate-400">Deepfake</p>
                          <p className={`font-bold ${selectedFrame.deepfake.status === 'fake' ? 'text-red-400' : 'text-green-400'}`}>
                            {selectedFrame.deepfake.status.toUpperCase()}
                          </p>
                        </div>
                      )}

                      <button
                        onClick={() => openFrameViewer(selectedFrame)}
                        className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-semibold transition-colors"
                      >
                        Full Details
                      </button>
                    </div>
                  </div>

                  {selectedFrame.risk_assessment.reasons && selectedFrame.risk_assessment.reasons.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-slate-700">
                      <p className="text-sm font-semibold text-white mb-2">🚩 Risk Factors:</p>
                      <div className="flex flex-wrap gap-1">
                        {selectedFrame.risk_assessment.reasons.map((reason, idx) => (
                          <span
                            key={idx}
                            className="inline-block bg-red-900/40 border border-red-500/50 text-red-300 px-3 py-1 rounded-full text-xs"
                          >
                            {reason}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </motion.div>
              )}

              {/* Heatmap Display */}
              {results.advanced_analytics?.heatmap_data && (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.1 }}
                  className="bg-[#060c18] rounded-2xl border border-slate-800/60 p-4"
                >
                  <h3 className="text-lg font-semibold text-white mb-3 flex items-center space-x-2">
                    <ImageIcon className="w-5 h-5 text-orange-400" />
                    <span>Activity Heatmap</span>
                  </h3>
                  <div className="bg-slate-900/30 rounded-xl p-4">
                    <p className="text-slate-400 text-sm mb-3">
                      Spatial activity map across the video (people-first, with motion fallback when no people are detected) ({results.advanced_analytics.heatmap_data.length}x{results.advanced_analytics.heatmap_data[0]?.length || 'N/A'} grid)
                    </p>
                    {/* Heatmap Grid Visualization */}
                    <div className="w-full overflow-auto">
                      <div className="inline-block">
                        {(() => {
                          const maxValue = Math.max(...results.advanced_analytics.heatmap_data.flat());
                          return results.advanced_analytics.heatmap_data.map((row, rowIdx) => (
                          <div key={rowIdx} className="flex">
                            {row.map((value, colIdx) => {
                              // Normalize value to 0-1 range for color mapping
                              const normalized = maxValue > 0 ? value / maxValue : 0;
                              
                              // Color gradient: blue (cool) -> green -> yellow -> red (hot)
                              let bgColor = 'bg-blue-900';
                              if (normalized > 0.75) bgColor = 'bg-red-600';
                              else if (normalized > 0.5) bgColor = 'bg-yellow-500';
                              else if (normalized > 0.25) bgColor = 'bg-green-600';
                              else if (normalized > 0) bgColor = 'bg-blue-500';
                              
                              return (
                                <div
                                  key={`${rowIdx}-${colIdx}`}
                                  className={`w-6 h-6 ${bgColor} border border-slate-700/20`}
                                  title={`Grid [${rowIdx},${colIdx}]: intensity ${Number(value).toFixed(3)}`}
                                />
                              );
                            })}
                          </div>
                          ));
                        })()}
                      </div>
                    </div>
                    {/* Legend */}
                    <div className="mt-4 flex items-center justify-center gap-4 text-xs text-slate-400">
                      <div className="flex items-center gap-2">
                        <div className="w-4 h-4 bg-blue-900"></div>
                        <span>Low</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-4 h-4 bg-green-600"></div>
                        <span>Medium</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-4 h-4 bg-yellow-500"></div>
                        <span>High</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-4 h-4 bg-red-600"></div>
                        <span>Very High</span>
                      </div>
                    </div>
                  </div>
                </motion.div>
              )}

              {/* Frame-by-Frame Scrollable Preview */}
              {results.results && results.results.length > 0 && (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="bg-[#060c18] rounded-2xl border border-slate-800/60 p-4"
                >
                  <h3 className="text-lg font-semibold text-white mb-3">📹 Frame-by-Frame Analysis</h3>
                  <div className="overflow-x-auto pb-3">
                    <div className="flex gap-3">
                      {results.results.map((frame, idx) => (
                        <motion.div
                          key={idx}
                          whileHover={{ scale: 1.05 }}
                          onClick={() => setSelectedFrame(frame)}
                          className={`flex-shrink-0 cursor-pointer rounded-lg overflow-hidden border-2 transition-all ${
                            selectedFrame?.frame_number === frame.frame_number 
                              ? 'border-blue-400' 
                              : 'border-slate-700 hover:border-slate-600'
                          }`}
                        >
                          {frame.annotated_image ? (
                            <img
                              src={`data:image/png;base64,${frame.annotated_image}`}
                              alt={`Frame ${frame.frame_number}`}
                              className="w-20 h-20 object-cover"
                            />
                          ) : (
                            <div className="w-20 h-20 bg-slate-800 flex items-center justify-center">
                              <span className="text-xs text-slate-500">No img</span>
                            </div>
                          )}
                          <div className="bg-slate-900/80 px-2 py-1 text-center">
                            <p className="text-xs font-semibold text-white">#{frame.frame_number}</p>
                            <p className={`text-xs font-bold ${
                              frame.risk_assessment.risk_level === 'CRITICAL' ? 'text-red-400' :
                              frame.risk_assessment.risk_level === 'HIGH' ? 'text-orange-400' : 'text-yellow-400'
                            }`}>
                              {frame.risk_assessment.risk_level}
                            </p>
                          </div>
                        </motion.div>
                      ))}
                    </div>
                  </div>
                </motion.div>
              )}
            </>
          )}

          {/* Frame Viewer Modal */}
          <AnimatePresence>
            {showFrameViewer && selectedFrame && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
                onClick={closeFrameViewer}
              >
                <motion.div
                  initial={{ scale: 0.8, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  exit={{ scale: 0.8, opacity: 0 }}
                  className="bg-[#060c18] border border-slate-700 rounded-2xl p-6 max-w-4xl w-full max-h-[90vh] overflow-y-auto"
                  onClick={(e) => e.stopPropagation()}
                >
                  {/* Header */}
                  <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center space-x-3">
                      <h2 className="text-2xl font-bold text-white">Frame #{selectedFrame.frame_number}</h2>
                      <span className={`px-4 py-2 rounded-full font-bold ${
                        selectedFrame.risk_assessment.risk_level === 'CRITICAL' 
                          ? 'bg-red-600 text-white' 
                          : 'bg-orange-500 text-white'
                      }`}>
                        {selectedFrame.risk_assessment.risk_level} RISK
                      </span>
                    </div>
                    <button
                      onClick={closeFrameViewer}
                      className="p-2 hover:bg-slate-800 rounded-lg transition-colors"
                    >
                      <X className="w-6 h-6 text-slate-400" />
                    </button>
                  </div>

                  {/* Frame Image */}
                  {selectedFrame.annotated_image && (
                    <div className="mb-6 rounded-xl overflow-hidden bg-black/40">
                      <img
                        src={`data:image/png;base64,${selectedFrame.annotated_image}`}
                        alt={`Frame ${selectedFrame.frame_number}`}
                        className="w-full h-auto object-cover"
                      />
                    </div>
                  )}

                  {/* Frame Details */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                    {/* Summary */}
                    <div className="bg-slate-900/50 rounded-xl p-4">
                      <h3 className="text-lg font-semibold text-white mb-3">📋 Summary</h3>
                      <p className="text-sm text-slate-300">{selectedFrame.summary}</p>
                    </div>

                    {/* Risk Score */}
                    <div className="bg-slate-900/50 rounded-xl p-4">
                      <h3 className="text-lg font-semibold text-white mb-3">⚠️ Risk Score</h3>
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-slate-400">Overall Score:</span>
                          <span className="font-bold text-white">{(selectedFrame.risk_assessment.overall_score * 100).toFixed(1)}%</span>
                        </div>
                        <div className="w-full bg-slate-700 rounded-full h-2">
                          <div
                            className="bg-gradient-to-r from-red-500 to-orange-500 h-2 rounded-full"
                            style={{ width: `${selectedFrame.risk_assessment.overall_score * 100}%` }}
                          />
                        </div>
                      </div>
                    </div>

                    {/* Deepfake Analysis */}
                    {selectedFrame.deepfake && (
                      <div className="bg-slate-900/50 rounded-xl p-4">
                        <h3 className="text-lg font-semibold text-white mb-3">🤖 Deepfake Detection</h3>
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="text-slate-400">Status:</span>
                            <span className={selectedFrame.deepfake.status === 'fake' ? 'text-red-400 font-bold' : 'text-green-400 font-bold'}>
                              {selectedFrame.deepfake.status.toUpperCase()}
                            </span>
                          </div>
                          {selectedFrame.deepfake.fake_probability !== undefined && (
                            <div className="flex items-center justify-between">
                              <span className="text-slate-400">Fake Probability:</span>
                              <span className="font-bold">{(selectedFrame.deepfake.fake_probability * 100).toFixed(2)}%</span>
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Objects Detected */}
                    {selectedFrame.objects && selectedFrame.objects.length > 0 && (
                      <div className="bg-slate-900/50 rounded-xl p-4">
                        <h3 className="text-lg font-semibold text-white mb-3">🎯 Objects Detected</h3>
                        <div className="space-y-2">
                          {selectedFrame.objects.slice(0, 5).map((obj, idx) => (
                            <div key={idx} className="flex items-center justify-between text-sm">
                              <span className="text-slate-400">{obj.class}</span>
                              <span className="font-bold text-blue-400">{(obj.confidence * 100).toFixed(1)}%</span>
                            </div>
                          ))}
                          {selectedFrame.objects.length > 5 && (
                            <p className="text-xs text-slate-500">+{selectedFrame.objects.length - 5} more...</p>
                          )}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Risk Reasons */}
                  <div className="bg-slate-900/50 rounded-xl p-4 mb-6">
                    <h3 className="text-lg font-semibold text-white mb-3">🚩 Risk Factors</h3>
                    <div className="flex flex-wrap gap-2">
                      {selectedFrame.risk_assessment.reasons?.map((reason, idx) => (
                        <span
                          key={idx}
                          className="inline-block bg-red-900/40 border border-red-500/50 text-red-300 px-3 py-1 rounded-full text-sm"
                        >
                          {reason}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Navigation */}
                  <div className="flex items-center justify-between">
                    <button
                      onClick={() => navigateFrame('prev')}
                      className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg flex items-center space-x-2 transition-colors"
                    >
                      <ChevronLeft className="w-4 h-4" />
                      <span>Previous</span>
                    </button>

                    <div className="flex-1 text-center">
                      <p className="text-sm text-slate-400">
                        Navigate through frames | Press ESC to close
                      </p>
                    </div>

                    <button
                      onClick={() => navigateFrame('next')}
                      className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg flex items-center space-x-2 transition-colors"
                    >
                      <span>Next</span>
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </motion.div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}
