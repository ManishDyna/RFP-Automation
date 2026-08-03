import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  // App is served under the "/rfp" path prefix (shared domain with COA).
  base: '/rfp/',
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 3000,
    // allowedHosts: ['be-aramco-01.bahra-cables.com'],
    // The SPA now calls /rfp/api, /rfp/dashboard, /rfp/upload. Strip the /rfp
    // prefix before forwarding to the backend (which still serves /api,
    // /dashboard, /upload) — this mirrors the prod reverse proxy.
    proxy: {
      '/rfp/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/rfp/, ''),
      },
      '/rfp/dashboard': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/rfp/, ''),
        bypass(req) {
          // Only proxy API calls (fetch/XHR), not browser page navigations
          if (req.headers.accept?.includes('text/html')) {
            return req.url
          }
        },
      },
      '/rfp/upload': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/rfp/, ''),
      },
    },
  },
})
