import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { BeatClock } from '../beat'
import type { Look, RecentLook, Zone } from '../contract'
import { FrameStore, decodeFrame } from '../frames'
import { LiveClient } from '../live-client'
import { createLiveStore } from '../live-store'
import type { ClientCommand } from '../ws-messages'
import { inMemorySockets } from './in-memory-socket'
import { MockServer, RECENT_LIMIT, beatMessage, snapshotMessages, type MockServerOptions } from './mock-server'
import { buildScenario } from './scenarios'

const NOW = new Date(2026, 8, 23, 19, 14)
/** Moves the wall clock on: the mock's times come from Date.now(). */
const later = (minutes: number) => vi.setSystemTime(NOW.getTime() + minutes * 60_000)
let servers: MockServer[] = []

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(NOW)
})

afterEach(() => {
  for (const server of servers) server.stop()
  servers = []
})

function serve(options: MockServerOptions = {}) {
  const server = new MockServer({ scenario: 'hero', clock: () => Date.now(), wallClock: () => Date.now(), ...options })
  servers.push(server)
  server.start()
  return server
}

/** One socket to the server, recording what it hears. */
function connect(server: MockServer) {
  const heard: (string | ArrayBuffer)[] = []
  let closed = false
  const session = server.connect({ send: (data) => heard.push(data), close: () => (closed = true) })
  let id = 0
  return {
    session,
    heard,
    closed: () => closed,
    json: () => heard.filter((data): data is string => typeof data === 'string').map((text) => JSON.parse(text)),
    binary: () => heard.filter((data): data is ArrayBuffer => data instanceof ArrayBuffer),
    send: (command: Omit<ClientCommand, 'id'> | Record<string, unknown>) => {
      if (session !== null) server.receive(session, JSON.stringify({ ...command, id: ++id }))
    },
    clear: () => heard.splice(0),
  }
}

/** The frames heard, decoded as `version`. */
function decoded(frames: ArrayBuffer[], version: 1 | 2) {
  const store = new FrameStore()
  for (const frame of frames) decodeFrame(frame, version, store, 0)
  return store
}

describe('a connection', () => {
  it('hears the snapshots first, v2 adding decks and inputs', () => {
    expect(connect(serve()).json().map((message) => message.channel)).toEqual([
      'running', 'lights', 'attention', 'transport', 'decks', 'inputs',
    ])
    expect(connect(serve({ protocol: 1 })).json().map((message) => message.channel)).toEqual([
      'running', 'lights', 'attention', 'transport',
    ])
  })

  it('gets v2 frames at 60 fps once it asks with protocol 2, for the streaming lights only', () => {
    const socket = connect(serve())
    socket.clear()
    socket.send({ action: 'subscribe_frames', fps: 60, protocol: 2, streams: ['live', 'preview'] })
    expect(socket.json()).toEqual([{ channel: 'ack', id: 1, action: 'subscribe_frames', protocol: 2, fps: 60 }])
    vi.advanceTimersByTime(1000)
    const frames = decoded(socket.binary(), 2)
    expect(frames.malformed).toBe(0)
    expect(frames.live.size).toBe(17)
    expect(frames.live.has('rope')).toBe(false)
    expect(frames.live.has('candle2')).toBe(false)
    const fps = frames.sampleFps()
    expect(fps).toBeGreaterThanOrEqual(59)
    expect(fps).toBeLessThanOrEqual(61)
    expect(frames.preview.size).toBe(0)
  })

  it('speaks as engine M1 with protocol 1: a bare ack, v1 frames at 30 fps, and errors', () => {
    const socket = connect(serve({ protocol: 1 }))
    socket.clear()
    socket.send({ action: 'subscribe_frames', fps: 60, protocol: 2, streams: ['live'] })
    socket.send({ action: 'subscribe_signals' })
    expect(socket.json()).toEqual([
      { channel: 'ack', id: 1, action: 'subscribe_frames' },
      { channel: 'error', id: 2, detail: 'Unknown action: subscribe_signals' },
    ])
    vi.advanceTimersByTime(1000)
    const frames = decoded(socket.binary(), 1)
    expect(frames.malformed).toBe(0)
    expect(frames.live.size).toBe(17)
    expect(frames.sampleFps()).toBeLessThanOrEqual(31)
  })

  it('reads bad JSON as an error, as M1 does', () => {
    const server = serve()
    const socket = connect(server)
    socket.clear()
    if (socket.session !== null) server.receive(socket.session, '{"action":')
    expect(socket.json()).toEqual([{ channel: 'error', detail: 'Invalid JSON' }])
  })

  it('sends the beat at the rate asked, moving at the tempo', () => {
    const socket = connect(serve())
    socket.clear()
    socket.send({ action: 'subscribe_beat', fps: 30 })
    vi.advanceTimersByTime(1000)
    const beats = socket.json().filter((message) => message.channel === 'beat')
    expect(beats.length).toBeGreaterThanOrEqual(29)
    expect(beats.length).toBeLessThanOrEqual(31)
    const [first, last] = [beats[0], beats[beats.length - 1]]
    expect(first).toMatchObject({ source: 'music', bpm: 121.8, bar: 42, beat_in_bar: 2, stale: false })
    expect(first.beat_phase).toBeCloseTo(0.25, 1)
    const position = (beat: typeof first) => (beat.bar - 1) * 4 + (beat.beat_in_bar - 1) + beat.beat_phase
    expect(position(last) - position(first)).toBeCloseTo(((last.server_time - first.server_time) * 121.8) / 60, 2)
  })

  it('holds the beat for ?still: one beat after the ack, then none', () => {
    const socket = connect(serve({ still: true }))
    socket.clear()
    socket.send({ action: 'subscribe_beat', fps: 30 })
    vi.advanceTimersByTime(2000)
    expect(socket.json().filter((message) => message.channel === 'beat')).toHaveLength(1)
  })

  it('sends stats every second, and signals at 10 Hz once asked', () => {
    const socket = connect(serve())
    socket.clear()
    socket.send({ action: 'subscribe_signals', names: ['loudness'] })
    vi.advanceTimersByTime(1010)
    const channels = socket.json().map((message) => message.channel)
    expect(channels.filter((channel) => channel === 'stats')).toHaveLength(1)
    const signals = socket.json().filter((message) => message.channel === 'signals')
    expect(signals.length).toBeGreaterThanOrEqual(9)
    expect(Object.keys(signals[0].values)).toEqual(['loudness'])
  })

  it("drops every session after the scenario's dropAfterMs, and refuses new ones", () => {
    const server = serve({ scenario: 'reconnecting' })
    const socket = connect(server)
    vi.advanceTimersByTime(999)
    expect(socket.closed()).toBe(false)
    vi.advanceTimersByTime(20)
    expect(socket.closed()).toBe(true)
    expect(connect(server).session).toBeNull()
  })
})

describe('the REST API', () => {
  it('starts a look with take-over, and pushes running and lights', () => {
    const server = serve()
    const socket = connect(server)
    socket.clear()
    const reply = server.handle('POST', '/api/zones/bedroom/start', { lookId: 'sunset' })
    expect(reply.status).toBe(200)
    const body = reply.body as { zoneId: string; takeOvers: { zoneId: string; lights: string[]; stopped: boolean }[] }
    expect(body.zoneId).toBe('bedroom')
    expect(body.takeOvers).toEqual([
      expect.objectContaining({ zoneId: 'home', lights: ['bedl', 'bedr'], stopped: false }),
      expect.objectContaining({ zoneId: 'office', lights: ['deskl', 'deskr', 'pc'], stopped: true }),
    ])
    expect(server.state.running.map((zone) => zone.zoneId)).toEqual(['home', 'living', 'bedroom'])
    expect(server.state.running[0].lights).not.toContain('bedl')
    expect(socket.json().map((message) => message.channel)).toEqual(['running', 'lights'])
  })

  it('turns a zone off again and again, and says 404 for a zone it does not know', () => {
    const server = serve()
    expect(server.handle('POST', '/api/zones/living/off').status).toBe(204)
    expect(server.state.running.map((zone) => zone.zoneId)).toEqual(['home', 'office'])
    expect(server.state.lights.find((light) => light.id === 'rcl')?.status).toBe('idle')
    expect(server.handle('POST', '/api/zones/living/off').status).toBe(204)
    expect(server.handle('POST', '/api/zones/nope/off')).toEqual({ status: 404, body: { detail: "No zone 'nope'" } })
  })

  it('refuses to change a built-in look, and saves a new one', () => {
    const server = serve()
    const fireflies = server.state.looks.find((look) => look.id === 'fireflies')
    expect(server.handle('PUT', '/api/looks/fireflies', fireflies).status).toBe(409)
    const saved = server.handle('POST', '/api/looks', { ...fireflies, name: 'Mine', derivedFrom: 'fireflies' })
    expect(saved.status).toBe(201)
    expect(saved.body).toMatchObject({ name: 'Mine', builtIn: false, derivedFrom: 'fireflies' })
    expect(server.handle('GET', `/api/looks/${(saved.body as { id: string }).id}`).status).toBe(200)
  })

  it("streams a preview on the preview stream only, and leaves the lights alone", () => {
    const server = serve()
    const socket = connect(server)
    socket.send({ action: 'subscribe_frames', fps: 60, protocol: 2, streams: ['live', 'preview'] })
    const lights = JSON.stringify(server.state.lights)
    const reply = server.handle('POST', '/api/preview', { zoneId: 'living', lookId: 'embers' })
    expect(reply.body).toEqual({ previewId: expect.any(String) })
    vi.advanceTimersByTime(500)
    const frames = decoded(socket.binary(), 2)
    expect(frames.preview.size).toBe(server.state.zones.find((zone) => zone.id === 'living')?.lights.length)
    expect(JSON.stringify(server.state.lights)).toBe(lights)
    const id = (reply.body as { previewId: string }).previewId
    expect(server.handle('DELETE', `/api/preview/${id}`).status).toBe(204)
    socket.clear()
    vi.advanceTimersByTime(500)
    expect(decoded(socket.binary(), 2).preview.size).toBe(0)
  })

  it('puts preview only on through the config, and pushes transport', () => {
    const server = serve()
    const socket = connect(server)
    socket.clear()
    expect(server.handle('PUT', '/api/config', { engine: { preview_only: true } }).status).toBe(200)
    expect(socket.json()).toEqual([{ channel: 'transport', state: 'simulating' }])
    expect(server.handle('PUT', '/api/config', { engine: { preview_only: 'yes' } }).status).toBe(400)
  })

  it('answers what it does not serve with 404 Not Found', () => {
    expect(serve().handle('GET', '/api/nope')).toEqual({ status: 404, body: { detail: 'Not Found' } })
  })
})

describe('"Start again"', () => {
  const listed = (server: MockServer) =>
    (server.handle('GET', '/api/running/recent').body as RecentLook[]).map((entry) => `${entry.zoneId}/${entry.lookId}`)
  const kept = (server: MockServer) => server.state.recent.map((entry) => `${entry.zoneId}/${entry.lookId}`)

  it("serves nothing-running's list, and leaves out what one tap could not start again", () => {
    const server = serve({ scenario: 'nothing-running' })
    expect(server.handle('GET', '/api/running/recent')).toEqual({ status: 200, body: server.state.recent })
    expect(listed(server)).toEqual(['home/goodnight', 'living/fireflies', 'home/homesunset'])

    server.handle('POST', '/api/zones/living/start', { lookId: 'fireflies' })
    expect(listed(server)).toEqual(['home/goodnight', 'home/homesunset']) // it runs there now

    const group = server.handle('POST', '/api/zones/groups', { name: 'Pair', lights: ['deskl'] }).body as Zone
    later(1)
    server.handle('POST', `/api/zones/${group.id}/start`, { lookId: 'comets' })
    later(2)
    server.handle('POST', `/api/zones/${group.id}/off`)
    expect(listed(server)[0]).toBe(`${group.id}/comets`)
    server.handle('DELETE', `/api/zones/groups/${group.id}`)
    expect(listed(server)).toEqual(['home/goodnight', 'home/homesunset']) // the zone is gone

    const fireflies = server.state.looks.find((look) => look.id === 'fireflies')
    const mine = server.handle('POST', '/api/looks', { ...fireflies, name: 'Mine' }).body as Look
    later(3)
    server.handle('POST', '/api/zones/office/start', { lookId: mine.id })
    later(4)
    server.handle('POST', '/api/zones/office/off')
    expect(listed(server)[0]).toBe(`office/${mine.id}`)
    server.handle('DELETE', `/api/looks/${mine.id}`)
    expect(listed(server)).toEqual(['home/goodnight', 'home/homesunset']) // the look is gone
    expect(kept(server)).toHaveLength(5) // left out when read, never forgotten
  })

  it('remembers each way a look stops, newest first, but not a draft or a deleted group', () => {
    const server = serve() // the hero: Home sunset, Fireflies and Twin comets run
    const embers = server.state.looks.find((look) => look.id === 'embers')
    later(1)
    server.handle('POST', '/api/zones/bedroom/start', { lookId: 'sunset' }) // takes all of the office's lights
    later(2)
    server.handle('POST', '/api/zones/living/start', { lookId: 'embers' }) // replaces Fireflies
    later(3)
    server.handle('POST', '/api/zones/living/off')
    later(4)
    server.handle('POST', '/api/zones/living/start', { look: { ...embers, id: '', name: 'Draft' } })
    later(5)
    server.handle('POST', '/api/running/stop-all')
    const group = server.handle('POST', '/api/zones/groups', { name: 'Pair', lights: ['deskl'] }).body as Zone
    server.handle('POST', `/api/zones/${group.id}/start`, { lookId: 'comets' })
    server.handle('DELETE', `/api/zones/groups/${group.id}`)

    expect(kept(server)).toEqual([
      'bedroom/sunset', // Stop all stopped these two together: the newer start first
      'home/homesunset',
      'living/embers',
      'living/fireflies',
      'office/comets',
    ])
    expect(server.state.recent[0]).toMatchObject({
      startedAt: new Date(NOW.getTime() + 60_000).toISOString(),
      stoppedAt: new Date(NOW.getTime() + 5 * 60_000).toISOString(),
    })
  })

  it('keeps one entry per zone and look, with its newest stop, and at most RECENT_LIMIT', () => {
    const server = serve({ scenario: 'nothing-running' })
    const looks = server.state.looks.slice(0, RECENT_LIMIT + 2)
    looks.forEach((look, index) => {
      later(index + 1)
      server.handle('POST', '/api/zones/office/start', { lookId: look.id }) // replaces the one before
    })
    later(RECENT_LIMIT + 3)
    server.handle('POST', '/api/zones/office/off')
    expect(kept(server)).toEqual(looks.slice(2).reverse().map((look) => `office/${look.id}`))

    later(RECENT_LIMIT + 4)
    server.handle('POST', '/api/zones/office/start', { lookId: looks[2].id })
    later(RECENT_LIMIT + 5)
    server.handle('POST', '/api/zones/office/off')
    expect(server.state.recent).toHaveLength(RECENT_LIMIT)
    expect(kept(server).filter((pair) => pair === `office/${looks[2].id}`)).toHaveLength(1)
    expect(server.state.recent[0]).toMatchObject({ lookId: looks[2].id, stoppedAt: new Date().toISOString() })
  })
})

describe('the messages', () => {
  it("sends today's beat as M1 does: bpm 0 with no DJ, Player 2's beat with one", () => {
    const hero = buildScenario('hero', NOW)
    expect(beatMessage(hero, 1, 0, 1)).toMatchObject({ bpm: 0, is_playing: false, deck_number: null })
    const dj = buildScenario('dj-playing', NOW)
    expect(beatMessage(dj, 0, 0, 1)).toMatchObject({ is_playing: true, beat_pos: 3, deck_number: 2, deck_name: 'Player 2' })
  })

  it('snapshots the transport as simulating while preview only is on', () => {
    const messages = snapshotMessages(buildScenario('preview-only', NOW), 2)
    expect(messages).toContainEqual({ channel: 'transport', state: 'simulating' })
  })
})

describe('the in-memory socket', () => {
  it('runs a LiveClient against the mock, with no MSW', async () => {
    const server = serve()
    const store = createLiveStore()
    const frames = new FrameStore()
    const client = new LiveClient({
      url: 'mock',
      store,
      frames,
      beatClock: new BeatClock(),
      openSocket: inMemorySockets(server),
      clock: () => Date.now() / 1000,
    })
    client.start()
    // Async: the socket delivers in microtasks, which run between the timers.
    await vi.advanceTimersByTimeAsync(2000)
    expect(store.getState().connection).toEqual({ status: 'live', fps: 60 })
    expect(store.getState().attention).toHaveLength(1)
    expect(frames.live.size).toBe(17)
    client.stop()
  })
})
