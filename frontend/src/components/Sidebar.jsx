import { Link, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import { 
  LayoutDashboard, 
  Image, 
  Video, 
  Camera, 
  Users, 
  Shield,
  Activity,
  Settings as SettingsIcon,
  LogOut,
  User
} from 'lucide-react'
import authService from '../services/authService'
import { useState, useEffect } from 'react'

const menuItems = [
  { path: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { path: '/image', icon: Image, label: 'Image Analysis' },
  { path: '/video', icon: Video, label: 'Video Analysis' },
  { path: '/live', icon: Camera, label: 'Live CCTV' },
  { path: '/database', icon: Users, label: 'Face Database' },
  { path: '/settings', icon: SettingsIcon, label: 'Settings' },
]

export default function Sidebar() {
  const location = useLocation()
  const [user, setUser] = useState(null)

  useEffect(() => {
    const currentUser = authService.getCurrentUser()
    setUser(currentUser)
  }, [])

  const handleLogout = () => {
    if (confirm('Are you sure you want to logout?')) {
      authService.logout()
    }
  }

  return (
    <motion.aside
      initial={{ x: -250 }}
      animate={{ x: 0 }}
      className="fixed left-0 top-0 h-screen w-64 bg-gradient-primary shadow-2xl flex flex-col"
    >
      <div className="flex-1 p-6 overflow-y-auto">
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

        {/* User Info */}
        {user && (
          <div className="mb-6 p-3 bg-white bg-opacity-10 rounded-lg">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-400 to-purple-400 rounded-full flex items-center justify-center">
                <User className="w-6 h-6 text-white" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-white font-medium text-sm truncate">
                  {user.full_name}
                </p>
                <p className="text-purple-200 text-xs truncate">
                  {user.email}
                </p>
              </div>
            </div>
          </div>
        )}

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
      </div>

      {/* Footer with Logout */}
      <div className="p-6 border-t border-white border-opacity-10">
        <button
          onClick={handleLogout}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-red-500 hover:bg-red-600 text-white rounded-lg transition-all font-medium"
        >
          <LogOut className="w-5 h-5" />
          Logout
        </button>
        <div className="mt-4 text-center text-purple-200 text-xs">
          <p>© 2026 VisionGuard</p>
          <p className="mt-1">Powered by AI</p>
        </div>
      </div>
    </motion.aside>
  )
}
