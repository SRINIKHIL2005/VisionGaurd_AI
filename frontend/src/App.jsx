import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Mic } from 'lucide-react'
import Sidebar from './components/Sidebar'
import ProtectedRoute from './components/ProtectedRoute'
import WakeWordListener from './components/WakeWordListener'
import JarvisAssistant from './components/JarvisAssistant'
import Login from './pages/Login'
import Signup from './pages/Signup'
import Dashboard from './pages/Dashboard'
import ImageAnalysis from './pages/ImageAnalysis'
import VideoAnalysis from './pages/VideoAnalysis'
import LiveCCTV from './pages/LiveCCTV'
import FaceDatabase from './pages/FaceDatabase'
import Settings from './pages/Settings'

function App() {
  return (
    <Router>
      <Routes>
        {/* Public Routes */}
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />

        {/* Protected Routes */}
        <Route
          path="/*"
          element={
            <ProtectedRoute>
              {/* Global always-on modules */}
              <WakeWordListener />
              <JarvisAssistant />

              {/* Floating Jarvis button — visible on every page */}
              <motion.button
                onClick={() => {
                  try { window.dispatchEvent(new CustomEvent('visionguard:jarvis-open')) } catch {}
                }}
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
                title="Talk to Jarvis"
                className="fixed bottom-7 right-7 z-40 w-14 h-14 rounded-full flex items-center justify-center text-white shadow-xl shadow-indigo-500/40"
                style={{ background: 'linear-gradient(135deg, #6366f1, #ec4899)' }}
              >
                <Mic className="w-6 h-6" />
              </motion.button>

              <div className="flex min-h-screen bg-gradient-to-br from-gray-50 via-blue-50 to-purple-50">
                <Sidebar />
                <main className="flex-1 ml-64 p-8">
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5 }}
                  >
                    <Routes>
                      <Route path="/" element={<Dashboard />} />
                      <Route path="/image" element={<ImageAnalysis />} />
                      <Route path="/video" element={<VideoAnalysis />} />
                      <Route path="/live" element={<LiveCCTV />} />
                      <Route path="/database" element={<FaceDatabase />} />
                      <Route path="/settings" element={<Settings />} />
                    </Routes>
                  </motion.div>
                </main>
              </div>
            </ProtectedRoute>
          }
        />
      </Routes>
    </Router>
  )
}

export default App
