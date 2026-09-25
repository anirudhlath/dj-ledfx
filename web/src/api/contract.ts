// The data contract (spec §12.2). What the backend serves is generated from its OpenAPI schema
// (generated/schema.d.ts, `npm run api:types`). What it doesn't serve yet is written here from §12,
// marked with the engine milestone that brings it, and mocked until then (src/api/mocks/).
// contract.test.ts fails once the backend serves a pending name: swap in the generated type then.
import type { components, paths } from './generated/schema'

type Schemas = components['schemas']

export type Id = string
/** Every REST path the backend serves today. */
export type ApiPath = keyof paths

// ── Served today (engine M1) ──────────────────────────────────────────────────────────────
export type Look = Schemas['Look']
export type Layer = Schemas['Layer']
export type LookModifiers = Schemas['LookModifiers']
export type Transition = Schemas['Transition']
export type Zone = Schemas['Zone']
export type CreateGroup = Schemas['CreateGroup']
export type UpdateGroup = Schemas['UpdateGroup']
export type RunningZone = Schemas['RunningZone']
export type Overlay = Schemas['Overlay']
export type Running = Schemas['Running']
export type StartRequest = Schemas['StartRequest']
export type StartResponse = Schemas['StartResponse']
export type TakeOver = Schemas['TakeOver']
export type AttentionItem = Schemas['AttentionItem']
export type InputKind = NonNullable<Look['needs']>[number]
export type LightStatus = Schemas['Light']['status']
/** A light (§12.2). The backend types `shape` loosely until engine M2 serves the home map. */
export type Light = Omit<Schemas['Light'], 'shape'> & { shape?: LightShape | null }
/** One light on the socket's `lights` channel. */
export type LightUpdate = Pick<Light, 'id' | 'status' | 'statusSince' | 'ownEffect' | 'power' | 'colour'>

// ── Pending: engine M2 (home map, preview runtimes, frame protocol v2) ────────────────────
// §12.2's Home, Room, SubZone, Anchor and LightShape; home.json's names for what §12.2 leaves out
// (decision 4).
export type Vec2 = [number, number]
export type Vec3 = [number, number, number]
export interface Room { id: Id; name: string; polygon: Vec2[]; labelAt: Vec2; hasLights: boolean }
export interface SubZone { id: Id; name: string; room: Id; polygon: Vec2[] }
export interface Anchor { id: Id; name: string; position: Vec3; points?: Vec3[]; confirmed: boolean }
export interface Wall {
  a: Vec2
  b: Vec2
  kind: 'wall' | 'window' | 'glass-door'
  westFacing: boolean
  exterior: boolean
  thickness: number
}
export interface Box2 { min: Vec2; max: Vec2 }
export interface Furniture {
  id: Id
  name: string
  height: number
  z0: number
  confirmed: boolean
  /** [x0, y0, x1, y1] on the plan. */
  box: [number, number, number, number]
}
export interface Outdoor { courtyard: Vec2[]; balcony: Vec2[]; courtyardOpensTo: string; balconyOffRoom: Id }
export interface Location { name: string; lat: number; lon: number; confirmed: boolean }
export interface Home {
  outline: Vec2[]
  rooms: Room[]
  subZones: SubZone[]
  walls: Wall[]
  columns: Box2[]
  furniture: Furniture[]
  anchors: Anchor[]
  ceiling: number
  beams: number
  northOffsetDeg: number
  location: Location
  size: { eastWest: number; northSouth: number }
  wallCutHeight: number
  outdoor: Outdoor
}
/** PUT /home: "north, ceiling, beams, location" (§12.3). */
export type HomeUpdate = Partial<Pick<Home, 'northOffsetDeg' | 'ceiling' | 'beams' | 'location'>>
export type AnchorInput = Omit<Anchor, 'id' | 'confirmed'>
export type SubZoneInput = Omit<SubZone, 'id'>
export type LightShape =
  | { kind: 'point'; position: Vec3 }
  | { kind: 'line'; path: [Vec3, Vec3] }
  | { kind: 'bent-line'; path: Vec3[] }
  | { kind: 'cylinder'; base: Vec3; height: number; radius: number }
  | { kind: 'grid'; center: Vec3; width: number; depth: number; rotation: Vec3 }
/** PUT /lights/{id}/placement: "shape, position, rotation, size, ledOrder" (§12.3). */
export interface Placement { shape: LightShape; ledOrder?: string }
/** What a placement request answers: the placement (engine M2 plan, Spec Ruling 16). */
export interface PlacementState { shape: LightShape | null; ledOrder: string | null; confirmed: boolean; confirmedAt: string | null }
export interface PreviewRequest { zoneId: Id; lookId?: Id; look?: Look }
export interface PreviewResponse { previewId: Id }
/** The binary frame's stream byte (§12.4): 0x01 live, 0x02 preview. */
export type FrameStream = 'live' | 'preview'
/**
 * A look that stopped, for State-Nothing-Running's "Start again" (§9.4): GET /api/running/recent
 * answers these, newest stop first. §12.2 has no such type; the engine M2 plan's Spec Ruling 19
 * shapes it. One tap starts it again with `api.start(zoneId, { lookId })`.
 */
export interface RecentLook {
  zoneId: Id
  zoneName: string
  lookId: Id
  lookName: string
  startedAt: string
  stoppedAt: string
}

// ── Pending: engine M3 (the tempo source chain) ───────────────────────────────────────────
export type TempoSource = 'prodjlink' | 'music' | 'internal'
export type TempoLock = 'auto' | TempoSource
/** One player on the socket's `decks` channel (§12.4, snake_case like the beat). */
export interface Deck {
  number: number
  player: string
  state: 'empty' | 'cued' | 'playing'
  bpm: number | null
  pitch_percent: number
  master: boolean
}

// ── Pending: engine M6/M7 (Music Assistant, Home Assistant, the sun, signals) ─────────────
// Shaped from §12.3–12.4, §9.3 and the Inputs renders; the milestone that serves them owns the
// final shape (decision 6).
export type InputState = 'connected' | 'stale' | 'disconnected' | 'idle'
export interface TempoInput { source: TempoSource; lock: TempoLock; bpm: number; stale: boolean }
export interface ProDjLinkInput { state: InputState; interface: string; lastSet: { from: string; to: string } | null }
export interface MusicInput {
  state: InputState
  track: { title: string; artist: string } | null
  group: string[]
  loudness: number
  lufs: number
  /** 32 bands, 0–1. */
  spectrum: number[]
  onsets: { kick: number; snare: number; hihat: number }
  updatedAt: string
}
export interface HomeAssistantEntity { id: string; state: string; since: string }
export interface HomeAssistantInput {
  state: InputState
  url: string
  since: string
  /** Seconds between retries while disconnected. */
  retryS: number | null
  entities: HomeAssistantEntity[]
}
export interface SunInput { elevation: number; azimuth: number; sunrise: string; sunset: string }
export interface Inputs {
  tempo: TempoInput
  prodjlink: ProDjLinkInput
  music: MusicInput
  homeAssistant: HomeAssistantInput
  sun: SunInput
}
export type SignalValue = number | string | boolean
export interface Signal { name: string; value: SignalValue; unit?: string; usedBy: Id[] }

/** The pending types' names, as the backend's schema would name them. */
export type PendingSchema =
  | 'Home' | 'Room' | 'SubZone' | 'Anchor' | 'Wall' | 'Furniture' | 'LightShape' | 'Placement'
  | 'PreviewRequest' | 'PreviewResponse' | 'RecentLook' | 'Deck' | 'Inputs' | 'Signal'
/** The pending REST paths (§12.3), with FastAPI's parameter names. */
export type PendingPath =
  | '/api/home'
  | '/api/home/anchors'
  | '/api/home/anchors/{anchor_id}'
  | '/api/home/subzones'
  | '/api/home/subzones/{subzone_id}'
  | '/api/lights/{light_id}/placement'
  | '/api/lights/{light_id}/placement/confirm'
  | '/api/lights/placement/guess'
  | '/api/preview'
  | '/api/preview/{preview_id}'
  | '/api/running/recent'
  | '/api/inputs'
  | '/api/signals'
