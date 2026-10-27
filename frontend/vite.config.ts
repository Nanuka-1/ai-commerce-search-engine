import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Виджет чата TopSport (F4). В разработке запросы /chat и /promo уходят на наш FastAPI (uvicorn :8000) —
// поэтому без CORS: для браузера это один адрес localhost:5173.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/chat': 'http://127.0.0.1:8000',
      '/promo': 'http://127.0.0.1:8000',
    },
  },
})
