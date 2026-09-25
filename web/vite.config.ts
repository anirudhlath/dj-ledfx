import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { fileURLToPath, URL } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import type { Plugin } from 'vite'
import { defineConfig } from 'vitest/config'

const WORKER = 'mockServiceWorker.js'

/**
 * MSW's service worker, straight from the installed package, at `${base}mockServiceWorker.js`: served
 * in dev and emitted into the mock build. Production never has it (decision 11), and
 * scripts/check-dist.ts fails a build that it reached.
 */
function mswWorker(): Plugin {
  const source = () => readFileSync(createRequire(import.meta.url).resolve(`msw/${WORKER}`), 'utf8')
  let base = '/'
  return {
    name: 'msw-worker',
    apply: (_, { mode }) => mode !== 'production',
    configResolved(config) {
      base = config.base
    },
    configureServer(server) {
      server.middlewares.use(`${base}${WORKER}`, (_, response) => {
        response.setHeader('Content-Type', 'text/javascript')
        response.end(source())
      })
    },
    generateBundle() {
      this.emitFile({ type: 'asset', fileName: WORKER, source: source() })
    },
  }
}

// Served by FastAPI at /next until the F11 cut-over (engine spec §10). `--mode mock` builds the app
// with its mocks into dist-mock for Playwright.
export default defineConfig(({ mode }) => ({
  base: '/next/',
  plugins: [react(), tailwindcss(), mswWorker()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
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
