import { motion } from 'framer-motion'
import { AlertTriangle, AlertCircle, CheckCircle, XCircle } from 'lucide-react'

export default function RiskBadge({ level, score }) {
  const configs = {
    CRITICAL: {
      icon: XCircle,
      bg: 'bg-gradient-danger',
      text: 'text-white',
      border: 'border-red-600',
      animation: 'animate-pulse-slow',
    },
    HIGH: {
      icon: AlertTriangle,
      bg: 'bg-gradient-to-r from-orange-500 to-red-500',
      text: 'text-white',
      border: 'border-orange-600',
      animation: '',
    },
    MEDIUM: {
      icon: AlertCircle,
      bg: 'bg-gradient-warning',
      text: 'text-white',
      border: 'border-yellow-600',
      animation: '',
    },
    LOW: {
      icon: CheckCircle,
      bg: 'bg-gradient-success',
      text: 'text-white',
      border: 'border-green-600',
      animation: '',
    },
  }

  const config = configs[level] || configs.LOW
  const Icon = config.icon

  return (
    <motion.div
      initial={{ scale: 0.9, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      className={`${config.bg} ${config.text} ${config.animation} rounded-2xl p-6 shadow-2xl border-2 ${config.border}`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Icon className="w-8 h-8" />
          <div>
            <p className="text-sm opacity-90 font-medium">Risk Level</p>
            <p className="text-2xl font-bold">{level}</p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-sm opacity-90 font-medium">Score</p>
          <p className="text-3xl font-bold">{(score * 100).toFixed(1)}%</p>
        </div>
      </div>
    </motion.div>
  )
}
