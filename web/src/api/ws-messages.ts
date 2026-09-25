// The /ws protocol (spec §12.4): what the server sends and what the client asks for. The beat,
// decks and stats are snake_case on the wire, as today; the pushed snapshots use the contract's
// camelCase (decision 5).
import type {
  AttentionItem, Deck, FrameStream, Id, Inputs, LightUpdate, Overlay, RunningZone, SignalValue, TempoSource,
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
/** "Effects in space" (§12.4, F10). Typed so it's recognised; nothing reads it before F10. */
export interface FxMessage { channel: 'fx' }
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
  const payload = PAYLOADS[record.channel]
  if (payload !== undefined && !IS[payload[1]](record[payload[0]])) return null
  if (record.channel === 'stats' && record.lights !== undefined && !IS.list(record.lights)) return null
  return value as ServerMessage
}
