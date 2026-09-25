// The one link to the server (spec §12.4, §9.4). It subscribes once per connection, stores what the
// server says (the live store) and the frames it streams (the FrameStore), and feeds the beat clock.
// When the link drops it says so at once and retries after 1, 2, 4 and 8 s, then every 10 s. On
// the way back it resyncs: frame seqs, the beat clock, and REST data through onResync.
import { ClockOffset, clientNow, normaliseBeat, type BeatClock } from './beat'
import type { FrameStream } from './contract'
import { decodeFrame, type FrameStore, type FrameVersion } from './frames'
import { applyMessage, type LiveStore } from './live-store'
import { parseMessage, type Command } from './ws-messages'

const BACKOFF_S = [1, 2, 4, 8, 10]
/**
 * A link silent this long is dead: the server sends stats every second. A link live this long
 * has held, so a drop after it starts the backoff from 1 s again.
 */
const SILENCE_MS = 3000
const BEAT_FPS = 30
const FRAME_FPS = 60
/** The most a v1 link (engine M1) sends. */
const V1_FRAME_FPS = 30
const TICK_MS = 1000

/** What the client needs of a WebSocket. The browser's WebSocket is one. */
export interface LiveSocket {
  binaryType: BinaryType
  send(data: string): void
  close(code?: number, reason?: string): void
  onopen: ((event: Event) => void) | null
  onmessage: ((event: MessageEvent) => void) | null
  onclose: ((event: CloseEvent) => void) | null
  onerror: ((event: Event) => void) | null
}
export type OpenSocket = (url: string) => LiveSocket
const openWebSocket: OpenSocket = (url) => new WebSocket(url)

/** The page's own /ws, which the Vite proxy and FastAPI both serve. */
export function liveSocketUrl(location: Pick<Location, 'protocol' | 'host'> = window.location): string {
  return `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws`
}

/** How long to wait before retry `attempt` (1, 2, …). */
export function backoffMs(attempt: number): number {
  return BACKOFF_S[Math.min(attempt, BACKOFF_S.length) - 1] * 1000
}

/** Decision 3: this second's count and the last's, averaged and capped; null when no frames flow. */
export function measuredFps(previous: number, current: number, cap: number): number | null {
  if (current === 0) return null
  return Math.min(cap, previous > 0 ? Math.round((previous + current) / 2) : current)
}

export interface LiveClientOptions {
  url: string
  store: LiveStore
  frames: FrameStore
  beatClock: BeatClock
  openSocket?: OpenSocket
  /** After a reconnect: fetch again what REST loaded (resync() in queries.ts). */
  onResync?: () => void
  /** Seconds on a clock that only moves forward (clientNow). Tests pass their own. */
  clock?: () => number
}

export class LiveClient {
  /** JSON messages dropped as malformed: bad JSON, no channel, a snapshot missing its list. */
  malformedJson = 0
  private readonly url: string
  private readonly store: LiveStore
  private readonly frames: FrameStore
  private readonly beatClock: BeatClock
  private readonly openSocket: OpenSocket
  private readonly onResync: () => void
  private readonly clock: () => number
  private readonly offset = new ClockOffset()
  private socket: LiveSocket | null = null
  private opened = false
  private heard = false
  private everLive = false
  private attempt = 0
  private frameAckId: number | null = null
  /** The frame subscription awaiting its answer asked for v2, so a refusal can ask for v1. */
  private frameAskV2 = false
  private frameVersion: FrameVersion | null = null
  private frameCap = V1_FRAME_FPS
  /** Last second's frame count; null while the first window since the link came up is partial. */
  private lastWindow: number | null = null
  private liveSince = 0
  private lastHeardAt = 0
  private lastTickAt = 0
  private nextId = 1
  private streams: FrameStream[] = ['live']
  private signals: string[] | null = null
  private retryTimer: ReturnType<typeof setTimeout> | null = null
  private tickTimer: ReturnType<typeof setInterval> | null = null

  constructor(options: LiveClientOptions) {
    this.url = options.url
    this.store = options.store
    this.frames = options.frames
    this.beatClock = options.beatClock
    this.openSocket = options.openSocket ?? openWebSocket
    this.onResync = options.onResync ?? (() => {})
    this.clock = options.clock ?? clientNow
  }

  start(): void {
    if (this.tickTimer !== null) return
    this.lastTickAt = this.clock()
    this.tickTimer = setInterval(() => this.tick(), TICK_MS)
    this.connect()
  }

  stop(): void {
    if (this.tickTimer !== null) clearInterval(this.tickTimer)
    if (this.retryTimer !== null) clearTimeout(this.retryTimer)
    this.tickTimer = null
    this.retryTimer = null
    const socket = this.socket
    this.detach()
    socket?.close()
  }

  /** §9.4's "Try now": retry at once rather than wait out the backoff. */
  retryNow(): void {
    if (this.tickTimer === null || this.socket !== null) return
    if (this.retryTimer !== null) clearTimeout(this.retryTimer)
    this.retryTimer = null
    this.connect()
  }

  /**
   * The frame streams: `live` alone until F4 opens a preview, then `preview` too while it's open
   * (engine M2 ends a preview nobody watches, its Spec Ruling 9). Asked again after a reconnect.
   */
  subscribeFrames(streams: FrameStream[]): void {
    this.streams = streams
    if (this.opened) this.sendFrames()
  }

  /** The `signals` channel (F6, F8): these names, or every signal. Sent again after a reconnect. */
  subscribeSignals(names: string[] = []): void {
    this.signals = names
    if (this.opened) this.sendSignals(names)
  }

  private connect(): void {
    const socket = this.openSocket(this.url)
    socket.binaryType = 'arraybuffer'
    this.socket = socket
    this.opened = false
    this.heard = false
    this.frameAckId = null
    this.lastHeardAt = this.clock()
    socket.onopen = () => {
      if (this.socket === socket) this.subscribe()
    }
    socket.onmessage = (event) => {
      if (this.socket === socket) this.receive(event.data)
    }
    socket.onclose = () => this.drop(socket)
    socket.onerror = () => this.drop(socket)
  }

  private subscribe(): void {
    this.opened = true
    this.send({ action: 'subscribe_beat', fps: BEAT_FPS })
    this.sendFrames()
    if (this.signals !== null) this.sendSignals(this.signals)
  }

  private sendFrames(): void {
    this.frameAckId = this.send({ action: 'subscribe_frames', fps: FRAME_FPS, protocol: 2, streams: this.streams })
    this.frameAskV2 = true
  }

  private sendSignals(names: string[]): void {
    this.send(names.length > 0 ? { action: 'subscribe_signals', names } : { action: 'subscribe_signals' })
  }

  private send(command: Command): number {
    const id = this.nextId++
    this.socket?.send(JSON.stringify({ ...command, id }))
    return id
  }

  private receive(data: unknown): void {
    const now = this.clock()
    this.lastHeardAt = now
    if (!this.heard) this.firstWord(now)
    else if (this.attempt > 0 && now - this.liveSince >= SILENCE_MS / 1000) this.attempt = 0
    if (typeof data === 'string') this.receiveText(data, now)
    // binaryType is 'arraybuffer', so anything else is a server's mistake.
    else if (!(data instanceof ArrayBuffer)) this.frames.reject()
    // A frame before the ack is dropped: its version isn't known yet (decision 1).
    else if (this.frameVersion !== null) decodeFrame(data, this.frameVersion, this.frames, now)
  }

  /**
   * The first message on a socket: the link is live. After a drop, that's a reconnect. The backoff
   * starts again only once the link has held for SILENCE_MS: a server that answers and then dies
   * mustn't be retried, and resynced, every second.
   */
  private firstWord(now: number): void {
    this.heard = true
    this.liveSince = now
    if (this.everLive) {
      // The server may have restarted: seqs count from 1 again, the beat re-anchors, and REST data
      // is fetched again (§9.4, "Resync everything on reconnect").
      this.frames.resetSeqs()
      this.beatClock.reset()
      this.offset.reset()
      this.onResync()
    }
    this.everLive = true
    this.lastWindow = null
    this.store.setState({ connection: { status: 'live', fps: null } })
  }

  private receiveText(text: string, now: number): void {
    const message = parseMessage(text)
    if (message === null) {
      this.malformedJson += 1
      return
    }
    if (message.channel === 'ack' && message.id === this.frameAckId) {
      this.frameVersion = message.protocol === 2 ? 2 : 1
      this.frameCap = this.frameVersion === 2 ? Math.min(FRAME_FPS, message.fps ?? FRAME_FPS) : V1_FRAME_FPS
      return
    }
    if (message.channel === 'error' && message.id === this.frameAckId && this.frameAskV2) {
      // Refused v2 frames: ask for today's instead, once, rather than show Live with none.
      this.frameAckId = this.send({ action: 'subscribe_frames', fps: V1_FRAME_FPS })
      this.frameAskV2 = false
      return
    }
    if (message.channel === 'beat') {
      // The store and the clock share the one Beat.
      const beat = normaliseBeat(message, now)
      this.store.setState({ beat })
      if (beat.serverTime !== null) this.offset.add(beat.serverTime, now)
      this.beatClock.receive(beat, this.offset.value)
      return
    }
    applyMessage(this.store, message, now)
  }

  private drop(socket: LiveSocket): void {
    if (this.socket !== socket) return // an old socket's late close
    this.detach()
    socket.close()
    if (this.tickTimer === null) return
    this.attempt += 1
    this.store.setState({ connection: { status: 'reconnecting', attempt: this.attempt } })
    this.retryTimer = setTimeout(() => {
      this.retryTimer = null
      this.connect()
    }, backoffMs(this.attempt))
  }

  private detach(): void {
    const socket = this.socket
    if (socket !== null) {
      socket.onopen = null
      socket.onmessage = null
      socket.onclose = null
      socket.onerror = null
    }
    this.socket = null
    this.opened = false
    this.frameVersion = null
  }

  /** Once a second: the silence watchdog, and the frame rate for "Live 60 fps". */
  private tick(): void {
    const now = this.clock()
    // A tick more than twice late (a stalled tab, a laptop waking) measured the stall, not the
    // server: the silence check waits a tick for the socket's queued messages.
    const late = now - this.lastTickAt > (2 * TICK_MS) / 1000
    this.lastTickAt = now
    const socket = this.socket
    if (socket !== null && !late && now - this.lastHeardAt > SILENCE_MS / 1000) {
      this.drop(socket)
      return
    }
    const connection = this.store.getState().connection
    if (connection.status !== 'live') return
    const current = this.frames.sampleFps()
    if (this.lastWindow === null) {
      // The window since the first message was part of a second: it would read low.
      this.lastWindow = 0
      return
    }
    const fps = measuredFps(this.lastWindow, current, this.frameCap)
    this.lastWindow = current
    // Only a change is stored, so a steady 60 fps re-renders nothing.
    if (fps !== connection.fps) this.store.setState({ connection: { status: 'live', fps } })
  }
}
