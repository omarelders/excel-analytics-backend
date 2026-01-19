import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/upload': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
      '/shipments': 'http://127.0.0.1:8000',
      '/payments': 'http://127.0.0.1:8000',
      '/statuses': 'http://127.0.0.1:8000',
      // Use /api/analytics for the API to avoid conflict with frontend route
      '/api/analytics': 'http://127.0.0.1:8000',
    }
  }
})
