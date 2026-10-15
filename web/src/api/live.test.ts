import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fakeSockets } from '@/test/fake-socket'
import { HERO_NOW, startMockDataLayer } from '@/test/live'
import { frames, fx, liveClient, resetDataLayer, startDataLayer, wantFx } from './live'
import { liveStore } from './live-store'
import { buildScenario } from './mocks/scenarios'
import { queries, queryClient } from './queries'

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(HERO_NOW)
})

describe('startDataLayer', () => {
  it("fills the app's stores from the server", async () => {
    startMockDataLayer()
    await vi.advanceTimersByTimeAsync(1100)
    expect(liveStore.getState().attention).toHaveLength(1)
    expect(liveStore.getState().connection.status).toBe('live')
    expect(frames.live.size).toBeGreaterThan(0)
  })

  // I6: a zone made on another device reaches this one's zones.
  it('refetches the zones when what runs names one REST never served', () => {
    const { open } = fakeSockets()
    startDataLayer({ openSocket: open, url: 'ws://test/ws' })
    queryClient.setQueryData(queries.zones().queryKey, [])
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
    liveStore.setState({ running: { zones: [{ ...buildScenario('hero').running[0], zoneId: 'group-9' }], overlays: [] } })
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['zones'] })
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

// F10 decision 2: the fx channel is on while any stage wants it.
describe('wantFx', () => {
  const fxCommands = (socket: { sent: { action: string }[] }) => socket.sent.filter((command) => command.action === 'subscribe_fx')

  it('asks for the fx channel while anything wants it, and lets go once nothing does', () => {
    const { sockets, open } = fakeSockets()
    startDataLayer({ openSocket: open, url: 'ws://test/ws' })
    sockets[0].open()
    const first = wantFx()
    const second = wantFx()
    first()
    first()
    expect(fxCommands(sockets[0])).toEqual([expect.objectContaining({ on: true })])
    second()
    expect(fxCommands(sockets[0])).toEqual([expect.objectContaining({ on: true }), expect.objectContaining({ on: false })])
  })

  it('carries a want over to a client started after it', () => {
    const release = wantFx()
    const { sockets, open } = fakeSockets()
    startDataLayer({ openSocket: open, url: 'ws://test/ws' })
    sockets[0].open()
    expect(fxCommands(sockets[0])).toEqual([expect.objectContaining({ on: true })])
    release()
  })

  // Every test ends with a reset: a stage unmounted after it lets go of nothing a later one wants.
  it("lets a want from before a reset go without touching a later one's", () => {
    const stale = wantFx()
    resetDataLayer()
    const { sockets, open } = fakeSockets()
    startDataLayer({ openSocket: open, url: 'ws://test/ws' })
    sockets[0].open()
    const release = wantFx()
    stale()
    expect(fxCommands(sockets[0])).toEqual([expect.objectContaining({ on: true })])
    release()
  })

  it("hears the mock hero's picture once asked", async () => {
    const release = wantFx()
    startMockDataLayer()
    await vi.advanceTimersByTimeAsync(1100)
    expect([...fx.live.keys()].sort()).toEqual(['living', 'office'])
    release()
  })
})
