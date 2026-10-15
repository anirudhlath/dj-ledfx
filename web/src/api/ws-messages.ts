// The /ws protocol (spec §12.4): what the server sends and what the client asks for. The beat,
// decks and stats are snake_case on the wire, as today; the pushed snapshots use the contract's
// camelCase (decision 5).
import type {
  AttentionItem, Deck, FrameStream, Id, Inputs, LightUpdate, Overlay, RunningZone, SignalValue, TempoSource, Vec3,
} from './contract'

/** Today's beat (engine M1): no source, bar or server time. */
export interface BeatV1 {
  channel: 'beat'
  bpm: number
  beat_phase: number
  bar_phase: number
  is_playing: boolean
  /** Beat in the bar, 1–4. */
  beat_pos: number
  pitch_percent: number
  deck_number: number | null
  deck_name: string | null
}
/** §12.4's beat (engine M3). `server_time` is seconds since the epoch (decision 2). */
export interface BeatV2 {
  channel: 'beat'
  bpm: number
  beat_phase: number
  bar_phase: number
  bar: number
  /** Beat in the bar, 1–4. */
  beat_in_bar: number
  pitch_percent: number
  source: TempoSource
  stale: boolean
  server_time: number
}
export type BeatMessage = BeatV1 | BeatV2
export interface DecksMessage { channel: 'decks'; decks: Deck[] }
export interface RunningMessage { channel: 'running'; zones: RunningZone[]; overlays?: Overlay[] }
export interface LightsMessage { channel: 'lights'; lights: LightUpdate[] }
export interface AttentionMessage { channel: 'attention'; items: AttentionItem[] }
/** Preview only is `simulating` (§12.1). */
export interface TransportMessage { channel: 'transport'; state: 'stopped' | 'playing' | 'simulating' }
export interface DeviceStat {
  id: Id
  name: string
  send_fps: number
  latency_ms: number
  frames_dropped: number
  dropped_pct: number
  connected: boolean
  status: string
}
/** One light's link (§12.4). Engine M2 sends these as `lights`; engine M1 has only `devices`. */
export interface LightStat {
  id: Id
  send_fps: number
  latency_ms: number
  dropped_pct: number
}
/** `devices` is per device, the PC's parts included; `lights` (engine M2) is per light. */
export interface StatsMessage { channel: 'stats'; devices: DeviceStat[]; lights?: LightStat[] }
export interface StatusMessage { channel: 'status'; ok: boolean; device_count: number; avg_render_ms: number; transport: string }
/** A command's answer. `protocol: 2` switches the session's frames to v2 (decision 1). */
export interface AckMessage { channel: 'ack'; id: number | null; action: string; protocol?: number; fps?: number }
export interface ErrorMessage { channel: 'error'; id?: number | null; detail: string }
export interface InputsMessage { channel: 'inputs'; inputs: Inputs }
export interface SignalsMessage { channel: 'signals'; values: Record<string, SignalValue> }
/**
 * One particle of §12.4's fx block: where it is, its colour and its radius. Places and lengths are metres in
 * the home map's frame (z up); colours linear 0–1, after the zone's brightness.
 */
export type FxParticle = [x: number, y: number, z: number, r: number, g: number, b: number, size: number]
/** A ring of light: a `sphere` is a shell, a `circle` lies level (its axis is z). `width` is how thick it's drawn. */
export interface FxRing {
  center: Vec3
  radius: number
  width: number
  rgb: Vec3
  form: 'sphere' | 'circle'
}
/** A plane of light: infinite, or with a `ray` (a direction in the plane) the half on that side of `point`. */
export interface FxPlane {
  point: Vec3
  normal: Vec3
  width: number
  rgb: Vec3
  ray?: Vec3
}
/** What one zone draws in space, with the frames of one stream. A zone with nothing to draw is left out. */
export interface ZoneFx {
  zoneId: Id
  stream: FrameStream
  particles?: FxParticle[]
  rings?: FxRing[]
  planes?: FxPlane[]
}
/** "Effects in space" (§7.4, §12.4): the whole picture, which each message replaces. */
export interface FxMessage { channel: 'fx'; zones: ZoneFx[] }
export type ServerMessage =
  | BeatMessage | DecksMessage | RunningMessage | LightsMessage | AttentionMessage | TransportMessage
  | StatsMessage | StatusMessage | AckMessage | ErrorMessage | InputsMessage | SignalsMessage | FxMessage

/** A command before the client numbers it. */
export type Command =
  | { action: 'subscribe_beat'; fps: number }
  | { action: 'subscribe_frames'; fps: number; protocol: 2; streams: FrameStream[]; lights?: Id[] }
  /** Today's frames (engine M1): a server that refuses v2 gets asked this instead. */
  | { action: 'subscribe_frames'; fps: number }
  | { action: 'subscribe_signals'; names?: string[] }
  | { action: 'subscribe_fx'; on: boolean }
  | { action: 'tap'; client_time: number }
export type ClientCommand = Command & { id: number }

const IS = {
  list: (value: unknown) => Array.isArray(value),
  object: (value: unknown) => typeof value === 'object' && value !== null && !Array.isArray(value),
  string: (value: unknown) => typeof value === 'string',
  number: (value: unknown) => typeof value === 'number',
}
// The field each message's store relies on: without it, the message is dropped, not stored.
const PAYLOADS: Partial<Record<string, [field: string, kind: keyof typeof IS]>> = {
  beat: ['bpm', 'number'],
  running: ['zones', 'list'],
  lights: ['lights', 'list'],
  attention: ['items', 'list'],
  stats: ['devices', 'list'],
  decks: ['decks', 'list'],
  inputs: ['inputs', 'object'],
  signals: ['values', 'object'],
  transport: ['state', 'string'],
}

const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)
const isVec3 = (value: unknown): value is Vec3 => Array.isArray(value) && value.length === 3 && value.every(finite)
const nonZero = (v: Vec3) => v[0] !== 0 || v[1] !== 0 || v[2] !== 0
const isRecord = (value: unknown): value is Record<string, unknown> => IS.object(value)
const isStream = (value: unknown): value is FrameStream => value === 'live' || value === 'preview'

/**
 * A particle: seven finite numbers, its size above 0. A longer one is a later optional field (§12.4's
 * "Extending it"), read as its first seven.
 */
function isParticle(value: unknown): value is FxParticle {
  if (!Array.isArray(value) || value.length < 7) return false
  for (let i = 0; i < 7; i++) if (!finite(value[i])) return false
  return value[6] > 0
}

function isRing(value: unknown): value is FxRing {
  if (!isRecord(value)) return false
  const { center, radius, width, rgb, form } = value
  return isVec3(center) && finite(radius) && radius >= 0 && finite(width) && width > 0 && isVec3(rgb) && (form === 'sphere' || form === 'circle')
}

/** A plane: a ray, when it has one, is a direction (not zero), or the plane isn't drawn whole by mistake. */
function isPlane(value: unknown): value is FxPlane {
  if (!isRecord(value)) return false
  const { point, normal, width, rgb, ray } = value
  return (
    isVec3(point) && isVec3(normal) && nonZero(normal) && finite(width) && width > 0 && isVec3(rgb) && (ray === undefined || (isVec3(ray) && nonZero(ray)))
  )
}

/** The items of `list` that `is` takes: none for a list that isn't one. */
const itemsOf = <T>(list: unknown, is: (item: unknown) => item is T): T[] | undefined => (Array.isArray(list) ? list.filter(is) : undefined)

/**
 * §12.4's fx block, checked as the other messages are, item by item: a zone or an item that isn't well formed is
 * dropped, not the message, and a key the client doesn't know is ignored. Null without its zones.
 */
function readFx(record: Record<string, unknown>): FxMessage | null {
  if (!IS.list(record.zones)) return null
  const zones: ZoneFx[] = []
  for (const zone of record.zones as unknown[]) {
    if (!isRecord(zone) || typeof zone.zoneId !== 'string' || !isStream(zone.stream)) continue
    const read: ZoneFx = { zoneId: zone.zoneId, stream: zone.stream }
    const particles = itemsOf(zone.particles, isParticle)
    const rings = itemsOf(zone.rings, isRing)
    const planes = itemsOf(zone.planes, isPlane)
    if (particles !== undefined) read.particles = particles
    if (rings !== undefined) read.rings = rings
    if (planes !== undefined) read.planes = planes
    zones.push(read)
  }
  return { channel: 'fx', zones }
}

/** A server message, or null for text that isn't one (bad JSON, no channel, a message missing its payload). */
export function parseMessage(text: string): ServerMessage | null {
  let value: unknown
  try {
    value = JSON.parse(text)
  } catch {
    return null
  }
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return null
  const record = value as Record<string, unknown>
  if (typeof record.channel !== 'string') return null
  if (record.channel === 'fx') return readFx(record)
  const payload = PAYLOADS[record.channel]
  if (payload !== undefined && !IS[payload[1]](record[payload[0]])) return null
  if (record.channel === 'stats' && record.lights !== undefined && !IS.list(record.lights)) return null
  return value as ServerMessage
}
