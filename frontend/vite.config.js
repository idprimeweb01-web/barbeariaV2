import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/static/cliente_portal/',
  build: {
    outDir: '../app/static/cliente_portal',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: 'index.js',
        chunkFileNames: 'chunk-[name].js',
        assetFileNames: 'assets/[name][extname]',
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:5000',
      '/pub': 'http://localhost:5000',
      '/sair': 'http://localhost:5000',
      '/entrar': 'http://localhost:5000',
      '/b': 'http://localhost:5000',
    },
  },
})
