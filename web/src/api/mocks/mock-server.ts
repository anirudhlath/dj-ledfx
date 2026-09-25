// A pretend server playing one scenario (spec §12.5): §12.3's REST API, §12.4's channels, and frames
// from the frame generator. MSW puts it behind fetch and WebSocket in dev and in the mock build
// (handlers.ts); tests reach it through an in-memory socket. With `protocol: 1` it is engine M1 as
// deployed today: a bare ack, the v1 beat, v1 frames at 30 fps, an error for any other command, no
// decks or inputs (decision 9), 404 for the routes M1 doesn't serve, and the PC as a light per part.
import type {
  AnchorIn, ApiPath, CreateGroup, FrameStream, HomeSettings, Id, Light, LightShape, LightUpdate, Look, PendingPath, Placement,
  PlacementIn, PreviewRequest, PreviewUpdate, RecentLook, RunningZone, StartRequest, SubZoneIn, TakeOver, UpdateGroup, Zone,
} from '../contract'
import { encodeFrame, type FrameVersion } from '../frames'
import { PATH_PARAM } from '../rest'
import type { BeatV1, BeatV2, ServerMessage, StatsMessage } from '../ws-messages'
import { coversOf, partId, runningZone } from './fixtures'
import { motifFor, paint, type MotifSpec } from './frame-generator'
import { asEngineM1, buildScenario, type ScenarioName, type ScenarioState } from './scenarios'

const FRAME_MS = 1000 / 60
const TICK_MS = 16
const STATS_MS = 1000
const STATUS_MS = 10_000
const SIGNALS_MS = 100
/** After a stall longer than this (a hidden tab), frames pick up from now rather than catch up. */
const STALL_MS = 100
/** How many looks "Start again" keeps, as engine M2 does (its Spec Ruling 19). */
export const RECENT_LIMIT = 10
/** Engine M2 ends a preview nobody watches this long (its Spec Ruling 9). */
const PREVIEW_UNWATCHED_MS = 10_000

/** "Start again"'s order, engine M2's: the newest stop first, and of two that stopped together, the newer start. */
const newestFirst = (a: RecentLook, b: RecentLook) =>
  Date.parse(b.stoppedAt) - Date.parse(a.stoppedAt) || Date.parse(b.startedAt) - Date.parse(a.startedAt)

export interface MockLink {
  send(data: string | ArrayBuffer): void
  close(): void
}

export interface MockReply {
  status: number
  body?: unknown
}

/** One connection, as the server hands it out: the handle to pass back to receive() and disconnect(). */
export interface MockSession {
  readonly link: MockLink
}

export interface MockServerOptions {
  scenario?: ScenarioName
  /** 2 speaks §12.4. 1 speaks engine M1's protocol (decision 9). */
  protocol?: 1 | 2
  /** ?still: one beat message after subscribe_beat, then none. */
  still?: boolean
  /** Monotonic ms. */
  clock?: () => number
  /** Epoch ms: the API's times and the beat's server_time. */
  wallClock?: () => number
}

interface Session extends MockSession {
  version: FrameVersion | null
  /** Send every nth frame: 1 for 60 fps, 2 for 30. */
  frameEvery: number
  streams: ReadonlySet<FrameStream>
  lights: ReadonlySet<Id> | null
  beatMs: number | null
  nextBeatAt: number
  signals: string[] | null
}

/** A light the mock streams, and the buffer it paints into. */
interface Painted {
  id: Id
  spec: MotifSpec
  brightness: number
  /** A crashed zone holds its last frame. */
  frozen: boolean
  seed: number
  rgb: Uint8Array
}

const STREAMING: ReadonlySet<Light['status']> = new Set(['streaming', 'streamed-copy'])

const ok = (body: unknown): MockReply => ({ status: 200, body })
const created = (body: unknown): MockReply => ({ status: 201, body })
const noContent: MockReply = { status: 204 }
const notFound = (detail = 'Not Found'): MockReply => ({ status: 404, body: { detail } })
const badRequest = (detail: string): MockReply => ({ status: 400, body: { detail } })
const BUILT_IN = 'Built-in looks are never changed; save an edit as a new look instead.'

function lightUpdate(light: Light): LightUpdate {
  return {
    id: light.id,
    status: light.status,
    statusSince: light.statusSince,
    ownEffect: light.ownEffect,
    power: light.power,
    colour: light.colour,
  }
}

type Pushed = 'running' | 'lights' | 'attention' | 'transport'

/** What a new connection hears first: M1's four snapshots, and in v2 the decks and inputs too. */
export function snapshotMessages(state: ScenarioState, protocol: 1 | 2): ServerMessage[] {
  const messages: ServerMessage[] = [
    { channel: 'running', zones: state.running, overlays: state.overlays },
    { channel: 'lights', lights: state.lights.map(lightUpdate) },
    { channel: 'attention', items: state.attention },
    { channel: 'transport', state: state.previewOnly ? 'simulating' : 'playing' },
  ]
  if (protocol === 2) messages.push({ channel: 'decks', decks: state.decks }, { channel: 'inputs', inputs: state.inputs })
  return messages
}

/** Beats since bar 1's downbeat, `elapsedS` after the scenario began a quarter into its beat. */
function position(state: Pick<ScenarioState, 'beat'>, elapsedS: number): number {
  const { beat } = state
  const start = (beat.bar - 1) * 4 + (beat.beatInBar - 1) + 0.25
  return beat.stale || beat.bpm <= 0 ? start : start + (elapsedS * beat.bpm) / 60
}

/** The beat message. M1 (protocol 1) only has Pro DJ Link: with no DJ it sends bpm 0, stopped. */
export function beatMessage(
  state: Pick<ScenarioState, 'beat' | 'decks'>,
  elapsedS: number,
  serverTime: number,
  protocol: 1 | 2,
): BeatV1 | BeatV2 {
  const { beat } = state
  const at = position(state, elapsedS)
  const withinBar = at % 4
  if (protocol === 1) {
    if (beat.source !== 'prodjlink') {
      return {
        channel: 'beat', bpm: 0, beat_phase: 0, bar_phase: 0, is_playing: false, beat_pos: 1,
        pitch_percent: 0, deck_number: null, deck_name: null,
      }
    }
    const master = state.decks.find((deck) => deck.master)
    return {
      channel: 'beat',
      bpm: beat.bpm,
      beat_phase: withinBar % 1,
      bar_phase: withinBar / 4,
      is_playing: !beat.stale && beat.bpm > 0,
      beat_pos: Math.floor(withinBar) + 1,
      pitch_percent: beat.pitchPercent,
      deck_number: master?.number ?? null,
      deck_name: master?.player ?? null,
    }
  }
  return {
    channel: 'beat',
    bpm: beat.bpm,
    beat_phase: withinBar % 1,
    bar_phase: withinBar / 4,
    bar: Math.floor(at / 4) + 1,
    beat_in_bar: Math.floor(withinBar) + 1,
    pitch_percent: beat.pitchPercent,
    source: beat.source,
    stale: beat.stale,
    server_time: serverTime,
  }
}

/** Stats per device, the PC's parts each one; protocol 2 adds §12.4's per light, as engine M2 does. */
export function statsMessage(state: ScenarioState, protocol: 1 | 2): StatsMessage {
  const devices = state.lights.flatMap((light) =>
    (light.parts ?? [light]).map((device, index) => ({
      id: light.parts == null ? light.id : partId(light.id, index),
      name: device.name,
      send_fps: light.sendFps,
      latency_ms: light.latency.measuredMs ?? 0,
      frames_dropped: 0,
      dropped_pct: light.droppedPct,
      connected: light.status !== 'offline',
      status: light.status === 'offline' ? 'offline' : 'online',
    })),
  )
  if (protocol === 1) return { channel: 'stats', devices }
  const lights = state.lights.map((light) => ({
    id: light.id,
    send_fps: light.sendFps,
    latency_ms: light.latency.measuredMs ?? 0,
    dropped_pct: light.droppedPct,
  }))
  return { channel: 'stats', devices, lights }
}

type Method = 'GET' | 'POST' | 'PUT' | 'DELETE'
/** A template's parameters by name: `{look_id}` in the path is `params.look_id`. */
type ParamsOf<Path extends string> = Path extends `${string}{${infer Name}}${infer Rest}` ? Record<Name, string> & ParamsOf<Rest> : unknown
type Handler<Params> = (params: Params, body: unknown) => MockReply
/** Handlers by path template, then method: a template tsc doesn't know is an error. */
type Routes<Path extends string> = { [P in Path]?: Partial<Record<Method, Handler<ParamsOf<P>>>> }
interface Route {
  pattern: RegExp
  handlers: Partial<Record<Method, Handler<Record<string, string>>>>
}

/** Each template matched as apiPath() fills it: a parameter is one path segment. */
function compile<Path extends string>(routes: Routes<Path>): Route[] {
  return Object.entries<Route['handlers'] | undefined>(routes as Record<string, Route['handlers']>).map(([template, handlers]) => ({
    pattern: new RegExp(`^${template.replace(PATH_PARAM, '(?<$1>[^/]+)')}$`),
    handlers: handlers ?? {},
  }))
}

/** The item that matches, handed to `then`, or a 404 that says `missing`. */
function withOne<T>(items: readonly T[], matches: (item: T) => boolean, missing: string, then: (item: T) => MockReply): MockReply {
  const item = items.find(matches)
  return item === undefined ? notFound(missing) : then(item)
}

export class MockServer {
  readonly state: ScenarioState
  private readonly protocol: 1 | 2
  private readonly still: boolean
  private readonly clock: () => number
  private readonly wallClock: () => number
  private readonly startedAt: number
  private readonly sessions = new Set<Session>()
  private nextId = 0
  private timer: ReturnType<typeof setInterval> | null = null
  private live: Painted[] = []
  private preview: { id: Id; lights: Painted[]; watchedAt: number } | null = null
  /** Each light's last seq, per stream: they run on across a replan, as the engine's do. */
  private readonly seqs: Record<FrameStream, Map<Id, number>> = { live: new Map(), preview: new Map() }
  /** When each light's placement was confirmed; the seed's confirmed lights have no time. */
  private readonly confirmedAt = new Map<Id, string>()
  private frameCount = 0
  private nextFrameAt: number
  private nextStatsAt: number
  private nextStatusAt: number
  private nextSignalsAt: number
  private firstConnectAt: number | null = null
  private refusing = false
  private readonly routes: Route[]

  constructor(options: MockServerOptions = {}) {
    this.protocol = options.protocol ?? 2
    this.still = options.still ?? false
    this.clock = options.clock ?? (() => performance.now())
    this.wallClock = options.wallClock ?? (() => Date.now())
    const state = buildScenario(options.scenario ?? 'hero', new Date(this.wallClock()))
    this.state = this.protocol === 1 ? asEngineM1(state) : state
    this.routes =
      this.protocol === 1 ? this.servedRoutes() : [...this.servedRoutes(), ...this.m2Routes(), ...this.pendingRoutes()]
    this.startedAt = this.clock()
    this.nextFrameAt = this.startedAt
    this.nextStatsAt = this.startedAt + STATS_MS
    this.nextStatusAt = this.startedAt + STATUS_MS
    this.nextSignalsAt = this.startedAt
    this.plan()
  }

  start(): void {
    this.timer ??= setInterval(() => this.tick(), TICK_MS)
  }

  stop(): void {
    if (this.timer !== null) clearInterval(this.timer)
    this.timer = null
  }

  // ── The socket ───────────────────────────────────────────────────────────────────────────

  /** A new connection hears the snapshots at once. Null while the scenario refuses connections. */
  connect(link: MockLink): MockSession | null {
    if (this.refusing) return null
    const session: Session = {
      link,
      version: null,
      frameEvery: 1,
      streams: new Set(),
      lights: null,
      beatMs: null,
      nextBeatAt: 0,
      signals: null,
    }
    this.sessions.add(session)
    this.firstConnectAt ??= this.clock()
    for (const message of snapshotMessages(this.state, this.protocol)) this.sendJson(session, message)
    return session
  }

  disconnect(handle: MockSession): void {
    this.sessions.delete(handle as Session)
  }

  receive(handle: MockSession, text: string): void {
    const session = handle as Session
    if (!this.sessions.has(session)) return
    let command: Record<string, unknown>
    try {
      const parsed: unknown = JSON.parse(text)
      if (typeof parsed !== 'object' || parsed === null) throw new Error('not an object')
      command = parsed as Record<string, unknown>
    } catch {
      this.sendJson(session, { channel: 'error', detail: 'Invalid JSON' })
      return
    }
    const id = typeof command.id === 'number' ? command.id : null
    const action = String(command.action)
    const fps = typeof command.fps === 'number' ? command.fps : 10
    if (action === 'subscribe_beat') {
      session.beatMs = 1000 / Math.min(Math.max(fps, 1), 30)
      session.nextBeatAt = this.clock()
      this.ack(session, id, action)
      if (this.still) this.sendJson(session, this.beat(this.clock()))
      return
    }
    if (action === 'subscribe_frames') {
      const v2 = this.protocol === 2 && command.protocol === 2
      const granted = Math.min(Math.max(fps, 1), v2 ? 60 : 30)
      const wanted = v2 ? command.lights : command.devices
      session.version = v2 ? 2 : 1
      session.frameEvery = Math.max(1, Math.round(60 / granted))
      session.streams = new Set(v2 && Array.isArray(command.streams) ? (command.streams as FrameStream[]) : ['live'])
      session.lights = Array.isArray(wanted) && wanted.length > 0 ? new Set(wanted as Id[]) : null
      this.ack(session, id, action, v2 ? { protocol: 2, fps: granted } : {})
      return
    }
    if (this.protocol === 2 && action === 'subscribe_signals') {
      session.signals = Array.isArray(command.names) ? (command.names as string[]) : []
      this.ack(session, id, action)
      return
    }
    if (this.protocol === 2 && (action === 'subscribe_fx' || action === 'tap')) {
      this.ack(session, id, action)
      return
    }
    this.sendJson(session, { channel: 'error', id, detail: `Unknown action: ${action}` })
  }

  private ack(session: Session, id: number | null, action: string, extra: object = {}): void {
    this.sendJson(session, { channel: 'ack', id, action, ...extra })
  }

  private sendJson(session: Session, message: object): void {
    session.link.send(JSON.stringify(message))
  }

  private broadcast(message: object): void {
    const text = JSON.stringify(message)
    for (const session of this.sessions) session.link.send(text)
  }

  private isoNow(): string {
    return new Date(this.wallClock()).toISOString()
  }

  /** Seconds the beat has moved: none while ?still holds it. */
  private beatElapsedS(now: number): number {
    return this.still ? 0 : (now - this.startedAt) / 1000
  }

  private beat(now: number): BeatV1 | BeatV2 {
    return beatMessage(this.state, this.beatElapsedS(now), this.wallClock() / 1000, this.protocol)
  }

  private tick(): void {
    const now = this.clock()
    const dropAfter = this.state.dropAfterMs
    if (!this.refusing && dropAfter !== null && this.firstConnectAt !== null && now - this.firstConnectAt >= dropAfter) {
      this.refusing = true
      for (const session of this.sessions) session.link.close()
      this.sessions.clear()
    }
    if (now - this.nextFrameAt > STALL_MS) this.nextFrameAt = now
    while (now >= this.nextFrameAt) {
      this.frame(now)
      this.nextFrameAt += FRAME_MS
    }
    if (this.preview !== null) {
      if (this.watching('preview')) this.preview.watchedAt = now
      else if (now - this.preview.watchedAt >= PREVIEW_UNWATCHED_MS) this.preview = null
    }
    for (const session of this.sessions) {
      if (session.beatMs === null || this.still || now < session.nextBeatAt) continue
      this.sendJson(session, this.beat(now))
      session.nextBeatAt = Math.max(session.nextBeatAt + session.beatMs, now - session.beatMs)
    }
    if (now >= this.nextSignalsAt) {
      this.nextSignalsAt += SIGNALS_MS
      for (const session of this.sessions) if (session.signals !== null) this.sendJson(session, this.signals(now, session.signals))
    }
    if (now >= this.nextStatsAt) {
      this.nextStatsAt += STATS_MS
      this.broadcast(statsMessage(this.state, this.protocol))
    }
    if (now >= this.nextStatusAt) {
      this.nextStatusAt += STATUS_MS
      this.broadcast({
        channel: 'status',
        ok: true,
        device_count: this.state.lights.length,
        avg_render_ms: 1.2,
        transport: this.state.previewOnly ? 'simulating' : 'playing',
      })
    }
  }

  private signals(now: number, names: string[]): ServerMessage {
    const at = position(this.state, this.beatElapsedS(now))
    const live: Record<string, number> = { 'beat.phase': at % 1, 'bar.phase': (at % 4) / 4, bpm: this.state.beat.bpm }
    const values = Object.fromEntries(
      this.state.signals
        .filter((signal) => names.length === 0 || names.includes(signal.name))
        .map((signal) => [signal.name, live[signal.name] ?? signal.value]),
    )
    return { channel: 'signals', values }
  }

  // ── Frames ───────────────────────────────────────────────────────────────────────────────

  private painted(id: Id, leds: number, spec: MotifSpec, brightness: number, frozen: boolean): Painted {
    return { id, spec, brightness, frozen, seed: id.length * 1.7 + id.charCodeAt(0) / 50, rgb: new Uint8Array(leds * 3) }
  }

  /** Which lights stream, and how: after every change to what runs or to a light. */
  private plan(): void {
    const lights = new Map(this.state.lights.map((light) => [light.id, light]))
    this.live = []
    for (const zone of this.state.running) {
      const look = this.state.looks.find((candidate) => candidate.id === zone.lookId)
      const spec = motifFor(look ?? { id: zone.lookId, category: 'ambient' })
      for (const id of zone.lights) {
        const light = lights.get(id)
        if (light === undefined || !STREAMING.has(light.status)) continue
        this.live.push(this.painted(id, light.leds, spec, zone.brightness, zone.state === 'crashed'))
      }
    }
  }

  /** Whether any session has subscribed to frames on `stream`. */
  private watching(stream: FrameStream): boolean {
    for (const session of this.sessions) if (session.version !== null && session.streams.has(stream)) return true
    return false
  }

  /** One frame: each light painted once, encoded once per protocol, sent to each session that wants it. */
  private frame(now: number): void {
    this.frameCount += 1
    const t = (now - this.startedAt) / 1000
    const beatPhase = position(this.state, this.beatElapsedS(now)) % 1
    if (this.watching('live')) for (const light of this.live) this.sendFrame(light, 'live', t, beatPhase)
    if (this.preview !== null && this.watching('preview')) {
      for (const light of this.preview.lights) this.sendFrame(light, 'preview', t, beatPhase)
    }
  }

  private sendFrame(light: Painted, stream: FrameStream, t: number, beatPhase: number): void {
    paint(light.rgb, light.spec, light.frozen ? 0 : t, beatPhase, light.brightness, light.seed)
    const seqs = this.seqs[stream]
    const seq = (seqs.get(light.id) ?? 0) + 1
    seqs.set(light.id, seq)
    let v1: ArrayBuffer | null = null
    let v2: ArrayBuffer | null = null
    for (const session of this.sessions) {
      if (session.version === null || this.frameCount % session.frameEvery !== 0 || !session.streams.has(stream)) continue
      if (session.lights !== null && !session.lights.has(light.id)) continue
      if (session.version === 2) session.link.send((v2 ??= encodeFrame(2, light.id, seq, light.rgb, stream)))
      else session.link.send((v1 ??= encodeFrame(1, light.id, seq, light.rgb)))
    }
  }

  // ── REST ─────────────────────────────────────────────────────────────────────────────────

  /** One request. `path` may carry a query, which is ignored. A method a path doesn't serve is a 404. */
  handle(method: string, path: string, body?: unknown): MockReply {
    const pathname = path.split('?')[0]
    for (const { pattern, handlers } of this.routes) {
      const handler = handlers[method as Method]
      const match = handler === undefined ? null : pattern.exec(pathname)
      if (handler === undefined || match === null) continue
      const params = Object.entries(match.groups ?? {}).map(([name, value]) => [name, decodeURIComponent(value)])
      return handler(Object.fromEntries(params), body)
    }
    return notFound()
  }

  /** Engine M1's routes. */
  private servedRoutes(): Route[] {
    return compile<ApiPath>({
      '/api/looks': { GET: () => ok(this.state.looks), POST: (_, body) => this.saveLook(body as Look) },
      '/api/looks/{look_id}': {
        GET: ({ look_id }) => this.withLook(look_id, ok),
        PUT: ({ look_id }, body) => this.updateLook(look_id, body as Look),
        DELETE: ({ look_id }) => this.deleteLook(look_id),
      },
      '/api/looks/{look_id}/starred': {
        PUT: ({ look_id }, body) =>
          this.withLook(look_id, (look) => {
            look.starred = (body as { starred: boolean }).starred
            return ok(look)
          }),
      },
      '/api/zones': { GET: () => ok(this.state.zones) },
      '/api/zones/groups': { POST: (_, body) => this.createGroup(body as CreateGroup) },
      '/api/zones/groups/{zone_id}': {
        PUT: ({ zone_id }, body) => this.updateGroup(zone_id, body as UpdateGroup),
        DELETE: ({ zone_id }) => this.deleteGroup(zone_id),
      },
      '/api/running': { GET: () => ok({ zones: this.state.running, overlays: this.state.overlays }) },
      '/api/zones/{zone_id}/start': { POST: ({ zone_id }, body) => this.startLook(zone_id, body as StartRequest) },
      '/api/zones/{zone_id}/brightness': {
        PUT: ({ zone_id }, body) =>
          this.withRunning(zone_id, (zone) => {
            zone.brightness = (body as { value: number }).value
            this.changed('running')
            return ok(zone)
          }),
      },
      '/api/zones/{zone_id}/off': { POST: ({ zone_id }) => this.off(zone_id) },
      '/api/zones/{zone_id}/restart': {
        POST: ({ zone_id }) =>
          this.withRunning(zone_id, (zone) => {
            Object.assign(zone, { state: 'running', error: null, fps: { actual: 60, target: 60 } } satisfies Partial<RunningZone>)
            this.state.attention = this.state.attention.filter((item) => item.subject.id !== zone_id)
            this.changed('running', 'attention')
            return ok(zone)
          }),
      },
      '/api/running/stop-all': { POST: () => this.stopAll() },
      '/api/lights': { GET: () => ok(this.state.lights) },
      '/api/attention': { GET: () => ok(this.state.attention) },
      '/api/config': {
        GET: () => ok({ engine: { preview_only: this.state.previewOnly } }),
        PUT: (_, body) => this.putConfig(body),
      },
    })
  }

  /** Engine M2's routes: engine M1 doesn't serve them, so a 404 with protocol 1. */
  private m2Routes(): Route[] {
    return compile<ApiPath>({
      '/api/home': {
        GET: () => ok(this.state.home),
        PUT: (_, body) => ok(Object.assign(this.state.home, body as HomeSettings)),
      },
      '/api/home/anchors': {
        POST: (_, body) => {
          const anchor = { ...(body as AnchorIn), id: this.newId('anchor'), confirmed: false }
          this.state.home.anchors.push(anchor)
          return created(anchor)
        },
      },
      '/api/home/anchors/{anchor_id}': {
        PUT: ({ anchor_id }, body) => this.update(this.state.home.anchors, anchor_id, body),
        DELETE: ({ anchor_id }) => this.remove(this.state.home.anchors, anchor_id),
      },
      '/api/home/subzones': {
        POST: (_, body) => {
          const subZone = { ...(body as SubZoneIn), id: this.newId('subzone') }
          this.state.home.subZones.push(subZone)
          return created(subZone)
        },
      },
      '/api/home/subzones/{sub_zone_id}': {
        PUT: ({ sub_zone_id }, body) => this.update(this.state.home.subZones, sub_zone_id, body),
        DELETE: ({ sub_zone_id }) => this.remove(this.state.home.subZones, sub_zone_id),
      },
      '/api/lights/placement/guess': { POST: () => this.guess() },
      '/api/lights/{light_id}/placement': {
        PUT: ({ light_id }, body) =>
          this.withLight(light_id, (light) => {
            const placement = body as PlacementIn
            Object.assign(light, { shape: placement.shape, ledOrder: placement.ledOrder ?? light.ledOrder, confirmed: false })
            this.confirmedAt.delete(light_id)
            return this.placementReply(light)
          }),
      },
      '/api/lights/{light_id}/placement/confirm': {
        POST: ({ light_id }) =>
          this.withLight(light_id, (light) => {
            if (light.shape == null) return this.placementReply(light)
            light.confirmed = true
            this.confirmedAt.set(light_id, this.isoNow())
            return this.placementReply(light)
          }),
      },
      '/api/preview': { POST: (_, body) => this.startPreview(body as PreviewRequest) },
      '/api/preview/{preview_id}': {
        PUT: ({ preview_id }, body) => this.updatePreview(preview_id, body as Partial<PreviewUpdate>),
        DELETE: ({ preview_id }) => this.stopPreview(preview_id),
      },
      '/api/running/recent': { GET: () => ok(this.recentLooks()) },
    })
  }

  /** What no engine serves yet (M3, M6 and M7), so a 404 with protocol 1. */
  private pendingRoutes(): Route[] {
    return compile<PendingPath>({
      '/api/inputs': { GET: () => ok(this.state.inputs) },
      '/api/signals': { GET: () => ok(this.state.signals) },
    })
  }

  private newId(kind: string): Id {
    return `${kind}-${++this.nextId}`
  }

  /** Pushes these channels' snapshots to every session, and replans the frames. */
  private changed(...channels: Pushed[]): void {
    for (const message of snapshotMessages(this.state, this.protocol)) {
      if ((channels as string[]).includes(message.channel)) this.broadcast(message)
    }
    this.plan()
  }

  private withLook(id: Id, then: (look: Look) => MockReply): MockReply {
    return withOne(this.state.looks, (look) => look.id === id, `No look '${id}'`, then)
  }

  private withLight(id: Id, then: (light: Light) => MockReply): MockReply {
    return withOne(this.state.lights, (light) => light.id === id, `No light '${id}'`, then)
  }

  private withZone(id: Id, then: (zone: Zone) => MockReply): MockReply {
    return withOne(this.state.zones, (zone) => zone.id === id, `No zone '${id}'`, then)
  }

  private withGroup(id: Id, then: (zone: Zone) => MockReply): MockReply {
    return withOne(this.state.zones, (zone) => zone.id === id && zone.kind === 'group', `No zone '${id}'`, then)
  }

  private withRunning(zoneId: Id, then: (zone: RunningZone) => MockReply): MockReply {
    return withOne(this.state.running, (zone) => zone.zoneId === zoneId, `Zone '${zoneId}' is not running`, then)
  }

  /** A zone's name for a message, or its id once it's gone. */
  private zoneName(id: Id): string {
    return this.state.zones.find((zone) => zone.id === id)?.name ?? id
  }

  /** The look a start or a preview names, as engine M2 reads it: a saved look by id, or a whole draft. */
  private withLookFor(body: { lookId?: Id | null; look?: Look | null }, then: (look: Look) => MockReply): MockReply {
    if ((body.lookId == null) === (body.look == null)) return badRequest('Send either lookId or look')
    return body.look != null ? then(body.look) : this.withLook(body.lookId!, then)
  }

  /** A light's placement, as engine M2 answers a placement request (its Spec Ruling 16). */
  private placement(light: Light, shape: LightShape): Placement {
    return { shape, ledOrder: light.ledOrder, confirmed: light.confirmed, confirmedAt: this.confirmedAt.get(light.id) ?? null }
  }

  private placementReply(light: Light): MockReply {
    return light.shape == null ? notFound(`Light '${light.id}' has no placement`) : ok(this.placement(light, light.shape))
  }

  /** A PUT on an anchor or a sub-zone: as engine M2 does, a field sent as null stays as it was. */
  private update<T extends { id: Id }>(items: T[], id: Id, body: unknown): MockReply {
    const sent = Object.fromEntries(Object.entries(body as Partial<T>).filter(([, value]) => value != null))
    return withOne(items, (item) => item.id === id, `No '${id}'`, (item) => ok(Object.assign(item, sent, { id })))
  }

  private remove<T extends { id: Id }>(items: T[], id: Id): MockReply {
    const index = items.findIndex((candidate) => candidate.id === id)
    if (index < 0) return notFound(`No '${id}'`)
    items.splice(index, 1)
    return noContent
  }

  private saveLook(body: Look): MockReply {
    const look: Look = { ...body, id: this.newId('look'), builtIn: false, starred: false }
    this.state.looks.push(look)
    return created(look)
  }

  private updateLook(id: Id, body: Look): MockReply {
    return this.withLook(id, (look) => {
      if (look.builtIn) return { status: 409, body: { detail: BUILT_IN } }
      return ok(Object.assign(look, body, { id, builtIn: false }))
    })
  }

  private deleteLook(id: Id): MockReply {
    return this.withLook(id, (look) => {
      if (look.builtIn) return { status: 409, body: { detail: BUILT_IN } }
      return this.remove(this.state.looks, id)
    })
  }

  private createGroup(body: CreateGroup): MockReply {
    const zone = { id: this.newId('group'), name: body.name, kind: 'group' as const, lights: body.lights }
    this.state.zones.push(zone)
    return created(zone)
  }

  private updateGroup(id: Id, body: UpdateGroup): MockReply {
    return this.withGroup(id, (zone) => {
      if (body.name != null) zone.name = body.name
      if (body.lights != null) zone.lights = body.lights
      return ok(zone)
    })
  }

  private deleteGroup(id: Id): MockReply {
    return this.withGroup(id, () => {
      this.off(id, false) // a deleted group can't start again, so engine M2 doesn't remember it
      return this.remove(this.state.zones, id)
    })
  }

  /** §11.3: the zone takes its lights from any running zone; a zone left with none stops. */
  private startLook(zoneId: Id, body: StartRequest): MockReply {
    return this.withZone(zoneId, (zone) => this.withLookFor(body, (look) => this.takeOver(zone, look)))
  }

  private takeOver(zone: Zone, look: Look): MockReply {
    const taking = new Set(zone.lights)
    const takeOvers: TakeOver[] = []
    const stopped: RunningZone[] = []
    for (const other of this.state.running) {
      if (other.zoneId === zone.id) continue
      const lost = other.lights.filter((id) => taking.has(id))
      if (lost.length === 0) continue
      other.lights = other.lights.filter((id) => !taking.has(id))
      other.covers = coversOf(this.state.home, this.state.lights, other.lights)
      const gone = other.lights.length === 0
      takeOvers.push({ zoneId: other.zoneId, zoneName: this.zoneName(other.zoneId), lookName: other.lookName, lights: lost, stopped: gone })
      if (gone) stopped.push(other)
    }
    const previous = this.state.running.find((candidate) => candidate.zoneId === zone.id)
    if (previous !== undefined && previous.lookId !== look.id) stopped.push(previous) // a new look replaces it
    this.remember(stopped)
    this.state.running = this.state.running.filter((other) => other.zoneId !== zone.id && other.lights.length > 0)
    const running = runningZone(this.state.home, this.state.lights, {
      zoneId: zone.id,
      lookId: look.id ?? '',
      lookName: look.name,
      since: this.isoNow(),
      brightness: previous?.brightness ?? 1,
      lights: zone.lights,
    })
    this.state.running.push(running)
    this.changed('running', 'lights')
    return ok({ ...running, takeOvers })
  }

  /** Off (§11.3): the look stops and its lights go back to how they were. Idempotent. */
  private off(zoneId: Id, remember = true): MockReply {
    return this.withZone(zoneId, () => {
      const running = this.state.running.find((zone) => zone.zoneId === zoneId)
      if (running === undefined) return noContent
      this.state.running = this.state.running.filter((zone) => zone !== running)
      if (remember) this.remember([running])
      this.release(running.lights)
      this.state.attention = this.state.attention.filter((item) => item.subject.id !== zoneId)
      this.changed('running', 'lights', 'attention')
      return noContent
    })
  }

  private stopAll(): MockReply {
    this.remember(this.state.running)
    this.release(this.state.running.flatMap((zone) => zone.lights))
    this.state.running = []
    this.state.overlays = []
    this.state.attention = this.state.attention.filter((item) => item.subject.type !== 'zone')
    this.changed('running', 'lights', 'attention')
    return noContent
  }

  private release(ids: Id[]): void {
    const since = this.isoNow()
    for (const light of this.state.lights) {
      if (!ids.includes(light.id) || light.status === 'offline' || light.status === 'switched-off') continue
      Object.assign(light, { status: 'idle', statusSince: since, ownEffect: null, sendFps: 0 } satisfies Partial<Light>)
    }
  }

  /**
   * Remembers looks that stop, as engine M2 does (its Spec Ruling 19): one entry per zone and look with
   * its newest stop, newest first, at most RECENT_LIMIT. A look the server doesn't have (a draft) isn't
   * remembered, because one tap couldn't start it.
   */
  private remember(stopped: RunningZone[]): void {
    const stoppedAt = this.isoNow()
    const entries = stopped
      .filter((zone) => this.state.looks.some((look) => look.id === zone.lookId))
      .map((zone): RecentLook => ({
        zoneId: zone.zoneId,
        zoneName: this.zoneName(zone.zoneId),
        lookId: zone.lookId,
        lookName: zone.lookName,
        startedAt: zone.since,
        stoppedAt,
      }))
    // A stable sort keeps a new entry ahead of an old one with the same times, as M2's upsert does.
    const all = [...entries, ...this.state.recent].sort(newestFirst)
    this.state.recent = all
      .filter((entry, index) => all.findIndex((other) => other.zoneId === entry.zoneId && other.lookId === entry.lookId) === index)
      .slice(0, RECENT_LIMIT)
  }

  /**
   * "Start again" (§9.4): what one tap can start again, with today's names. A zone that's gone or holds no
   * lights, a deleted look and a look running on its zone now are left out, but stay remembered.
   */
  private recentLooks(): RecentLook[] {
    return this.state.recent.flatMap((entry) => {
      const zone = this.state.zones.find((candidate) => candidate.id === entry.zoneId)
      const look = this.state.looks.find((candidate) => candidate.id === entry.lookId)
      const running = this.state.running.some((each) => each.zoneId === entry.zoneId && each.lookId === entry.lookId)
      if (zone === undefined || zone.lights.length === 0 || look === undefined || running) return []
      return [{ ...entry, zoneName: zone.name, lookName: look.name }]
    })
  }

  private putConfig(body: unknown): MockReply {
    const on = (body as { engine?: { preview_only?: unknown } } | null)?.engine?.preview_only
    if (on !== undefined && typeof on !== 'boolean') return badRequest('engine.preview_only must be true or false')
    if (on !== undefined && on !== this.state.previewOnly) {
      this.state.previewOnly = on
      this.changed('transport')
    }
    return ok({ engine: { preview_only: this.state.previewOnly } })
  }

  /** Spreads unplaced lights around their rooms, unconfirmed (§12.3): here, at the room's label. */
  private guess(): MockReply {
    const guessed: Record<Id, Placement> = {}
    for (const light of this.state.lights) {
      const room = this.state.home.rooms.find((candidate) => candidate.id === light.room)
      if (light.shape != null || room === undefined) continue
      const shape: LightShape = { kind: 'point', position: [room.labelAt[0], room.labelAt[1], 1] }
      Object.assign(light, { shape, confirmed: false })
      guessed[light.id] = this.placement(light, shape)
    }
    return ok(guessed)
  }

  /** One preview at a time (§12.3): its frames go on the preview stream, and the lights are left alone. */
  private startPreview(body: PreviewRequest): MockReply {
    return this.withZone(body.zoneId, (zone) =>
      this.withLookFor(body, (look) => {
        const lights = new Map(this.state.lights.map((light) => [light.id, light]))
        const spec = motifFor(look)
        const id = this.newId('preview')
        this.preview = {
          id,
          lights: zone.lights.map((lightId) => this.painted(lightId, lights.get(lightId)?.leds ?? 0, spec, 1, false)),
          watchedAt: this.clock(),
        }
        return created({ previewId: id })
      }),
    )
  }

  private updatePreview(id: Id, body: Partial<PreviewUpdate>): MockReply {
    if (this.preview?.id !== id) return notFound(`No preview '${id}'`)
    if (body.look !== undefined) {
      const spec = motifFor(body.look)
      for (const light of this.preview.lights) light.spec = spec
    }
    return noContent
  }

  private stopPreview(id: Id): MockReply {
    if (this.preview?.id === id) this.preview = null
    return noContent
  }
}
