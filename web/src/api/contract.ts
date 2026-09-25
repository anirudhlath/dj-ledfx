// The data contract (spec §12.2). What the backend serves is generated from its OpenAPI schema
// (generated/schema.d.ts, `npm run api:types`). What it doesn't serve yet is written here from §12,
// marked with the engine milestone that brings it, and mocked until then (src/api/mocks/).
// contract.test.ts fails once the backend serves a pending name: swap in the generated type then.
import type { components, paths } from './generated/schema'

type Schemas = components['schemas']

export type Id = string
/** Every REST path the backend serves today. */
export type ApiPath = keyof paths

// ── Served since engine M1 ────────────────────────────────────────────────────────────────
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
export type Light = Schemas['Light']
export type LightPart = Schemas['LightPart']
/** One light on the socket's `lights` channel. */
export type LightUpdate = Pick<Light, 'id' | 'status' | 'statusSince' | 'ownEffect' | 'power' | 'colour'>

// ── Served since engine M2 (home map, preview runtimes, frame protocol v2) ────────────────
// §12.2's Home, Room, SubZone, Anchor and LightShape, with home.json's names for what §12.2
// leaves out (decision 4). Where F1's hand-written types and engine M2's differed, M2's won.
export type Vec2 = [number, number]
export type Vec3 = [number, number, number]
export type Home = Schemas['Home']
export type HomeSize = Schemas['HomeSize']
export type Room = Schemas['Room']
export type SubZone = Schemas['SubZone']
export type Anchor = Schemas['Anchor']
export type Wall = Schemas['Wall']
export type Box2 = Schemas['Box2']
export type Furniture = Schemas['Furniture']
export type Outdoor = Schemas['Outdoor']
export type Location = Schemas['Location']
/** PUT /home: "north, ceiling, beams, location" (§12.3). Only what's sent changes. */
export type HomeSettings = Schemas['HomeSettings']
export type AnchorIn = Schemas['AnchorIn']
export type AnchorUpdate = Schemas['AnchorUpdate']
export type SubZoneIn = Schemas['SubZoneIn']
export type SubZoneUpdate = Schemas['SubZoneUpdate']
export type PointShape = Schemas['PointShape']
export type LineShape = Schemas['LineShape']
export type BentLineShape = Schemas['BentLineShape']
export type CylinderShape = Schemas['CylinderShape']
export type GridShape = Schemas['GridShape']
export type LightShape = PointShape | LineShape | BentLineShape | CylinderShape | GridShape
/**
 * PUT /lights/{id}/placement: "shape, position, rotation, size, ledOrder" (§12.3). Without a
 * ledOrder, a shape of the same kind keeps its order (engine M2 plan, Spec Ruling 16).
 */
export type PlacementIn = Schemas['PlacementIn']
/** A light's placement: what the placement requests answer, and the guess per light it placed. */
export type Placement = Schemas['Placement']
export type PreviewRequest = Schemas['PreviewRequest']
export type PreviewStarted = Schemas['PreviewStarted']
/** PUT /preview/{id}: the editor's look as it is now, saved or not. */
export type PreviewUpdate = Schemas['PreviewUpdate']
/** The binary frame's stream byte (§12.4): 0x01 live, 0x02 preview. */
export type FrameStream = 'live' | 'preview'
/**
 * A look that stopped, for State-Nothing-Running's "Start again" (§9.4): GET /api/running/recent
 * answers these, newest stop first (the engine M2 plan's Spec Ruling 19). One tap starts it again
 * with `api.start(zoneId, { lookId })`.
 */
export type RecentLook = Schemas['RecentLook']

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

/** The pending types' names, as the backend's schema will name them. */
export type PendingSchema = 'Deck' | 'Inputs' | 'Signal'
/** The pending REST paths (§12.3), with FastAPI's parameter names. */
export type PendingPath = '/api/inputs' | '/api/signals'
