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
      '^/api/': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
        timeout: 120000
      },
      '/health': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true
      }
    },
    middlewareMode: false,
    historyApiFallback: true
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets'
  }
})
