// MSW in the browser over a MockServer. main.tsx imports this only in dev and in the mock build.
import { setupWorker } from 'msw/browser'
import { liveSocketUrl } from '../live-client'
import type { MockChoice } from './choice'
import { mockHandlers } from './handlers'
import { MockServer } from './mock-server'

export async function startMocks(choice: MockChoice): Promise<MockServer> {
  const server = new MockServer(choice)
  const worker = setupWorker(...mockHandlers(server, liveSocketUrl()))
  await worker.start({
    serviceWorker: { url: `${import.meta.env.BASE_URL}mockServiceWorker.js` },
    onUnhandledRequest: 'bypass',
    quiet: true,
  })
  server.start()
  return server
}
