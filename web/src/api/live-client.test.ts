import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fakeSockets, type FakeSocket } from '@/test/fake-socket'
import { HERO_NOW } from '@/test/live'
import { BeatClock } from './beat'
import { FrameStore, encodeFrame } from './frames'
import { LiveClient, backoffMs, liveSocketUrl, measuredFps } from './live-client'
import { createLiveStore, type LiveStore } from './live-store'

let store: LiveStore
let frames: FrameStore
let beatClock: BeatClock
let sockets: FakeSocket[]
let client: LiveClient
const onResync = vi.fn()

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(HERO_NOW)
  onResync.mockClear()
  store = createLiveStore()
  frames = new FrameStore()
  beatClock = new BeatClock()
  const fake = fakeSockets()
  sockets = fake.sockets
  client = new LiveClient({
    url: 'ws://test/ws',
    store,
    frames,
    beatClock,
    openSocket: fake.open,
    onResync,
    clock: () => Date.now() / 1000,
  })
})

afterEach(() => {
  client.stop()
})

const rgb = (...values: number[]) => new Uint8Array(values)
const now = () => Date.now() / 1000
const latest = () => sockets[sockets.length - 1]
const connection = () => store.getState().connection

/** The latest socket opens and the server greets it, as the backend does on connect. */
function welcome(socket = latest()) {
  socket.open()
  socket.say({ channel: 'transport', state: 'playing' })
}

/** The server acks the frame subscription: with protocol 2 for v2, bare for today's v1. */
function ackFrames(protocol?: 2, socket = latest()) {
  socket.say({
    channel: 'ack',
    id: socket.idOf('subscribe_frames'),
    action: 'subscribe_frames',
    ...(protocol === 2 ? { protocol: 2, fps: 60 } : {}),
  })
}

/** §12.4's beat at 120 BPM, a beat and a half into bar 42, sent now. */
const beatV2 = () => ({
  channel: 'beat', bpm: 120, beat_phase: 0.5, bar_phase: 0.375, bar: 42, beat_in_bar: 2,
  pitch_percent: 0, source: 'music', stale: false, server_time: now(),
})

/** `perSecond` new frames for a light, every second for `seconds`. */
function stream(version: 1 | 2, perSecond: number, seconds: number) {
  let seq = 1000
  for (let s = 0; s < seconds; s++) {
    for (let i = 0; i < perSecond; i++) latest().sayRaw(encodeFrame(version, 'rope', seq++, rgb(0, 0, 0)))
    vi.advanceTimersByTime(1000)
  }
}

describe('LiveClient', () => {
  it('is connecting until the server first speaks, then live', () => {
    client.start()
    expect(connection()).toEqual({ status: 'connecting' })
    latest().open()
    expect(connection()).toEqual({ status: 'connecting' })
    latest().say({ channel: 'transport', state: 'playing' })
    expect(connection()).toEqual({ status: 'live', fps: null })
    expect(store.getState().previewOnly).toBe(false)
  })

  // Review focus 1: no duplicate subscriptions (§14 Resilience). Live frames only: engine M2 keeps
  // a preview running while a tab watches its stream, so only F4's preview asks for it.
  it('subscribes to the beat and to the live frames, once per connection', () => {
    client.start()
    welcome()
    expect(latest().sent).toEqual([
      expect.objectContaining({ action: 'subscribe_beat', fps: 30 }),
      expect.objectContaining({ action: 'subscribe_frames', fps: 60, protocol: 2, streams: ['live'] }),
    ])
    latest().drop()
    vi.advanceTimersByTime(1000)
    welcome()
    expect(sockets).toHaveLength(2)
    expect(sockets[1].sent.map((command) => command.action)).toEqual(['subscribe_beat', 'subscribe_frames'])
  })

  // Review focus 1.
  it('drops to Reconnecting at once on a close, then retries after 1, 2, 4, 8, 10 and 10 s', () => {
    client.start()
    welcome()
    for (const [i, seconds] of [1, 2, 4, 8, 10, 10].entries()) {
      latest().drop()
      expect(connection()).toEqual({ status: 'reconnecting', attempt: i + 1 })
      const count = sockets.length
      vi.advanceTimersByTime(seconds * 1000 - 1)
      expect(sockets).toHaveLength(count)
      vi.advanceTimersByTime(1)
      expect(sockets).toHaveLength(count + 1)
    }
  })

  // Review focus 1: a server that hangs rather than closing.
  it('drops a link that has gone silent for 3 s', () => {
    client.start()
    welcome()
    vi.advanceTimersByTime(3000)
    expect(connection().status).toBe('live')
    vi.advanceTimersByTime(1000)
    expect(connection()).toEqual({ status: 'reconnecting', attempt: 1 })
    expect(sockets[0].closed).toBe(true)
  })

  it('gives up on a connection that never opens', () => {
    client.start()
    vi.advanceTimersByTime(4000)
    expect(connection()).toEqual({ status: 'reconnecting', attempt: 1 })
  })

  it('counts attempts from the first failure, and from 1 again after it was live for 3 s', () => {
    client.start()
    latest().drop()
    expect(connection()).toEqual({ status: 'reconnecting', attempt: 1 })
    vi.advanceTimersByTime(1000)
    welcome()
    for (let s = 0; s < 3; s++) {
      vi.advanceTimersByTime(1000)
      latest().say({ channel: 'attention', items: [] })
    }
    latest().drop()
    expect(connection()).toEqual({ status: 'reconnecting', attempt: 1 })
  })

  // M9: a server that accepts and then dies mustn't be retried every second, resyncing each time.
  it('keeps backing off a server that answers and then drops at once', () => {
    client.start()
    for (const [i, seconds] of [1, 2, 4].entries()) {
      welcome()
      latest().drop()
      expect(connection()).toEqual({ status: 'reconnecting', attempt: i + 1 })
      const count = sockets.length
      vi.advanceTimersByTime(seconds * 1000 - 1)
      expect(sockets).toHaveLength(count)
      vi.advanceTimersByTime(1)
    }
  })

  // M12: a tab that stalled (or a laptop that woke) runs its tick late; the stall isn't the server's.
  it('gives the link a tick of grace when the tick itself ran late', () => {
    client.start()
    welcome()
    vi.setSystemTime(Date.now() + 10_000)
    vi.advanceTimersByTime(1000)
    expect(connection().status).toBe('live')
    latest().say({ channel: 'attention', items: [] })
    vi.advanceTimersByTime(1000)
    expect(connection().status).toBe('live')
    vi.advanceTimersByTime(3000)
    expect(connection()).toEqual({ status: 'reconnecting', attempt: 1 })
  })

  // Review focus 1.
  it("keeps one socket: Try now opens one, and a dead socket's late messages are ignored", () => {
    client.start()
    welcome()
    const dead = sockets[0]
    dead.drop()
    client.retryNow()
    client.retryNow()
    expect(sockets).toHaveLength(2)
    welcome(sockets[1])
    vi.advanceTimersByTime(1000)
    expect(sockets).toHaveLength(2)
    dead.say({ channel: 'attention', items: [] })
    dead.drop()
    expect(store.getState().attention).toBeNull()
    expect(connection().status).toBe('live')
    client.retryNow()
    expect(sockets).toHaveLength(2)
  })

  // Review focus 1: a restarted server counts its frames from 1 again (§9.4, "Resync everything").
  it('resyncs on reconnect: seqs restart, the beat clock re-anchors and REST refetches', () => {
    client.start()
    welcome()
    ackFrames(2)
    latest().sayRaw(encodeFrame(2, 'rope', 500, rgb(1, 1, 1)))
    latest().say(beatV2())
    expect(beatClock.sample(now()).running).toBe(true)
    expect(onResync).not.toHaveBeenCalled()

    latest().drop()
    vi.advanceTimersByTime(1000)
    welcome()
    ackFrames(2)
    expect(onResync).toHaveBeenCalledTimes(1)
    expect(beatClock.sample(now()).running).toBe(false)
    // M7: the restarted server's count has reached 500 again, a seq the client last saw.
    latest().sayRaw(encodeFrame(2, 'rope', 500, rgb(2, 2, 2)))
    expect(frames.get('rope')).toMatchObject({ seq: 500, rgb: rgb(2, 2, 2) })
  })

  // Review focus 3: engine M1 acks without a protocol and sends v1 frames.
  it('falls back to v1 frames at 30 fps when the ack has no protocol', () => {
    client.start()
    welcome()
    latest().sayRaw(encodeFrame(1, 'rope', 1, rgb(9, 9, 9)))
    expect(frames.live.size).toBe(0) // before the ack, the version isn't known
    ackFrames()
    latest().sayRaw(encodeFrame(1, 'rope', 2, rgb(1, 2, 3)))
    expect(frames.get('rope')?.rgb).toEqual(rgb(1, 2, 3))
    stream(1, 60, 3)
    expect(connection()).toEqual({ status: 'live', fps: 30 })
  })

  it('reads v2 frames once the ack says protocol 2, and measures up to 60 fps', () => {
    client.start()
    welcome()
    ackFrames(2)
    latest().sayRaw(encodeFrame(2, 'rope', 1, rgb(4, 5, 6), 'preview'))
    expect(frames.get('rope', 'preview')?.rgb).toEqual(rgb(4, 5, 6))
    stream(2, 60, 3)
    expect(connection()).toEqual({ status: 'live', fps: 60 })
  })

  // M8: the first window after the first message is only part of a second.
  it('shows no frame rate for the part-second before its first full window', () => {
    client.start()
    vi.advanceTimersByTime(700)
    welcome()
    ackFrames(2)
    for (let seq = 1; seq <= 18; seq++) latest().sayRaw(encodeFrame(2, 'rope', seq, rgb(0, 0, 0)))
    vi.advanceTimersByTime(300)
    expect(connection()).toEqual({ status: 'live', fps: null })
    stream(2, 60, 1)
    expect(connection()).toEqual({ status: 'live', fps: 60 })
  })

  // M11: a server that refuses v2 frames would otherwise leave "Live" showing with none.
  it('asks for v1 frames when the server refuses v2, and only once', () => {
    client.start()
    welcome()
    latest().say({ channel: 'error', id: latest().idOf('subscribe_frames'), detail: 'Unknown frame protocol 2' })
    expect(latest().sent.at(-1)).toEqual({ action: 'subscribe_frames', id: expect.any(Number), fps: 30 })
    latest().say({ channel: 'error', id: latest().idOf('subscribe_frames'), detail: 'no frames today' })
    expect(latest().sent.filter((command) => command.action === 'subscribe_frames')).toHaveLength(2)
    latest().say({ channel: 'ack', id: latest().idOf('subscribe_frames'), action: 'subscribe_frames' })
    latest().sayRaw(encodeFrame(1, 'rope', 1, rgb(1, 2, 3)))
    expect(frames.get('rope')?.rgb).toEqual(rgb(1, 2, 3))
  })

  it("counts binary data that isn't an ArrayBuffer as malformed", () => {
    client.start()
    welcome()
    ackFrames(2)
    latest().sayRaw(new Blob([new Uint8Array(8)]))
    expect(frames.malformed).toBe(1)
  })

  // M16: F4's preview stream survives a reconnect, as the signals do.
  it('asks for the frame streams it was given, and again after a reconnect', () => {
    client.start()
    welcome()
    client.subscribeFrames(['live', 'preview'])
    expect(latest().sent.at(-1)).toMatchObject({ action: 'subscribe_frames', protocol: 2, streams: ['live', 'preview'] })
    latest().drop()
    vi.advanceTimersByTime(1000)
    welcome()
    expect(latest().sent).toEqual([
      expect.objectContaining({ action: 'subscribe_beat' }),
      expect.objectContaining({ action: 'subscribe_frames', streams: ['live', 'preview'] }),
    ])
  })

  it('shows no frame rate while no frames flow', () => {
    client.start()
    welcome()
    ackFrames(2)
    vi.advanceTimersByTime(2000)
    expect(connection()).toEqual({ status: 'live', fps: null })
  })

  // Review focus 5.
  it('drops bad JSON and counts it, and the next message still lands', () => {
    client.start()
    welcome()
    latest().sayRaw('{"channel":')
    latest().sayRaw('{"channel":"attention"}')
    expect(client.malformedJson).toBe(2)
    latest().say({ channel: 'attention', items: [] })
    expect(store.getState().attention).toEqual([])
  })

  it("feeds each beat to the beat clock, on the server's clock", () => {
    client.start()
    welcome()
    latest().say(beatV2())
    vi.advanceTimersByTime(250)
    expect(beatClock.sample(now())).toMatchObject({ bar: 42, beatInBar: 3, running: true })
  })

  it('subscribes to signals when asked, and again after a reconnect', () => {
    client.start()
    welcome()
    client.subscribeSignals(['loudness'])
    expect(latest().sent.at(-1)).toMatchObject({ action: 'subscribe_signals', names: ['loudness'] })
    latest().drop()
    vi.advanceTimersByTime(1000)
    welcome()
    expect(latest().sent.map((command) => command.action)).toEqual(['subscribe_beat', 'subscribe_frames', 'subscribe_signals'])
  })

  it('stops for good: it closes the socket and never retries', () => {
    client.start()
    welcome()
    client.stop()
    expect(sockets[0].closed).toBe(true)
    vi.advanceTimersByTime(60_000)
    expect(sockets).toHaveLength(1)
  })
})

describe('measuredFps', () => {
  it.each([
    [0, 60, 60, 60],
    [60, 59, 60, 60],
    [59, 61, 60, 60],
    [40, 44, 60, 42],
    [60, 60, 30, 30],
    [60, 0, 60, null],
  ])('(%i, %i, cap %i) is %s', (previous, current, cap, fps) => {
    expect(measuredFps(previous, current, cap)).toBe(fps)
  })
})

describe('backoffMs', () => {
  it.each([
    [1, 1000],
    [2, 2000],
    [3, 4000],
    [4, 8000],
    [5, 10_000],
    [9, 10_000],
  ])('waits before retry %i for %i ms', (attempt, ms) => {
    expect(backoffMs(attempt)).toBe(ms)
  })
})

describe('liveSocketUrl', () => {
  it("is the page's own /ws, secure when the page is", () => {
    expect(liveSocketUrl({ protocol: 'http:', host: 'localhost:5174' })).toBe('ws://localhost:5174/ws')
    expect(liveSocketUrl({ protocol: 'https:', host: 'example.test' })).toBe('wss://example.test/ws')
  })
})
