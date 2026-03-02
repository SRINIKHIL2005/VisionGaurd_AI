import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiPort = env.VITE_API_PORT || '8000'
  const apiTarget = `http://localhost:${apiPort}`

  // All backend path prefixes — proxy them to FastAPI
  const apiPaths = ['/analyze', '/face', '/user', '/assistant', '/auth', '/health', '/stats', '/camera', '/stream']
  const proxy = Object.fromEntries(
    apiPaths.map(p => [p, { target: apiTarget, changeOrigin: true }])
  )

  return {
    plugins: [react()],
    server: {
      port: 3000,
      proxy,
    }
  }
})
