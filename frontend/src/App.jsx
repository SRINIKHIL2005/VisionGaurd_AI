import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { motion } from 'framer-motion'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import ImageAnalysis from './pages/ImageAnalysis'
import VideoAnalysis from './pages/VideoAnalysis'
import LiveCCTV from './pages/LiveCCTV'
import FaceDatabase from './pages/FaceDatabase'

function App() {
  return (
    <Router>
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
            </Routes>
          </motion.div>
        </main>
      </div>
    </Router>
  )
}

export default App
