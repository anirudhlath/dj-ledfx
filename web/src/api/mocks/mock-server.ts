// A pretend server playing one scenario (spec §12.5): §12.3's REST API, §12.4's channels, and frames
// from the frame generator. MSW puts it behind fetch and WebSocket in dev and in the mock build
// (handlers.ts); tests reach it through an in-memory socket. With `protocol: 1` it speaks as engine
// M1 does today: a bare ack, the v1 beat, v1 frames at 30 fps, an error for any other command, and
// no decks or inputs (decision 9).
import type {
  AnchorInput, CreateGroup, FrameStream, HomeUpdate, Id, Light, LightUpdate, Look, Placement, PlacementState, PreviewRequest,
  RecentLook, RunningZone, StartRequest, SubZoneInput, TakeOver, UpdateGroup,
} from '../contract'
import { encodeFrame, type FrameVersion } from '../frames'
import type { BeatV1, BeatV2, ServerMessage, StatsMessage } from '../ws-messages'
import { coversOf } from './fixtures'
import { motifFor, paint, type MotifSpec } from './frame-generator'
import { buildScenario, type ScenarioName, type ScenarioState } from './scenarios'

const FRAME_MS = 1000 / 60
const TICK_MS = 16
const STATS_MS = 1000
const STATUS_MS = 10_000
const SIGNALS_MS = 100
/** After a stall longer than this (a hidden tab), frames pick up from now rather than catch up. */
const STALL_MS = 100
/** How many looks "Start again" keeps, as engine M2 does (its Spec Ruling 19). */
export const RECENT_LIMIT = 10

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

export interface MockSession {
  readonly id: number
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
  link: MockLink
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

export function statsMessage(state: ScenarioState): StatsMessage {
  return {
    channel: 'stats',
    devices: state.lights.map((light) => ({
      id: light.id,
      name: light.name,
      send_fps: light.sendFps,
      latency_ms: light.latency.measuredMs ?? 0,
      frames_dropped: 0,
      dropped_pct: light.droppedPct,
      connected: light.status !== 'offline',
      status: light.status === 'offline' ? 'offline' : 'online',
    })),
  }
}

type Route = [method: string, pattern: RegExp, handler: (params: string[], body: unknown) => MockReply]

export class MockServer {
  readonly state: ScenarioState
  private readonly protocol: 1 | 2
  private readonly still: boolean
  private readonly clock: () => number
  private readonly wallClock: () => number
  private readonly startedAt: number
  private sessions: Session[] = []
  private nextSessionId = 0
  private nextId = 0
  private timer: ReturnType<typeof setInterval> | null = null
  private live: Painted[] = []
  private preview: { id: Id; lights: Painted[] } | null = null
  private readonly seqs = new Map<string, number>()
  /** When each light's placement was confirmed; the seed's confirmed lights have no time. */
  private readonly confirmedAt = new Map<Id, string>()
  private frameCount = 0
  private nextFrameAt: number
  private nextStatsAt: number
  private nextStatusAt: number
  private nextSignalsAt: number
  private firstConnectAt: number | null = null
  private refusing = false

  constructor(options: MockServerOptions = {}) {
    this.protocol = options.protocol ?? 2
    this.still = options.still ?? false
    this.clock = options.clock ?? (() => performance.now())
    this.wallClock = options.wallClock ?? (() => Date.now())
    this.state = buildScenario(options.scenario ?? 'hero', new Date(this.wallClock()))
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
      id: ++this.nextSessionId,
      link,
      version: null,
      frameEvery: 1,
      streams: new Set(),
      lights: null,
      beatMs: null,
      nextBeatAt: 0,
      signals: null,
    }
    this.sessions.push(session)
    this.firstConnectAt ??= this.clock()
    for (const message of snapshotMessages(this.state, this.protocol)) this.sendJson(session, message)
    return session
  }

  disconnect(handle: MockSession): void {
    this.sessions = this.sessions.filter((session) => session.id !== handle.id)
  }

  receive(handle: MockSession, text: string): void {
    const session = this.sessions.find((candidate) => candidate.id === handle.id)
    if (session === undefined) return
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

  private beat(now: number): BeatV1 | BeatV2 {
    const elapsedS = this.still ? 0 : (now - this.startedAt) / 1000
    return beatMessage(this.state, elapsedS, this.wallClock() / 1000, this.protocol)
  }

  private tick(): void {
    const now = this.clock()
    const dropAfter = this.state.link.dropAfterMs
    if (!this.refusing && dropAfter !== null && this.firstConnectAt !== null && now - this.firstConnectAt >= dropAfter) {
      this.refusing = true
      for (const session of this.sessions) session.link.close()
      this.sessions = []
    }
    if (now - this.nextFrameAt > STALL_MS) this.nextFrameAt = now
    while (now >= this.nextFrameAt) {
      this.frame(now)
      this.nextFrameAt += FRAME_MS
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
      this.broadcast(statsMessage(this.state))
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
    const at = position(this.state, this.still ? 0 : (now - this.startedAt) / 1000)
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

  /** One frame: each light painted once, encoded once per protocol, sent to each session that wants it. */
  private frame(now: number): void {
    this.frameCount += 1
    const sessions = this.sessions.filter((session) => session.version !== null)
    if (sessions.length === 0) return
    const t = (now - this.startedAt) / 1000
    const beatPhase = position(this.state, this.still ? 0 : t) % 1
    for (const light of this.live) this.sendFrame(light, 'live', t, beatPhase, sessions)
    for (const light of this.preview?.lights ?? []) this.sendFrame(light, 'preview', t, beatPhase, sessions)
  }

  private sendFrame(light: Painted, stream: FrameStream, t: number, beatPhase: number, sessions: Session[]): void {
    paint(light.rgb, light.rgb.length / 3, light.spec, light.frozen ? 0 : t, beatPhase, light.brightness, light.seed)
    const key = `${stream}:${light.id}`
    const seq = (this.seqs.get(key) ?? 0) + 1
    this.seqs.set(key, seq)
    let v1: ArrayBuffer | null = null
    let v2: ArrayBuffer | null = null
    for (const session of sessions) {
      if (this.frameCount % session.frameEvery !== 0 || !session.streams.has(stream)) continue
      if (session.lights !== null && !session.lights.has(light.id)) continue
      if (session.version === 2) session.link.send((v2 ??= encodeFrame(2, light.id, seq, light.rgb, stream)))
      else session.link.send((v1 ??= encodeFrame(1, light.id, seq, light.rgb)))
    }
  }

  // ── REST ─────────────────────────────────────────────────────────────────────────────────

  /** One request. `path` may carry a query, which is ignored. */
  handle(method: string, path: string, body?: unknown): MockReply {
    const pathname = path.split('?')[0]
    for (const [verb, pattern, handler] of this.routes) {
      if (verb !== method) continue
      const match = pattern.exec(pathname)
      if (match !== null) return handler(match.slice(1).map(decodeURIComponent), body)
    }
    return notFound()
  }

  private readonly routes: Route[] = [
    // Engine M1
    ['GET', /^\/api\/looks$/, () => ok(this.state.looks)],
    ['POST', /^\/api\/looks$/, (_, body) => this.saveLook(body as Look)],
    ['GET', /^\/api\/looks\/([^/]+)$/, ([id]) => this.withLook(id, (look) => ok(look))],
    ['PUT', /^\/api\/looks\/([^/]+)$/, ([id], body) => this.updateLook(id, body as Look)],
    ['DELETE', /^\/api\/looks\/([^/]+)$/, ([id]) => this.deleteLook(id)],
    [
      'PUT',
      /^\/api\/looks\/([^/]+)\/starred$/,
      ([id], body) =>
        this.withLook(id, (look) => {
          look.starred = (body as { starred: boolean }).starred
          return ok(look)
        }),
    ],
    ['GET', /^\/api\/zones$/, () => ok(this.state.zones)],
    ['POST', /^\/api\/zones\/groups$/, (_, body) => this.createGroup(body as CreateGroup)],
    ['PUT', /^\/api\/zones\/groups\/([^/]+)$/, ([id], body) => this.updateGroup(id, body as UpdateGroup)],
    ['DELETE', /^\/api\/zones\/groups\/([^/]+)$/, ([id]) => this.deleteGroup(id)],
    ['GET', /^\/api\/running$/, () => ok({ zones: this.state.running, overlays: this.state.overlays })],
    ['POST', /^\/api\/zones\/([^/]+)\/start$/, ([id], body) => this.startLook(id, body as StartRequest)],
    [
      'PUT',
      /^\/api\/zones\/([^/]+)\/brightness$/,
      ([id], body) =>
        this.withRunning(id, (zone) => {
          zone.brightness = (body as { value: number }).value
          this.changed('running')
          return ok(zone)
        }),
    ],
    ['POST', /^\/api\/zones\/([^/]+)\/off$/, ([id]) => this.off(id)],
    [
      'POST',
      /^\/api\/zones\/([^/]+)\/restart$/,
      ([id]) =>
        this.withRunning(id, (zone) => {
          Object.assign(zone, { state: 'running', error: null, fps: { actual: 60, target: 60 } } satisfies Partial<RunningZone>)
          this.state.attention = this.state.attention.filter((item) => item.subject.id !== id)
          this.changed('running', 'attention')
          return ok(zone)
        }),
    ],
    ['POST', /^\/api\/running\/stop-all$/, () => this.stopAll()],
    ['GET', /^\/api\/lights$/, () => ok(this.state.lights)],
    ['GET', /^\/api\/attention$/, () => ok(this.state.attention)],
    ['GET', /^\/api\/config$/, () => ok({ engine: { preview_only: this.state.previewOnly } })],
    ['PUT', /^\/api\/config$/, (_, body) => this.putConfig(body)],

    // Pending: engine M2
    ['GET', /^\/api\/home$/, () => ok(this.state.home)],
    ['PUT', /^\/api\/home$/, (_, body) => ok(Object.assign(this.state.home, body as HomeUpdate))],
    [
      'POST',
      /^\/api\/home\/anchors$/,
      (_, body) => {
        const anchor = { ...(body as AnchorInput), id: this.newId('anchor'), confirmed: false }
        this.state.home.anchors.push(anchor)
        return created(anchor)
      },
    ],
    ['PUT', /^\/api\/home\/anchors\/([^/]+)$/, ([id], body) => this.update(this.state.home.anchors, id, body)],
    ['DELETE', /^\/api\/home\/anchors\/([^/]+)$/, ([id]) => this.remove(this.state.home.anchors, id)],
    [
      'POST',
      /^\/api\/home\/subzones$/,
      (_, body) => {
        const subZone = { ...(body as SubZoneInput), id: this.newId('subzone') }
        this.state.home.subZones.push(subZone)
        return created(subZone)
      },
    ],
    ['PUT', /^\/api\/home\/subzones\/([^/]+)$/, ([id], body) => this.update(this.state.home.subZones, id, body)],
    ['DELETE', /^\/api\/home\/subzones\/([^/]+)$/, ([id]) => this.remove(this.state.home.subZones, id)],
    ['POST', /^\/api\/lights\/placement\/guess$/, () => this.guess()],
    [
      'PUT',
      /^\/api\/lights\/([^/]+)\/placement$/,
      ([id], body) =>
        this.withLight(id, (light) => {
          const placement = body as Placement
          Object.assign(light, { shape: placement.shape, ledOrder: placement.ledOrder ?? light.ledOrder, confirmed: false })
          this.confirmedAt.delete(id)
          return ok(this.placementOf(light))
        }),
    ],
    [
      'POST',
      /^\/api\/lights\/([^/]+)\/placement\/confirm$/,
      ([id]) =>
        this.withLight(id, (light) => {
          light.confirmed = true
          this.confirmedAt.set(id, new Date(this.wallClock()).toISOString())
          return ok(this.placementOf(light))
        }),
    ],
    ['POST', /^\/api\/preview$/, (_, body) => this.startPreview(body as PreviewRequest)],
    ['PUT', /^\/api\/preview\/([^/]+)$/, ([id], body) => this.updatePreview(id, body as { look?: Look })],
    ['DELETE', /^\/api\/preview\/([^/]+)$/, ([id]) => this.stopPreview(id)],
    ['GET', /^\/api\/running\/recent$/, () => ok(this.recentLooks())],

    // Pending: engine M3, M6 and M7
    ['GET', /^\/api\/inputs$/, () => ok(this.state.inputs)],
    ['GET', /^\/api\/signals$/, () => ok(this.state.signals)],
  ]

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
    const look = this.state.looks.find((candidate) => candidate.id === id)
    return look === undefined ? notFound(`No look '${id}'`) : then(look)
  }

  private withLight(id: Id, then: (light: Light) => MockReply): MockReply {
    const light = this.state.lights.find((candidate) => candidate.id === id)
    return light === undefined ? notFound(`No light '${id}'`) : then(light)
  }

  /** A light's placement, as engine M2 answers a placement request (its Spec Ruling 16). */
  private placementOf(light: Light): PlacementState {
    return {
      shape: light.shape ?? null,
      ledOrder: light.ledOrder ?? null,
      confirmed: light.confirmed ?? false,
      confirmedAt: this.confirmedAt.get(light.id) ?? null,
    }
  }

  private withRunning(zoneId: Id, then: (zone: RunningZone) => MockReply): MockReply {
    const zone = this.state.running.find((candidate) => candidate.zoneId === zoneId)
    return zone === undefined ? notFound(`Zone '${zoneId}' is not running`) : then(zone)
  }

  private update<T extends { id: Id }>(items: T[], id: Id, body: unknown): MockReply {
    const item = items.find((candidate) => candidate.id === id)
    return item === undefined ? notFound(`No '${id}'`) : ok(Object.assign(item, body as Partial<T>, { id }))
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
    const zone = this.state.zones.find((candidate) => candidate.id === id && candidate.kind === 'group')
    if (zone === undefined) return notFound(`No zone '${id}'`)
    if (body.name != null) zone.name = body.name
    if (body.lights != null) zone.lights = body.lights
    return ok(zone)
  }

  private deleteGroup(id: Id): MockReply {
    if (!this.state.zones.some((zone) => zone.id === id && zone.kind === 'group')) return notFound(`No zone '${id}'`)
    this.off(id, false) // a deleted group can't start again, so engine M2 doesn't remember it
    return this.remove(this.state.zones, id)
  }

  /** §11.3: the zone takes its lights from any running zone; a zone left with none stops. */
  private startLook(zoneId: Id, body: StartRequest): MockReply {
    const zone = this.state.zones.find((candidate) => candidate.id === zoneId)
    if (zone === undefined) return notFound(`No zone '${zoneId}'`)
    if ((body.lookId == null) === (body.look == null)) return badRequest('Send either lookId or look')
    const look = body.lookId != null ? this.state.looks.find((candidate) => candidate.id === body.lookId) : body.look
    if (look == null) return notFound(`No look '${body.lookId}'`)
    const taking = new Set(zone.lights)
    const takeOvers: TakeOver[] = []
    const stopped: RunningZone[] = []
    for (const other of this.state.running) {
      if (other.zoneId === zoneId) continue
      const lost = other.lights.filter((id) => taking.has(id))
      if (lost.length === 0) continue
      other.lights = other.lights.filter((id) => !taking.has(id))
      other.covers = coversOf(this.state.home, this.state.lights, other.lights)
      const name = this.state.zones.find((candidate) => candidate.id === other.zoneId)?.name ?? other.zoneId
      takeOvers.push({ zoneId: other.zoneId, zoneName: name, lookName: other.lookName, lights: lost, stopped: other.lights.length === 0 })
      if (other.lights.length === 0) stopped.push(other)
    }
    const previous = this.state.running.find((candidate) => candidate.zoneId === zoneId)
    if (previous !== undefined && previous.lookId !== look.id) stopped.push(previous) // a new look replaces it
    this.remember(stopped)
    this.state.running = this.state.running.filter((other) => other.zoneId !== zoneId && other.lights.length > 0)
    const running: RunningZone = {
      zoneId,
      lookId: look.id ?? '',
      lookName: look.name,
      since: this.isoNow(),
      brightness: previous?.brightness ?? 1,
      lights: zone.lights,
      covers: coversOf(this.state.home, this.state.lights, zone.lights),
      state: 'running',
      fps: { actual: 60, target: 60 },
    }
    this.state.running.push(running)
    for (const light of this.state.lights) {
      if (!taking.has(light.id) || light.status === 'offline' || light.status === 'switched-off') continue
      Object.assign(light, { status: 'streaming', statusSince: running.since, ownEffect: null, power: true, sendFps: 60 } satisfies Partial<Light>)
    }
    this.changed('running', 'lights')
    return ok({ ...running, takeOvers })
  }

  /** Off (§11.3): the look stops and its lights go back to how they were. Idempotent. */
  private off(zoneId: Id, remember = true): MockReply {
    if (!this.state.zones.some((zone) => zone.id === zoneId)) return notFound(`No zone '${zoneId}'`)
    const running = this.state.running.find((zone) => zone.zoneId === zoneId)
    if (running === undefined) return noContent
    this.state.running = this.state.running.filter((zone) => zone !== running)
    if (remember) this.remember([running])
    this.release(running.lights)
    this.state.attention = this.state.attention.filter((item) => item.subject.id !== zoneId)
    this.changed('running', 'lights', 'attention')
    return noContent
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
        zoneName: this.state.zones.find((candidate) => candidate.id === zone.zoneId)?.name ?? zone.zoneId,
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
    const guessed: Light[] = []
    for (const light of this.state.lights) {
      const room = this.state.home.rooms.find((candidate) => candidate.id === light.room)
      if (light.shape != null || room === undefined) continue
      light.shape = { kind: 'point', position: [room.labelAt[0], room.labelAt[1], 1] }
      light.confirmed = false
      guessed.push(light)
    }
    return ok(guessed)
  }

  /** One preview at a time (§12.3): its frames go on the preview stream, and the lights are left alone. */
  private startPreview(body: PreviewRequest): MockReply {
    const zone = this.state.zones.find((candidate) => candidate.id === body.zoneId)
    if (zone === undefined) return notFound(`No zone '${body.zoneId}'`)
    const look = body.lookId != null ? this.state.looks.find((candidate) => candidate.id === body.lookId) : body.look
    if (look == null) return badRequest('Send either lookId or look')
    const lights = new Map(this.state.lights.map((light) => [light.id, light]))
    const spec = motifFor(look)
    this.preview = {
      id: this.newId('preview'),
      lights: zone.lights.map((id) => this.painted(id, lights.get(id)?.leds ?? 0, spec, 1, false)),
    }
    return ok({ previewId: this.preview.id })
  }

  private updatePreview(id: Id, body: { look?: Look }): MockReply {
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
