// MSW in the browser over a MockServer. main.tsx imports this only in dev and in the mock build.
import { setupWorker } from 'msw/browser'
import { liveSocketUrl } from '../live-client'
import type { MockChoice } from './choice'
import { mockHandlers } from './handlers'
import { MockServer } from './mock-server'

/**
 * e2e's sign that the stage has a picture of the effects in space to draw (e2e/helpers.ts, fxPictured()):
 * how many have gone out, and `data-mock-fx-preview` while the last has a preview's in it. A screenshot
 * waits until the stage has drawn that many (its canvas's `data-fx-drawn`, the pictures the fx store
 * stored), or it races the picture's arrival; a composer's, until a preview's picture went out first.
 */
let fxSent = 0
function markFx(preview: boolean): void {
  const page = document.documentElement
  page.toggleAttribute('data-mock-fx-preview', preview)
  page.setAttribute('data-mock-fx', String(++fxSent))
}

export async function startMocks(choice: MockChoice): Promise<MockServer> {
  const server = new MockServer({ ...choice, onFx: markFx })
  const worker = setupWorker(...mockHandlers(server, liveSocketUrl()))
  await worker.start({
    serviceWorker: { url: `${import.meta.env.BASE_URL}mockServiceWorker.js` },
    onUnhandledRequest: 'bypass',
    quiet: true,
  })
  server.start()
  return server
}
