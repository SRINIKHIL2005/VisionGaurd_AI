import { Link, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import { 
  LayoutDashboard, 
  Image, 
  Video, 
  Camera, 
  Users, 
  Shield,
  Activity
} from 'lucide-react'

const menuItems = [
  { path: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { path: '/image', icon: Image, label: 'Image Analysis' },
  { path: '/video', icon: Video, label: 'Video Analysis' },
  { path: '/live', icon: Camera, label: 'Live CCTV' },
  { path: '/database', icon: Users, label: 'Face Database' },
]

export default function Sidebar() {
  const location = useLocation()

  return (
    <motion.aside
      initial={{ x: -250 }}
      animate={{ x: 0 }}
      className="fixed left-0 top-0 h-screen w-64 bg-gradient-primary shadow-2xl"
    >
      <div className="p-6">
        {/* Logo */}
        <div className="flex items-center justify-center mb-8">
          <div className="relative">
            <Shield className="w-12 h-12 text-white" strokeWidth={1.5} />
            <Activity className="w-6 h-6 text-green-400 absolute -bottom-1 -right-1 animate-pulse" />
          </div>
        </div>
        <h1 className="text-2xl font-bold text-white text-center mb-2">
          VisionGuard AI
        </h1>
        <p className="text-purple-200 text-center text-sm mb-8">
          Security Intelligence v2.0
        </p>

        {/* Navigation */}
        <nav className="space-y-2">
          {menuItems.map((item) => {
            const Icon = item.icon
            const isActive = location.pathname === item.path
            
            return (
              <Link
                key={item.path}
                to={item.path}
                className="block"
              >
                <motion.div
                  whileHover={{ x: 5 }}
                  whileTap={{ scale: 0.95 }}
                  className={`flex items-center space-x-3 px-4 py-3 rounded-lg transition-all ${
                    isActive
                      ? 'bg-white bg-opacity-20 text-white shadow-lg'
                      : 'text-purple-100 hover:bg-white hover:bg-opacity-10'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  <span className="font-medium">{item.label}</span>
                </motion.div>
              </Link>
            )
          })}
        </nav>

        {/* Status Indicator */}
        <div className="mt-8 p-4 bg-white bg-opacity-10 rounded-lg">
          <div className="flex items-center justify-between mb-2">
            <span className="text-purple-200 text-sm">System Status</span>
            <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
          </div>
          <div className="space-y-1 text-xs text-purple-200">
            <div className="flex justify-between">
              <span>Deepfake AI</span>
              <span className="text-green-400">●</span>
            </div>
            <div className="flex justify-between">
              <span>Face Recognition</span>
              <span className="text-green-400">●</span>
            </div>
            <div className="flex justify-between">
              <span>Object Detection</span>
              <span className="text-green-400">●</span>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-8 text-center text-purple-200 text-xs">
          <p>© 2025 VisionGuard</p>
          <p className="mt-1">Powered by AI</p>
        </div>
      </div>
    </motion.aside>
  )
}
