import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { Users, Upload, Loader, AlertCircle, UserPlus, Trash2, Camera } from 'lucide-react'
import { useDropzone } from 'react-dropzone'
import axios from 'axios'

export default function FaceDatabase() {
  const [identities, setIdentities] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [addingFace, setAddingFace] = useState(false)
  const [newName, setNewName] = useState('')
  const [newImage, setNewImage] = useState(null)
  const [imagePreview, setImagePreview] = useState(null)

  // Fetch identities
  const fetchIdentities = async () => {
    try {
      const response = await axios.get('http://localhost:8000/face/list?detailed=true')
      setIdentities(response.data.identities)
      setLoading(false)
    } catch (err) {
      setError('Failed to load identities. Make sure backend is running')
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchIdentities()
  }, [])

  const onDrop = useCallback((acceptedFiles) => {
    const file = acceptedFiles[0]
    if (file) {
      setNewImage(file)
      setImagePreview(URL.createObjectURL(file))
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/*': ['.png', '.jpg', '.jpeg'] },
    multiple: false,
  })

  const addIdentity = async () => {
    if (!newName || !newImage) return

    setAddingFace(true)
    setError(null)

    const formData = new FormData()
    formData.append('name', newName)
    formData.append('file', newImage)

    try {
      await axios.post('http://localhost:8000/face/add', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      
      // Reset form
      setNewName('')
      setNewImage(null)
      setImagePreview(null)
      
      // Refresh list
      await fetchIdentities()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add identity')
    } finally {
      setAddingFace(false)
    }
  }

  const removeIdentity = async (name) => {
    if (!confirm(`Remove ${name} from database?`)) return

    try {
      await axios.delete(`http://localhost:8000/face/${encodeURIComponent(name)}`)
      await fetchIdentities()
    } catch (err) {
      setError(`Failed to remove ${name}`)
    }
  }

  return (
    <div className="space-y-6">
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1 className="text-4xl font-bold bg-gradient-primary bg-clip-text text-transparent mb-2">
          Face Database
        </h1>
        <p className="text-gray-600">Manage registered identities for face recognition</p>
      </motion.div>

      {error && (
        <div className="bg-red-50 border-2 border-red-200 rounded-2xl p-4">
          <div className="flex items-start space-x-3">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
            <p className="text-red-700 text-sm">{error}</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Registered Identities */}
        <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-100">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-gray-900 flex items-center">
              <Users className="w-6 h-6 mr-2 text-primary-500" />
              Registered Identities
            </h2>
            <span className="bg-primary-100 text-primary-800 px-4 py-2 rounded-full font-bold">
              {identities.length}
            </span>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader className="w-8 h-8 text-primary-500 animate-spin" />
            </div>
          ) : identities.length === 0 ? (
            <div className="text-center py-12">
              <Users className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500">No identities registered yet</p>
              <p className="text-sm text-gray-400 mt-2">Add your first identity using the form →</p>
            </div>
          ) : (
            <div className="space-y-3 max-h-[600px] overflow-y-auto">
              {identities.map((identity, idx) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.05 }}
                  className="flex items-start justify-between p-4 bg-gradient-to-r from-blue-50 to-purple-50 rounded-xl hover:shadow-md transition-all"
                >
                  <div className="flex items-start space-x-3 flex-1">
                    {/* Photo or Avatar */}
                    {identity.photo_base64 ? (
                      <img 
                        src={`data:image/jpeg;base64,${identity.photo_base64}`}
                        alt={identity.name}
                        className="w-16 h-16 rounded-full object-cover border-2 border-primary-300"
                      />
                    ) : (
                      <div className="w-16 h-16 bg-gradient-primary rounded-full flex items-center justify-center text-white font-bold text-xl flex-shrink-0">
                        {identity.name.charAt(0).toUpperCase()}
                      </div>
                    )}
                    
                    {/* Details */}
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-gray-900 text-lg">{identity.name}</p>
                      <div className="mt-1 space-y-0.5 text-xs text-gray-600">
                        <p>📅 Added: {identity.added_date && identity.added_date !== 'Unknown' 
                          ? new Date(identity.added_date).toLocaleString('en-US', {
                              year: 'numeric',
                              month: 'short',
                              day: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit'
                            })
                          : 'Legacy Entry'}</p>
                        <p>👤 Approved by: {identity.approved_by}</p>
                        {identity.telegram_username && (
                          <p>📱 Telegram: @{identity.telegram_username} (ID: {identity.telegram_user_id})</p>
                        )}
                        {identity.telegram_first_name && !identity.telegram_username && (
                          <p>📱 Telegram: {identity.telegram_first_name} {identity.telegram_last_name || ''} (ID: {identity.telegram_user_id})</p>
                        )}
                        <p>📍 Location: {identity.camera_location}</p>
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={() => removeIdentity(identity.name)}
                    className="p-2 text-red-600 hover:bg-red-100 rounded-lg transition-colors"
                  >
                    <Trash2 className="w-5 h-5" />
                  </button>
                </motion.div>
              ))}
            </div>
          )}
        </div>

        {/* Add New Identity */}
        <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-100">
          <h2 className="text-2xl font-bold text-gray-900 mb-6 flex items-center">
            <UserPlus className="w-6 h-6 mr-2 text-green-600" />
            Add New Identity
          </h2>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Name / Identifier
              </label>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Enter person's name"
                className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-primary-500 focus:ring-2 focus:ring-primary-200 outline-none transition-all"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Face Photo
              </label>
              <div
                {...getRootProps()}
                className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
                  isDragActive
                    ? 'border-primary-500 bg-primary-50'
                    : 'border-gray-300 hover:border-primary-400 hover:bg-gray-50'
                }`}
              >
                <input {...getInputProps()} />
                {imagePreview ? (
                  <div>
                    <img src={imagePreview} alt="Preview" className="w-32 h-32 object-cover rounded-full mx-auto mb-3" />
                    <p className="text-sm text-gray-600">Click to change photo</p>
                  </div>
                ) : (
                  <>
                    <Camera className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                    <p className="text-sm font-semibold text-gray-700">
                      {isDragActive ? 'Drop photo here' : 'Click or drag photo'}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">Clear, front-facing photo</p>
                  </>
                )}
              </div>
            </div>

            <button
              onClick={addIdentity}
              disabled={!newName || !newImage || addingFace}
              className="w-full bg-gradient-to-r from-green-500 to-emerald-600 text-white py-4 rounded-xl font-semibold text-lg shadow-lg hover:shadow-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
            >
              {addingFace ? (
                <>
                  <Loader className="w-5 h-5 mr-2 animate-spin" />
                  Adding...
                </>
              ) : (
                <>
                  <UserPlus className="w-5 h-5 mr-2" />
                  Add to Database
                </>
              )}
            </button>

            <div className="bg-blue-50 rounded-xl p-4 mt-4">
              <h4 className="font-semibold text-blue-900 mb-2">Tips for best results:</h4>
              <ul className="text-sm text-blue-800 space-y-1">
                <li>• Use a clear, well-lit photo</li>
                <li>• Face should be front-facing</li>
                <li>• Remove glasses if possible</li>
                <li>• Avoid shadows on face</li>
                <li>• Use recent photo</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
