// @vitest-environment node
import { setupServer } from 'msw/node'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { startMockServer } from '@/test/live'
import { BeatClock } from '../beat'
import { FrameStore } from '../frames'
import { LiveClient } from '../live-client'
import { createLiveStore } from '../live-store'
import { api } from '../rest'
import { mockHandlers } from './handlers'

const SOCKET_URL = 'ws://localhost/ws'
let stop: () => void = () => {}

// Node has no page, so no location for rest.ts to resolve its paths against.
beforeEach(() => void vi.stubGlobal('location', new URL('http://localhost/next/live')))
afterEach(() => {
  stop()
  vi.unstubAllGlobals()
})

function serve(protocol: 1 | 2) {
  const server = startMockServer({ protocol })
  const msw = setupServer(...mockHandlers(server, SOCKET_URL))
  msw.listen({ onUnhandledRequest: 'error' })
  const store = createLiveStore()
  const frames = new FrameStore()
  const client = new LiveClient({ url: SOCKET_URL, store, frames, beatClock: new BeatClock() })
  client.start()
  stop = () => {
    client.stop()
    msw.close()
  }
  return { store, frames, client }
}

describe('MSW over the mock server', () => {
  it('serves the REST API through fetch', async () => {
    serve(2)
    const running = await api.running()
    expect(running.zones.map((zone) => zone.zoneId)).toEqual(['home', 'living', 'office'])
    expect(await api.recentLooks()).toEqual([])
    await expect(api.look('nope')).rejects.toMatchObject({ status: 404 })
  })

  it('speaks §12.4 to a LiveClient: snapshots, v2 frames and the beat', async () => {
    const { store, frames } = serve(2)
    await expect.poll(() => frames.live.size, { timeout: 3000 }).toBe(17)
    expect(store.getState().attention).toHaveLength(1)
    expect(store.getState().inputs?.music.state).toBe('connected')
    await expect.poll(() => store.getState().beat?.source, { timeout: 3000 }).toBe('music')
    expect(store.getState().beat?.bar).toBeGreaterThanOrEqual(42)
  })

  // Review focus 3: engine M1's protocol.
  it("speaks today's protocol to a LiveClient over MSW", async () => {
    const { store, frames, client } = serve(1)
    await expect.poll(() => frames.live.size, { timeout: 3000 }).toBe(21) // the PC as its five parts
    expect(frames.version).toBeGreaterThan(0)
    await expect.poll(() => store.getState().beat?.source, { timeout: 3000 }).toBe('prodjlink')
    expect(store.getState().beat).toMatchObject({ bar: null, bpm: 0, playing: false })
    expect(store.getState().decks).toBeNull()
    expect(store.getState().inputs).toBeNull()
    expect(client.malformedJson).toBe(0)
  })
})
