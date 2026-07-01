import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  base: '/admin',
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 8103,
    host: true,
    proxy: {
      '/api': {
        target: 'http://backend:8102',
        changeOrigin: true,
      },
    },
  },
})
