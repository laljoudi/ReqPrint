import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // In dev, the frontend (this server) and backend (FastAPI on :8000) are two
    // separate processes. This forwards any request to /api/... straight to
    // FastAPI, so the browser only ever talks to one origin - no CORS needed,
    // and it matches how production serves both from a single port.
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
})
