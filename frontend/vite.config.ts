import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/arena': 'http://localhost:8000',
      '/generations': 'http://localhost:8000',
      '/attacks': 'http://localhost:8000',
      '/defenses': 'http://localhost:8000',
      '/episodes': 'http://localhost:8000',
      '/harnesses': 'http://localhost:8000',
      '/memory': 'http://localhost:8000',
      '/model-calls': 'http://localhost:8000',
      '/patches': 'http://localhost:8000',
      '/red-versions': 'http://localhost:8000',
      '/blue-versions': 'http://localhost:8000',
      '/attack-candidates': 'http://localhost:8000',
      '/replay': 'http://localhost:8000',
      '/runs': 'http://localhost:8000',
      '/scenarios': 'http://localhost:8000',
      '/system': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
})
