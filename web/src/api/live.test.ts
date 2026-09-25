import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fakeSockets } from '@/test/fake-socket'
import { frames, liveClient, startDataLayer } from './live'
import { liveStore } from './live-store'
import { inMemorySockets } from './mocks/in-memory-socket'
import { MockServer } from './mocks/mock-server'

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date(2026, 8, 23, 19, 14))
})

afterEach(() => {
  liveClient()?.stop()
})

describe('startDataLayer', () => {
  it("fills the app's stores from the server", async () => {
    const server = new MockServer({ clock: () => Date.now(), wallClock: () => Date.now() })
    server.start()
    startDataLayer({ openSocket: inMemorySockets(server), url: 'mock' })
    await vi.advanceTimersByTimeAsync(1100)
    expect(liveStore.getState().attention).toHaveLength(1)
    expect(liveStore.getState().connection.status).toBe('live')
    expect(frames.live.size).toBeGreaterThan(0)
    server.stop()
  })

  it('keeps one client: starting again stops the first', () => {
    const { sockets, open } = fakeSockets()
    const first = startDataLayer({ openSocket: open, url: 'ws://test/ws' })
    const second = startDataLayer({ openSocket: open, url: 'ws://test/ws' })
    expect(second).not.toBe(first)
    expect(liveClient()).toBe(second)
    expect(sockets).toHaveLength(2)
    expect(sockets[0].closed).toBe(true)
  })
})
