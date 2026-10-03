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
/**
 * A zone's transition with its duration, which engine M4 serves (F3 decision 16). Until then the duration
 * is missing and the card says only the kind. contract.test.ts fails once the backend serves it: then this
 * becomes `NonNullable<RunningZone['transition']>`.
 */
export type ZoneTransition = NonNullable<RunningZone['transition']> & { durationS?: number }
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
/**
 * The statuses whose lights the engine streams to the web app: a look's, and while anyone watches
 * the live stream, an approximation of a light's own effect (engine zones/frames.py).
 */
export const STREAMED: ReadonlySet<LightStatus> = new Set<LightStatus>(['streaming', 'own-effect', 'streamed-copy'])

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

// ── Served since engine M3 (the tempo clock) ─────────────────────────────────────────────
/** GET /inputs's tempo. `held`: a tap or a set BPM keeps Internal until a DJ starts again. */
export type TempoInput = Schemas['TempoInput']
export type TempoSource = TempoInput['source']
export type TempoLock = TempoInput['lock']
/** The internal clock's BPM, how it got it and when: "118.0 · tapped 19:10". */
export type InternalTempo = Schemas['InternalTempo']
/**
 * One player on the socket's `decks` channel (§12.4, snake_case like the beat): the players heard,
 * with the track's BPM and the pitch apart. `master` is the deck the clock follows.
 */
export type Deck = Schemas['Deck']
export type DjSet = Schemas['DjSet']
/** `interface` is where the server listens (host:port), null when it doesn't. */
export type ProDjLinkInput = Schemas['ProDjLinkInput']
export type InputState = ProDjLinkInput['state']
/** PUT /inputs/tempo: a lock, and a BPM for the internal clock. */
export type TempoRequest = Schemas['TempoRequest']
/** POST /inputs/tempo/tap: the tap's time on the client's clock, in seconds. */
export type TapRequest = Schemas['TapRequest']
/** POST /inputs/tempo/nudge: a phase shift in beats, -1 to 1; positive brings the beat sooner. */
export type NudgeRequest = Schemas['NudgeRequest']

// ── Served since engine M4 (modifiers and transitions) ───────────────────────────────────
/** A layer modifier: where the layer shows (§12.2's mask), and how its field is moved. */
export type HeightMask = Schemas['HeightMask']
export type RoomMask = Schemas['RoomMask']
export type SubZoneMask = Schemas['SubZoneMask']
export type AnchorMask = Schemas['AnchorMask']
export type Mask = NonNullable<Layer['mask']>
export type Mirror = Schemas['Mirror']
export type Transform = Schemas['Transform']
/** A running zone's transition: `durationS` lets the bar move on between the running channel's pushes. */
export type RunningZoneTransition = Schemas['RunningZoneTransition']

// ── Pending: engine M6/M7 (Music Assistant, Home Assistant, the sun, signals) ─────────────
// Shaped from §12.3–12.4, §9.3 and the Inputs renders; the milestone that serves them owns the
// final shape (decision 6).
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
/** A point on the sun's recent path, for the stage's arc (§7.4); F2 asks engine M6 for it (F2 decision 7). */
export interface SunPathPoint {
  at: string
  elevation: number
  azimuth: number
}
export interface SunInput {
  elevation: number
  azimuth: number
  sunrise: string
  sunset: string
  /** The last two hours or so, oldest first; without it the stage draws no arc. */
  path?: SunPathPoint[]
}
/** What M6 and M7 add to GET /inputs. */
export interface PendingInputs { music: MusicInput; homeAssistant: HomeAssistantInput; sun: SunInput }
/** GET /inputs: the tempo and Pro DJ Link since engine M3; the rest is optional until it's served. */
export type Inputs = Schemas['Inputs'] & Partial<PendingInputs>
export type SignalValue = number | string | boolean
export interface Signal { name: string; value: SignalValue; unit?: string; usedBy: Id[] }

/** The pending types' names, as the backend's schema will name them. */
export type PendingSchema = 'Signal'
/** The pending REST paths (§12.3), with FastAPI's parameter names. */
export type PendingPath = '/api/signals'
