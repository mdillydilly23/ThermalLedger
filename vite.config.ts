import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// ADR-005: MapLibre GL JS — no Mapbox token needed
// ADR-001: API proxy → backend:8000 so frontend never calls ML service directly
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // All /api/* calls proxied to backend — never directly to ML service
      '/api': {
        target: process.env.VITE_API_BASE_URL ?? 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
