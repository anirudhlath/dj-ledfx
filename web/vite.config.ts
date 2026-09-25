import { fileURLToPath, URL } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Served by FastAPI at /next until the F11 cut-over (engine spec §10). `--mode mock` builds the app
// with its mocks into dist-mock for Playwright. Only dev and that build get MSW's worker from
// public/; production has no public dir (decision 11).
export default defineConfig(({ mode }) => ({
  base: '/next/',
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  publicDir: mode === 'production' ? false : 'public',
  build: { outDir: mode === 'mock' ? 'dist-mock' : 'dist' },
  server: {
    port: 5174,
    strictPort: true,
    proxy: {
      '/api': 'http://localhost:8080',
      '/ws': { target: 'ws://localhost:8080', ws: true },
    },
  },
  // No proxy for preview (it would default to server.proxy): e2e runs with no backend, and never
  // reaches a server on :8080, the deployed app included.
  preview: { port: 4174, strictPort: true, proxy: {} },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    // A spy (a muted console.error, say) ends with the test that made it, and so does a stubbed global.
    restoreMocks: true,
    unstubGlobals: true,
  },
}))
