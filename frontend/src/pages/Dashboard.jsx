import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Shield, Eye, Users, Activity, Camera, Image as ImageIcon, Video, Zap, Brain, Target, Lock, AlertCircle } from 'lucide-react'
import axios from 'axios'

export default function Dashboard() {
  const [systemHealth, setSystemHealth] = useState(null)
  const [faceCount, setFaceCount] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch system health
        const healthRes = await axios.get('/health')
        setSystemHealth(healthRes.data)

        // Fetch face database count
        const facesRes = await axios.get('/face/list')
        setFaceCount(facesRes.data.identities.length)
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [])

  return (
    <div className="space-y-8">
      {/* Hero Section */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative overflow-hidden bg-gradient-to-br from-blue-600 via-purple-600 to-pink-600 rounded-3xl shadow-2xl p-12 text-white"
      >
        <div className="absolute top-0 right-0 w-64 h-64 bg-white opacity-5 rounded-full -mr-32 -mt-32"></div>
        <div className="absolute bottom-0 left-0 w-96 h-96 bg-white opacity-5 rounded-full -ml-48 -mb-48"></div>
        
        <div className="relative z-10">
          <div className="flex items-center space-x-4 mb-4">
            <div className="p-4 bg-white/20 backdrop-blur-sm rounded-2xl">
              <Shield className="w-12 h-12" />
            </div>
            <div>
              <h1 className="text-5xl font-bold mb-2">VisionGuard AI</h1>
              <p className="text-xl text-blue-100">Real-Time Security Intelligence System</p>
            </div>
          </div>
          
          <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-white/10 backdrop-blur-sm rounded-xl p-6 border border-white/20">
              <div className="flex items-center justify-between mb-2">
                <span className="text-blue-100">System Status</span>
                <div className="w-3 h-3 bg-green-400 rounded-full animate-pulse"></div>
              </div>
              <p className="text-3xl font-bold">
                {loading ? '...' : systemHealth?.status === 'healthy' ? 'Online' : 'Offline'}
              </p>
            </div>
            
            <div className="bg-white/10 backdrop-blur-sm rounded-xl p-6 border border-white/20">
              <span className="text-blue-100 block mb-2">AI Models Loaded</span>
              <p className="text-3xl font-bold">
                {loading ? '...' : systemHealth ? '3/3' : '0/3'}
              </p>
            </div>
            
            <div className="bg-white/10 backdrop-blur-sm rounded-xl p-6 border border-white/20">
              <span className="text-blue-100 block mb-2">Registered Identities</span>
              <p className="text-3xl font-bold">{loading ? '...' : faceCount}</p>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Project Overview */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="bg-white rounded-2xl shadow-lg p-8 border border-gray-100"
      >
        <h2 className="text-3xl font-bold text-gray-900 mb-4">About This Project</h2>
        <div className="prose max-w-none">
          <p className="text-lg text-gray-700 leading-relaxed mb-4">
            <strong>VisionGuard AI</strong> is an advanced computer vision security platform that combines multiple AI models 
            to provide comprehensive threat detection and monitoring capabilities. Built for VRSU (Vision Recognition Security Unit), 
            this system integrates state-of-the-art deep learning technologies to protect against modern security threats.
          </p>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-6">
            <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl p-6">
              <Brain className="w-10 h-10 text-blue-600 mb-3" />
              <h3 className="font-bold text-gray-900 mb-2">Deep Learning Powered</h3>
              <p className="text-sm text-gray-700">
                Utilizes Vision Transformers, ArcFace, and YOLOv8 for maximum accuracy
              </p>
            </div>
            
            <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-xl p-6">
              <Zap className="w-10 h-10 text-purple-600 mb-3" />
              <h3 className="font-bold text-gray-900 mb-2">Real-Time Processing</h3>
              <p className="text-sm text-gray-700">
                5-15 FPS analysis with instant threat detection and alerting
              </p>
            </div>
            
            <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-xl p-6">
              <Lock className="w-10 h-10 text-green-600 mb-3" />
              <h3 className="font-bold text-gray-900 mb-2">Multi-Layer Security</h3>
              <p className="text-sm text-gray-700">
                Deepfake detection, face recognition, and object detection combined
              </p>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Features Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Core AI Capabilities */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-white rounded-2xl shadow-lg p-8 border border-gray-100"
        >
          <div className="flex items-center space-x-3 mb-6">
            <div className="p-3 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl">
              <Target className="w-6 h-6 text-white" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900">AI Detection Models</h2>
          </div>

          <div className="space-y-4">
            <div className="p-5 bg-gradient-to-r from-blue-50 via-purple-50 to-pink-50 rounded-xl border-l-4 border-blue-500">
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-bold text-gray-900">🎭 Deepfake Detection</h3>
                <span className={`px-3 py-1 rounded-full text-xs font-bold ${
                  loading ? 'bg-gray-200 text-gray-600' : 
                  systemHealth?.models_loaded?.deepfake_detector ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                }`}>
                  {loading ? 'Loading...' : systemHealth?.models_loaded?.deepfake_detector ? 'LOADED' : 'OFFLINE'}
                </span>
              </div>
              <p className="text-sm text-gray-700 mb-2">
                Vision Transformer (ViT) model trained on deepfake datasets
              </p>
              <p className="text-xs text-gray-600">
                Model: dima806/deepfake_vs_real_image_detection • Accuracy: 95%+
              </p>
            </div>

            <div className="p-5 bg-gradient-to-r from-cyan-50 via-blue-50 to-indigo-50 rounded-xl border-l-4 border-cyan-500">
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-bold text-gray-900">👤 Face Recognition</h3>
                <span className={`px-3 py-1 rounded-full text-xs font-bold ${
                  loading ? 'bg-gray-200 text-gray-600' : 
                  systemHealth?.models_loaded?.face_recognizer ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                }`}>
                  {loading ? 'Loading...' : systemHealth?.models_loaded?.face_recognizer ? 'LOADED' : 'OFFLINE'}
                </span>
              </div>
              <p className="text-sm text-gray-700 mb-2">
                InsightFace ArcFace technology for identity matching
              </p>
              <p className="text-xs text-gray-600">
                Model: buffalo_l • Database: {faceCount} identities • Multi-face tracking
              </p>
            </div>

            <div className="p-5 bg-gradient-to-r from-green-50 via-emerald-50 to-teal-50 rounded-xl border-l-4 border-green-500">
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-bold text-gray-900">🎯 Object Detection</h3>
                <span className={`px-3 py-1 rounded-full text-xs font-bold ${
                  loading ? 'bg-gray-200 text-gray-600' : 
                  systemHealth?.models_loaded?.object_detector ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                }`}>
                  {loading ? 'Loading...' : systemHealth?.models_loaded?.object_detector ? 'LOADED' : 'OFFLINE'}
                </span>
              </div>
              <p className="text-sm text-gray-700 mb-2">
                YOLOv8 real-time detection with threat classification
              </p>
              <p className="text-xs text-gray-600">
                Model: yolov8n.pt • 80 object classes • 5-15 FPS processing
              </p>
            </div>

            <div className="p-5 bg-gradient-to-r from-orange-50 via-red-50 to-pink-50 rounded-xl border-l-4 border-orange-500">
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-bold text-gray-900">⚠️ Risk Assessment</h3>
                <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-xs font-bold">
                  ACTIVE
                </span>
              </div>
              <p className="text-sm text-gray-700 mb-2">
                Multi-factor threat evaluation engine
              </p>
              <p className="text-xs text-gray-600">
                Combines all detection outputs • Real-time scoring • Automated alerts
              </p>
            </div>
          </div>
        </motion.div>

        {/* Feature Access Cards */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.3 }}
          className="space-y-4"
        >
          <h2 className="text-2xl font-bold text-gray-900 flex items-center">
            <Activity className="w-7 h-7 mr-3 text-purple-600" />
            Available Features
          </h2>

          <motion.a
            href="/image"
            whileHover={{ scale: 1.02, y: -2 }}
            whileTap={{ scale: 0.98 }}
            className="block bg-gradient-to-br from-blue-500 to-purple-600 text-white rounded-2xl shadow-xl hover:shadow-2xl transition-all overflow-hidden"
          >
            <div className="p-6">
              <div className="flex items-center justify-between mb-3">
                <ImageIcon className="w-12 h-12" />
                <span className="px-4 py-2 bg-white/20 backdrop-blur-sm rounded-full text-sm font-semibold">
                  Upload & Analyze
                </span>
              </div>
              <h3 className="text-2xl font-bold mb-2">Image Analysis</h3>
              <p className="text-blue-100 mb-4">
                Upload images for comprehensive AI-powered threat detection including deepfakes, identity verification, and object recognition
              </p>
              <div className="flex items-center space-x-4 text-sm">
                <span className="flex items-center">
                  <div className="w-2 h-2 bg-green-400 rounded-full mr-2"></div>
                  Deepfake Check
                </span>
                <span className="flex items-center">
                  <div className="w-2 h-2 bg-green-400 rounded-full mr-2"></div>
                  Face ID
                </span>
                <span className="flex items-center">
                  <div className="w-2 h-2 bg-green-400 rounded-full mr-2"></div>
                  Object Detect
                </span>
              </div>
            </div>
          </motion.a>

          <motion.a
            href="/video"
            whileHover={{ scale: 1.02, y: -2 }}
            whileTap={{ scale: 0.98 }}
            className="block bg-gradient-to-br from-purple-500 to-pink-600 text-white rounded-2xl shadow-xl hover:shadow-2xl transition-all overflow-hidden"
          >
            <div className="p-6">
              <div className="flex items-center justify-between mb-3">
                <Video className="w-12 h-12" />
                <span className="px-4 py-2 bg-white/20 backdrop-blur-sm rounded-full text-sm font-semibold">
                  Frame-by-Frame
                </span>
              </div>
              <h3 className="text-2xl font-bold mb-2">Video Analysis</h3>
              <p className="text-purple-100 mb-4">
                Process video files with frame sampling, risk timeline visualization, and comprehensive statistics tracking
              </p>
              <div className="flex items-center space-x-4 text-sm">
                <span className="flex items-center">
                  <div className="w-2 h-2 bg-yellow-400 rounded-full mr-2"></div>
                  Timeline Chart
                </span>
                <span className="flex items-center">
                  <div className="w-2 h-2 bg-yellow-400 rounded-full mr-2"></div>
                  Risk Stats
                </span>
                <span className="flex items-center">
                  <div className="w-2 h-2 bg-yellow-400 rounded-full mr-2"></div>
                  Frame Skip
                </span>
              </div>
            </div>
          </motion.a>

          <motion.a
            href="/live"
            whileHover={{ scale: 1.02, y: -2 }}
            whileTap={{ scale: 0.98 }}
            className="block bg-gradient-to-br from-red-500 to-orange-600 text-white rounded-2xl shadow-xl hover:shadow-2xl transition-all overflow-hidden"
          >
            <div className="p-6">
              <div className="flex items-center justify-between mb-3">
                <Camera className="w-12 h-12" />
                <span className="px-4 py-2 bg-white/20 backdrop-blur-sm rounded-full text-sm font-semibold flex items-center">
                  <div className="w-2 h-2 bg-red-300 rounded-full mr-2 animate-pulse"></div>
                  Live Feed
                </span>
              </div>
              <h3 className="text-2xl font-bold mb-2">CCTV Monitoring</h3>
              <p className="text-red-100 mb-4">
                Real-time webcam surveillance with instant threat alerts, continuous analysis, and live risk assessment dashboard
              </p>
              <div className="flex items-center space-x-4 text-sm">
                <span className="flex items-center">
                  <div className="w-2 h-2 bg-orange-400 rounded-full mr-2"></div>
                  Real-Time
                </span>
                <span className="flex items-center">
                  <div className="w-2 h-2 bg-orange-400 rounded-full mr-2"></div>
                  Auto Alerts
                </span>
                <span className="flex items-center">
                  <div className="w-2 h-2 bg-orange-400 rounded-full mr-2"></div>
                  Multi-Cam
                </span>
              </div>
            </div>
          </motion.a>

          <motion.a
            href="/database"
            whileHover={{ scale: 1.02, y: -2 }}
            whileTap={{ scale: 0.98 }}
            className="block bg-gradient-to-br from-green-500 to-teal-600 text-white rounded-2xl shadow-xl hover:shadow-2xl transition-all overflow-hidden"
          >
            <div className="p-6">
              <div className="flex items-center justify-between mb-3">
                <Users className="w-12 h-12" />
                <span className="px-4 py-2 bg-white/20 backdrop-blur-sm rounded-full text-sm font-semibold">
                  {faceCount} Registered
                </span>
              </div>
              <h3 className="text-2xl font-bold mb-2">Face Database</h3>
              <p className="text-green-100 mb-4">
                Manage identity database with photo upload, add/remove individuals, and maintain recognition profiles
              </p>
              <div className="flex items-center space-x-4 text-sm">
                <span className="flex items-center">
                  <div className="w-2 h-2 bg-teal-400 rounded-full mr-2"></div>
                  Add Identity
                </span>
                <span className="flex items-center">
                  <div className="w-2 h-2 bg-teal-400 rounded-full mr-2"></div>
                  Upload Photo
                </span>
                <span className="flex items-center">
                  <div className="w-2 h-2 bg-teal-400 rounded-full mr-2"></div>
                  Manage All
                </span>
              </div>
            </div>
          </motion.a>
        </motion.div>
      </div>

      {/* Technical Specifications */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 rounded-2xl shadow-2xl p-8 text-white"
      >
        <h2 className="text-3xl font-bold mb-6 flex items-center">
          <Zap className="w-8 h-8 mr-3 text-yellow-400" />
          Technical Specifications
        </h2>
        
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <div className="text-center p-4 bg-white/5 backdrop-blur-sm rounded-xl border border-white/10">
            <Brain className="w-10 h-10 text-blue-400 mx-auto mb-3" />
            <p className="text-3xl font-bold text-blue-400">95%+</p>
            <p className="text-sm text-gray-400 mt-1">Detection Accuracy</p>
          </div>
          
          <div className="text-center p-4 bg-white/5 backdrop-blur-sm rounded-xl border border-white/10">
            <Activity className="w-10 h-10 text-green-400 mx-auto mb-3" />
            <p className="text-3xl font-bold text-green-400">5-15</p>
            <p className="text-sm text-gray-400 mt-1">Frames Per Second</p>
          </div>
          
          <div className="text-center p-4 bg-white/5 backdrop-blur-sm rounded-xl border border-white/10">
            <Target className="w-10 h-10 text-purple-400 mx-auto mb-3" />
            <p className="text-3xl font-bold text-purple-400">80+</p>
            <p className="text-sm text-gray-400 mt-1">Object Classes</p>
          </div>
          
          <div className="text-center p-4 bg-white/5 backdrop-blur-sm rounded-xl border border-white/10">
            <Shield className="w-10 h-10 text-red-400 mx-auto mb-3" />
            <p className="text-3xl font-bold text-red-400">24/7</p>
            <p className="text-sm text-gray-400 mt-1">Monitoring Ready</p>
          </div>
        </div>

        <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white/5 backdrop-blur-sm rounded-xl p-6 border border-white/10">
            <h3 className="font-bold text-xl mb-4 text-blue-400">Tech Stack</h3>
            <ul className="space-y-2 text-sm text-gray-300">
              <li>• Frontend: React + Vite + Tailwind CSS</li>
              <li>• Backend: FastAPI (Python)</li>
              <li>• Deep Learning: PyTorch + Transformers</li>
              <li>• Detection: YOLOv8, InsightFace, ViT</li>
              <li>• Computer Vision: OpenCV, Pillow</li>
            </ul>
          </div>
          
          <div className="bg-white/5 backdrop-blur-sm rounded-xl p-6 border border-white/10">
            <h3 className="font-bold text-xl mb-4 text-purple-400">Use Cases</h3>
            <ul className="space-y-2 text-sm text-gray-300">
              <li>• Corporate security surveillance</li>
              <li>• Identity verification systems</li>
              <li>• Deepfake content detection</li>
              <li>• Threat & weapon identification</li>
              <li>• Access control monitoring</li>
            </ul>
          </div>
        </div>
      </motion.div>
    </div>
  )
}
