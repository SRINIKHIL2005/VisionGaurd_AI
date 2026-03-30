import React, { useState, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Activity,
  AlertTriangle,
  Users,
  Navigation2,
  Eye,
  TrendingUp,
  ChevronDown,
  Download,
  Image as ImageIcon,
  BarChart3,
  Clock,
  Share2,
  FileDown,
} from 'lucide-react'
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts'

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899']

export default function AdvancedAnalyticsDisplay({ analytics, reports }) {
  const [expandedSections, setExpandedSections] = useState({
    activity: true,
    crowd: true,
    anomalies: true,
    loitering: true,
    movements: true,
    reports: true,
  })

  const toggleSection = (section) => {
    setExpandedSections((prev) => ({
      ...prev,
      [section]: !prev[section],
    }))
  }

  // Download handler for base64 images
  const downloadImage = (base64, filename) => {
    try {
      const link = document.createElement('a')
      link.href = base64
      link.download = filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    } catch (error) {
      console.error('Download failed:', error)
      alert('Failed to download image')
    }
  }

  // Export report as JSON
  const exportReportAsJSON = () => {
    try {
      const dataStr = JSON.stringify(reports.json_report, null, 2)
      const dataBlob = new Blob([dataStr], { type: 'application/json' })
      const url = URL.createObjectURL(dataBlob)
      const link = document.createElement('a')
      link.href = url
      link.download = `report_${new Date().getTime()}.json`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
    } catch (error) {
      console.error('JSON export failed:', error)
      alert('Failed to export JSON report')
    }
  }

  // Copy report data to clipboard
  const copyReportLink = async () => {
    try {
      const reportSummary = `
Analysis Report - Generated ${new Date().toLocaleString()}
Frames Analyzed: ${reports.json_report?.metadata?.total_frames_analyzed || 'N/A'}
Duration: ${reports.json_report?.metadata?.duration_seconds?.toFixed(2) || 'N/A'}s
${JSON.stringify(reports.json_report?.statistics, null, 2)}
      `
      await navigator.clipboard.writeText(reportSummary)
      alert('Report copied to clipboard!')
    } catch (error) {
      console.error('Copy failed:', error)
      alert('Failed to copy report')
    }
  }

  if (!analytics) {
    return (
      <div className="p-4 bg-red-900/20 border border-red-500/50 rounded-xl">
        <p className="text-red-300">❌ No analytics data provided</p>
      </div>
    )
  }

  const {
    activity_summary = {},
    anomalies_detected = [],
    anomalies_total,
    crowd_density_timeline = [],
    crowd_density_points_total,
    loitering_incidents = [],
    loitering_incidents_total,
    unusual_movements = [],
    unusual_movements_total,
    object_motion_events = [],
    object_motion_events_total,
    frames_with_people = 0,
    heatmap_generated,
    status = 'UNKNOWN',
    enabled = false,
    preview_limits = {},
    dependency_health = {},
  } = analytics

  const anomaliesCount = anomalies_total ?? anomalies_detected.length
  const crowdCount = crowd_density_points_total ?? crowd_density_timeline.length
  const loiteringCount = loitering_incidents_total ?? loitering_incidents.length
  const unusualCount = unusual_movements_total ?? unusual_movements.length
  const objectMotionCount = object_motion_events_total ?? object_motion_events.length

  // Show status indicator if analytics are disabled
  const isDisabled = !enabled || status.includes('DISABLED')
  const statusMessage = status === 'DISABLED (video > 60s)' 
    ? 'Advanced analytics disabled: Video longer than 60 seconds' 
    : status.includes('DISABLED') 
    ? 'Advanced analytics unavailable: Backend dependencies not loaded'
    : status
  
  const hasData = anomaliesCount > 0 || crowdCount > 0 || loiteringCount > 0 || unusualCount > 0 || objectMotionCount > 0

  // Prepare activity chart data
  const activityChartData = Object.entries(activity_summary).map(([key, value]) => ({
    name: key.toUpperCase(),
    count: value.count || value || 0,
    percentage: value.percentage || 0,
  }))

  // Prepare crowd density chart data
  const crowdChartData = crowd_density_timeline
    .map((item, idx) => ({
      frame: item.frame || idx,
      density: item.person_count ?? item.density ?? 0,
      state: item.density_level || item.state || 'UNKNOWN',
      occupied_cells: item.occupied_cells ?? 0,
      max_density: item.max_density ?? 0,
    }))
    .slice(0, 100) // Limit to 100 points for performance

  // Severity color mapping
  const getSeverityColor = (severity) => {
    switch (severity?.toUpperCase()) {
      case 'CRITICAL':
        return 'bg-red-900/40 border-red-500/50 text-red-300'
      case 'HIGH':
        return 'bg-orange-900/40 border-orange-500/50 text-orange-300'
      case 'MEDIUM':
        return 'bg-yellow-900/40 border-yellow-500/50 text-yellow-300'
      case 'LOW':
        return 'bg-blue-900/40 border-blue-500/50 text-blue-300'
      default:
        return 'bg-slate-900/40 border-slate-500/50 text-slate-300'
    }
  }

  const getSeverityBadgeColor = (severity) => {
    switch (severity?.toUpperCase()) {
      case 'CRITICAL':
        return 'bg-red-600 text-white'
      case 'HIGH':
        return 'bg-orange-500 text-white'
      case 'MEDIUM':
        return 'bg-yellow-500 text-white'
      case 'LOW':
        return 'bg-blue-500 text-white'
      default:
        return 'bg-slate-600 text-white'
    }
  }

  return (
    <div className="space-y-4">
      {isDisabled && (
        <div className="p-3 bg-amber-900/20 border border-amber-500/40 rounded-lg">
          <p className="text-amber-300 text-sm">{statusMessage}</p>
        </div>
      )}

      {!isDisabled && !hasData && (
        <div className="p-3 bg-slate-900/50 border border-slate-700/50 rounded-lg">
          <p className="text-slate-300 text-sm">
            Advanced analytics ran, but no incidents were detected in sampled frames. Check Frames w/ People and Object Motion to interpret this run.
          </p>
        </div>
      )}

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-8 gap-2">
        <div className="bg-blue-900/40 border border-blue-500/50 rounded-lg p-3 text-center">
          <p className="text-2xl font-bold text-blue-300">{activityChartData.length}</p>
          <p className="text-xs text-slate-400">Activity Types</p>
        </div>
        <div className="bg-red-900/40 border border-red-500/50 rounded-lg p-3 text-center">
          <p className="text-2xl font-bold text-red-300">{anomaliesCount}</p>
          <p className="text-xs text-slate-400">Anomalies</p>
        </div>
        <div className="bg-green-900/40 border border-green-500/50 rounded-lg p-3 text-center">
          <p className="text-2xl font-bold text-green-300">{crowdCount}</p>
          <p className="text-xs text-slate-400">Crowd Updates</p>
        </div>
        <div className="bg-yellow-900/40 border border-yellow-500/50 rounded-lg p-3 text-center">
          <p className="text-2xl font-bold text-yellow-300">{loiteringCount}</p>
          <p className="text-xs text-slate-400">Loitering</p>
        </div>
        <div className="bg-purple-900/40 border border-purple-500/50 rounded-lg p-3 text-center">
          <p className="text-2xl font-bold text-purple-300">{unusualCount}</p>
          <p className="text-xs text-slate-400">Unusual</p>
        </div>
        <div className="bg-cyan-900/40 border border-cyan-500/50 rounded-lg p-3 text-center">
          <p className="text-2xl font-bold text-cyan-300">{objectMotionCount}</p>
          <p className="text-xs text-slate-400">Object Motion</p>
        </div>
        <div className="bg-indigo-900/40 border border-indigo-500/50 rounded-lg p-3 text-center">
          <p className="text-2xl font-bold text-indigo-300">{frames_with_people}</p>
          <p className="text-xs text-slate-400">Frames w/ People</p>
        </div>
        <div className={`${heatmap_generated ? 'bg-orange-900/40 border-orange-500/50' : 'bg-slate-900/40 border-slate-500/50'} border rounded-lg p-3 text-center`}>
          <p className="text-2xl font-bold text-orange-300">{heatmap_generated ? '✓' : '✗'}</p>
          <p className="text-xs text-slate-400">Heatmap</p>
        </div>
      </div>

      {/* Activity Summary */}
      <motion.div
        className="bg-[#060c18] rounded-2xl border border-slate-800/60 overflow-hidden"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <button
          onClick={() => toggleSection('activity')}
          className="w-full px-6 py-4 flex items-center justify-between hover:bg-slate-800/30 transition-colors"
        >
          <div className="flex items-center space-x-3">
            <Activity className="w-6 h-6 text-blue-400" />
            <h3 className="text-lg font-semibold text-white">Activity Summary</h3>
          </div>
          <ChevronDown
            className={`w-5 h-5 text-slate-400 transition-transform ${
              expandedSections.activity ? 'rotate-180' : ''
            }`}
          />
        </button>

        <AnimatePresence>
          {expandedSections.activity && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="px-6 pb-6 border-t border-slate-800/40"
            >
              {activityChartData.length > 0 ? (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart data={activityChartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis dataKey="name" stroke="#9ca3af" fontSize={12} />
                      <YAxis stroke="#9ca3af" fontSize={12} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#1f2937',
                          border: '1px solid #4b5563',
                          borderRadius: '8px',
                        }}
                      />
                      <Bar dataKey="count" fill="#3b82f6" radius={[8, 8, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>

                  <ResponsiveContainer width="100%" height={250}>
                    <PieChart>
                      <Pie
                        data={activityChartData}
                        cx="50%"
                        cy="50%"
                        labelLine={false}
                        label={({ name, percentage }) => `${name}: ${(percentage || 0).toFixed(1)}%`}
                        outerRadius={80}
                        fill="#8884d8"
                        dataKey="count"
                      >
                        {activityChartData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#1f2937',
                          border: '1px solid #4b5563',
                          borderRadius: '8px',
                        }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <p className="text-slate-400 text-center py-4">No activity data available</p>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {/* Crowd Density Timeline */}
      <motion.div
        className="bg-[#060c18] rounded-2xl border border-slate-800/60 overflow-hidden"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <button
          onClick={() => toggleSection('crowd')}
          className="w-full px-6 py-4 flex items-center justify-between hover:bg-slate-800/30 transition-colors"
        >
          <div className="flex items-center space-x-3">
            <Users className="w-6 h-6 text-green-400" />
            <h3 className="text-lg font-semibold text-white">Crowd Density Timeline</h3>
          </div>
          <ChevronDown
            className={`w-5 h-5 text-slate-400 transition-transform ${
              expandedSections.crowd ? 'rotate-180' : ''
            }`}
          />
        </button>

        <AnimatePresence>
          {expandedSections.crowd && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="px-6 pb-6 border-t border-slate-800/40"
            >
              {crowdChartData.length > 0 ? (
                <>
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={crowdChartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis dataKey="frame" stroke="#9ca3af" fontSize={12} />
                      <YAxis stroke="#9ca3af" fontSize={12} label={{ value: 'People', angle: -90, position: 'insideLeft' }} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#1f2937',
                          border: '1px solid #4b5563',
                          borderRadius: '8px',
                        }}
                      />
                      <Legend />
                      <Line
                        type="monotone"
                        dataKey="density"
                        stroke="#10b981"
                        strokeWidth={2}
                        dot={false}
                        isAnimationActive={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                  <p className="text-xs text-slate-400 mt-2">
                    Peak People Count: {Math.max(...crowdChartData.map((d) => d.density || 0)).toFixed(0)}
                  </p>
                </>
              ) : (
                <p className="text-slate-400 text-center py-4">No crowd density data available</p>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {/* Anomalies Detected */}
      <motion.div
        className="bg-[#060c18] rounded-2xl border border-slate-800/60 overflow-hidden"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        <button
          onClick={() => toggleSection('anomalies')}
          className="w-full px-6 py-4 flex items-center justify-between hover:bg-slate-800/30 transition-colors"
        >
          <div className="flex items-center space-x-3">
            <AlertTriangle className="w-6 h-6 text-red-400" />
            <h3 className="text-lg font-semibold text-white">
              Anomalies Detected ({anomalies_detected.length})
            </h3>
          </div>
          <ChevronDown
            className={`w-5 h-5 text-slate-400 transition-transform ${
              expandedSections.anomalies ? 'rotate-180' : ''
            }`}
          />
        </button>

        <AnimatePresence>
          {expandedSections.anomalies && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="px-6 pb-6 border-t border-slate-800/40 max-h-96 overflow-y-auto"
            >
              {anomalies_detected.length > 0 ? (
                <div className="space-y-3">
                  {anomaliesCount > anomalies_detected.length && (
                    <p className="text-xs text-slate-400">Showing first {anomalies_detected.length} of {anomaliesCount} anomalies.</p>
                  )}
                  {anomalies_detected.map((anomaly, idx) => (
                    <div key={idx} className={`p-4 rounded-xl border ${getSeverityColor(anomaly.severity)}`}>
                      <div className="flex items-start justify-between mb-2">
                        <span className="font-semibold">Frame #{anomaly.frame}</span>
                        <span className={`px-2 py-1 rounded text-xs font-bold ${getSeverityBadgeColor(anomaly.severity)}`}>
                          {anomaly.severity}
                        </span>
                      </div>
                      <p className="text-sm mb-2">{anomaly.description}</p>
                      {anomaly.features && (
                        <div className="flex flex-wrap gap-2">
                          {Object.entries(anomaly.features).map(([key, value]) => (
                            <span key={key} className="text-xs bg-slate-700/50 px-2 py-1 rounded-full">
                              {key}: {value}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-slate-400 text-center py-4">No anomalies detected</p>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {/* Loitering Incidents */}
      <motion.div
        className="bg-[#060c18] rounded-2xl border border-slate-800/60 overflow-hidden"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <button
          onClick={() => toggleSection('loitering')}
          className="w-full px-6 py-4 flex items-center justify-between hover:bg-slate-800/30 transition-colors"
        >
          <div className="flex items-center space-x-3">
            <Clock className="w-6 h-6 text-yellow-400" />
            <h3 className="text-lg font-semibold text-white">
              Loitering Incidents ({loitering_incidents.length})
            </h3>
          </div>
          <ChevronDown
            className={`w-5 h-5 text-slate-400 transition-transform ${
              expandedSections.loitering ? 'rotate-180' : ''
            }`}
          />
        </button>

        <AnimatePresence>
          {expandedSections.loitering && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="px-6 pb-6 border-t border-slate-800/40 max-h-96 overflow-y-auto"
            >
              {loitering_incidents.length > 0 ? (
                <div className="space-y-3">
                  {loiteringCount > loitering_incidents.length && (
                    <p className="text-xs text-slate-400">Showing first {loitering_incidents.length} of {loiteringCount} loitering incidents.</p>
                  )}
                  {loitering_incidents.map((incident, idx) => (
                    <div key={idx} className="p-4 rounded-xl border border-yellow-500/40 bg-yellow-900/20">
                      <div className="flex items-start justify-between mb-2">
                        <span className="font-semibold text-white">
                          Loitering Event #{idx + 1}
                          {incident.track_id !== undefined ? ` (Track #${incident.track_id})` : ''}
                        </span>
                        <span className="text-xs text-yellow-300 bg-yellow-900/40 px-2 py-1 rounded">
                          {(incident.duration_seconds ?? incident.duration ?? 0).toFixed(1)}s
                        </span>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm text-slate-300">
                        <div>
                          Movement: <span className="font-mono text-yellow-400">{(incident.movement_distance ?? 0).toFixed(1)} px</span>
                        </div>
                        <div>
                          Position: <span className="font-mono text-yellow-400">
                            {Array.isArray(incident.position) ? `(${incident.position[0]}, ${incident.position[1]})` : 'N/A'}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-slate-400 text-center py-4">No loitering incidents detected</p>
              )}
              
              {/* Settings Info */}
              <div className="mt-4 p-3 bg-slate-900/40 border border-slate-700/50 rounded-lg text-xs text-slate-400">
                <p className="font-semibold text-slate-300 mb-1">ℹ️ Detection Thresholds</p>
                <p>Customize these settings in Account Settings → Video Analysis Settings</p>
                <div className="mt-2 space-y-1 text-slate-500">
                  <p>• Min Duration: 5.0 seconds</p>
                  <p>• Position Threshold: 50 pixels</p>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {/* Unusual Movements */}
      <motion.div
        className="bg-[#060c18] rounded-2xl border border-slate-800/60 overflow-hidden"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
      >
        <button
          onClick={() => toggleSection('movements')}
          className="w-full px-6 py-4 flex items-center justify-between hover:bg-slate-800/30 transition-colors"
        >
          <div className="flex items-center space-x-3">
            <Navigation2 className="w-6 h-6 text-purple-400" />
            <div>
              <h3 className="text-lg font-semibold text-white">
                Unusual Movements ({unusual_movements.length})
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">Detects rapid/anomalous people movement (requires person tracking)</p>
            </div>
          </div>
          <ChevronDown
            className={`w-5 h-5 text-slate-400 transition-transform ${
              expandedSections.movements ? 'rotate-180' : ''
            }`}
          />
        </button>

        <AnimatePresence>
          {expandedSections.movements && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="px-6 pb-6 border-t border-slate-800/40 max-h-96 overflow-y-auto"
            >
              {unusual_movements.length > 0 ? (
                <div className="space-y-3">
                  {unusualCount > unusual_movements.length && (
                    <p className="text-xs text-slate-400">Showing first {unusual_movements.length} of {unusualCount} unusual movements.</p>
                  )}
                  {unusual_movements.map((movement, idx) => (
                    <div key={idx} className={`p-4 rounded-xl border ${getSeverityColor(movement.severity)}`}>
                      <div className="flex items-start justify-between mb-2">
                        <span className="font-semibold text-white">Track #{movement.track_id}</span>
                        <span className={`px-2 py-1 rounded text-xs font-bold ${getSeverityBadgeColor(movement.severity)}`}>
                          {movement.severity}
                        </span>
                      </div>
                      <p className="text-sm text-slate-300 mb-3">{movement.anomaly_type}</p>
                      <div className="grid grid-cols-3 gap-2 text-xs text-slate-400">
                        <div>
                          Velocity: <span className="font-mono text-purple-300">{movement.velocity} px/f</span>
                        </div>
                        <div>
                          Z-Score: <span className="font-mono text-purple-300">{movement.z_score}</span>
                        </div>
                        <div>
                          Status: <span className="font-mono text-purple-300">Anomalous</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-6 space-y-2">
                  <p className="text-slate-400">No unusual movements detected</p>
                  <p className="text-xs text-slate-500">
                    💡 Requires: People/persons being tracked + Fast/sudden movement patterns
                  </p>
                  <p className="text-xs text-slate-500">
                    Note: Weapon detection is tracked separately in Anomalies
                  </p>
                </div>
              )}

              {Object.keys(dependency_health || {}).length > 0 && (
                <div className="mt-4 p-3 bg-slate-900/40 border border-slate-700/50 rounded-lg text-xs text-slate-300">
                  <p className="font-semibold mb-2">Dependency Health</p>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                    {Object.entries(dependency_health).map(([k, v]) => (
                      <div key={k} className="flex items-center justify-between bg-slate-800/40 px-2 py-1 rounded">
                        <span className="text-slate-400">{k}</span>
                        <span className={v ? 'text-green-400' : 'text-red-400'}>{v ? 'OK' : 'MISSING'}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {/* Reports Section */}
      {reports && (reports.json_report || reports.timeline_chart || reports.statistics_chart) && (
        <motion.div
          className="bg-[#060c18] rounded-2xl border border-slate-800/60 overflow-hidden"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
        >
          <div className="px-6 py-4 flex items-center justify-between hover:bg-slate-800/30 transition-colors border-b border-slate-800/40">
            <button
              onClick={() => toggleSection('reports')}
              className="flex-1 flex items-center space-x-3"
            >
              <BarChart3 className="w-6 h-6 text-purple-400" />
              <h3 className="text-lg font-semibold text-white">Detailed Reports</h3>
            </button>
            <div className="flex items-center space-x-2">
              {reports.json_report && (
                <button
                  onClick={exportReportAsJSON}
                  className="p-2 rounded-lg hover:bg-blue-500/20 text-blue-400 transition-colors"
                  title="Export as JSON"
                >
                  <FileDown className="w-5 h-5" />
                </button>
              )}
              {(reports.timeline_chart || reports.statistics_chart) && (
                <button
                  onClick={copyReportLink}
                  className="p-2 rounded-lg hover:bg-green-500/20 text-green-400 transition-colors"
                  title="Copy report summary"
                >
                  <Share2 className="w-5 h-5" />
                </button>
              )}
              <ChevronDown
                onClick={() => toggleSection('reports')}
                className={`w-5 h-5 text-slate-400 transition-transform cursor-pointer hover:text-slate-300 ${
                  expandedSections.reports ? 'rotate-180' : ''
                }`}
              />
            </div>
          </div>

          <AnimatePresence>
            {expandedSections.reports && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="px-6 pb-6 border-t border-slate-800/40 space-y-6"
              >
                {/* JSON Report Summary */}
                {reports.json_report && (
                  <div className="space-y-3">
                    <h4 className="font-semibold text-blue-300 flex items-center space-x-2">
                      <Activity className="w-5 h-5" />
                      <span>Analysis Summary</span>
                    </h4>
                    <div className="bg-gradient-to-br from-slate-900/80 to-slate-900/40 rounded-lg p-4 space-y-3 text-sm text-slate-300 border border-slate-700/30">
                      {reports.json_report.metadata && (
                        <>
                          <div className="grid grid-cols-3 gap-3">
                            <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-3">
                              <p className="text-xs text-slate-500 uppercase tracking-wider">Generated</p>
                              <p className="text-sm font-mono text-blue-300 mt-1">{new Date(reports.json_report.metadata.generated_at).toLocaleDateString()}</p>
                              <p className="text-xs text-blue-400/60">{new Date(reports.json_report.metadata.generated_at).toLocaleTimeString()}</p>
                            </div>
                            <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-3">
                              <p className="text-xs text-slate-500 uppercase tracking-wider">Frames</p>
                              <p className="text-lg font-bold text-green-300">{reports.json_report.metadata.total_frames_analyzed}</p>
                              <p className="text-xs text-green-400/60">analyzed</p>
                            </div>
                            <div className="bg-orange-500/10 border border-orange-500/30 rounded-lg p-3">
                              <p className="text-xs text-slate-500 uppercase tracking-wider">Duration</p>
                              <p className="text-lg font-bold text-orange-300">{reports.json_report.metadata.duration_seconds?.toFixed(2)}</p>
                              <p className="text-xs text-orange-400/60">seconds</p>
                            </div>
                          </div>
                        </>
                      )}
                      {reports.json_report.statistics && (
                        <>
                          <div className="border-t border-slate-700/50 pt-3 mt-1">
                            <p className="text-slate-400 mb-2 font-semibold text-xs uppercase tracking-wider">Key Statistics</p>
                            <div className="grid grid-cols-2 gap-2">
                              {Object.entries(reports.json_report.statistics).map(([key, value]) => (
                                <div key={key} className="bg-slate-800/40 rounded p-2 border border-slate-700/30">
                                  <p className="text-xs text-slate-500 uppercase">{key}</p>
                                  <p className="font-mono text-slate-100">{typeof value === 'object' ? JSON.stringify(value) : value}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                )}

                {/* Timeline Chart */}
                {reports.timeline_chart && (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <h4 className="font-semibold text-green-300 flex items-center space-x-2">
                        <TrendingUp className="w-5 h-5" />
                        <span>Risk Timeline</span>
                      </h4>
                      <button
                        onClick={() => downloadImage(reports.timeline_chart, `timeline_${new Date().getTime()}.png`)}
                        className="flex items-center space-x-1 px-3 py-1 rounded-lg bg-green-500/20 hover:bg-green-500/30 text-green-400 text-sm transition-colors"
                      >
                        <Download className="w-4 h-4" />
                        <span>PNG</span>
                      </button>
                    </div>
                    <img
                      src={reports.timeline_chart}
                      alt="Timeline Chart"
                      className="w-full rounded-lg border border-slate-700/50"
                    />
                  </div>
                )}

                {/* Statistics Chart */}
                {reports.statistics_chart && (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <h4 className="font-semibold text-orange-300 flex items-center space-x-2">
                        <BarChart3 className="w-5 h-5" />
                        <span>Statistics</span>
                      </h4>
                      <button
                        onClick={() => downloadImage(reports.statistics_chart, `statistics_${new Date().getTime()}.png`)}
                        className="flex items-center space-x-1 px-3 py-1 rounded-lg bg-orange-500/20 hover:bg-orange-500/30 text-orange-400 text-sm transition-colors"
                      >
                        <Download className="w-4 h-4" />
                        <span>PNG</span>
                      </button>
                    </div>
                    <img
                      src={reports.statistics_chart}
                      alt="Statistics Chart"
                      className="w-full rounded-lg border border-slate-700/50"
                    />
                  </div>
                )}

                {/* Report Actions Footer */}
                <div className="border-t border-slate-700/50 pt-4 flex flex-wrap gap-3">
                  {reports.json_report && (
                    <>
                      <button
                        onClick={exportReportAsJSON}
                        className="flex items-center space-x-2 px-4 py-2 rounded-lg bg-blue-500/20 hover:bg-blue-500/30 text-blue-300 text-sm transition-colors"
                      >
                        <FileDown className="w-4 h-4" />
                        <span>Export JSON</span>
                      </button>
                      <button
                        onClick={copyReportLink}
                        className="flex items-center space-x-2 px-4 py-2 rounded-lg bg-green-500/20 hover:bg-green-500/30 text-green-300 text-sm transition-colors"
                      >
                        <Share2 className="w-4 h-4" />
                        <span>Copy Summary</span>
                      </button>
                    </>
                  )}
                  <div className="flex-1" />
                  <span className="text-xs text-slate-400 self-center">
                    Generated: {reports.json_report?.metadata?.generated_at ? new Date(reports.json_report.metadata.generated_at).toLocaleString() : 'N/A'}
                  </span>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      )}

    </div>
  )
}
