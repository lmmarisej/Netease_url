import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true
      },
      '/song': {
        target: 'http://localhost:5000',
        changeOrigin: true
      },
      '/search': {
        target: 'http://localhost:5000',
        changeOrigin: true
      },
      '/playlist': {
        target: 'http://localhost:5000',
        changeOrigin: true
      },
      '/album': {
        target: 'http://localhost:5000',
        changeOrigin: true
      },
      '/download': {
        target: 'http://localhost:5000',
        changeOrigin: true
      },
      '/sync': {
        target: 'http://localhost:5000',
        changeOrigin: true
      },
      '/health': {
        target: 'http://localhost:5000',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets'
  }
})
