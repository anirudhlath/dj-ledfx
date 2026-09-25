// Fixtures from the handoff's own files (spec §12.5). The home, its lights and the looks come from
// byte copies of home.json and looks.json, so no name, position or description is typed here
// (CLAUDE.md, "Web App Design"), except the owner's name for one room (decision 8). What the files don't say, the mock makes up in the API's shape:
// addresses from the documentation range (RFC 5737), no MACs, and M1's latency heuristics.
import type { Home, Id, InputKind, Light, LightShape, Location, Look, Room, Vec3, Zone } from '../contract'
import homeJson from './home.json'
import looksJson from './looks.json'

type Protocol = Light['protocol']
type Capability = Light['capabilities'][number]
const CAPABILITIES: readonly string[] = ['colour', 'multizone', 'matrix', 'effects'] satisfies Capability[]
const isCapability = (name: string): name is Capability => CAPABILITIES.includes(name)

/** A light as home.json has it: its shape's fields sit on the light itself. */
interface RawLight {
  id: Id
  name: string
  room: Id
  subZone: Id | null
  model: string
  protocol: Protocol
  leds: number
  ledsEstimated: boolean
  /** Capitalised in the file ("Colour"), lower case in the API. */
  capabilities: string[]
  shape: LightShape['kind']
  confirmed: boolean
  position?: Vec3
  path?: Vec3[]
  base?: Vec3
  height?: number
  radius?: number
  center?: Vec3
  width?: number
  depth?: number
  ledOrder?: string
  parts?: { name: string; leds: number }[]
}

/** home.json: the home, with its lights and their totals beside it. */
interface RawHome extends Home {
  location: Location
  lights: RawLight[]
  totals: { lights: number; leds: number }
}

interface RawLook {
  id: Id
  name: string
  category: Look['category']
  inputs: InputKind[]
  description: string
  thumbnail: string
  scope: NonNullable<Look['scope']>
}

// JSON imports type arrays as number[], not tuples. The tests pin the shapes these casts claim.
const RAW = homeJson as unknown as RawHome
const RAW_LOOKS = (looksJson as unknown as { looks: RawLook[] }).looks

/** home.json's own totals. */
export const HOME_TOTALS = RAW.totals

/**
 * The owner's names for rooms, over home.json's (decision 8): the owner decided on 2026-09-24 that the
 * room `corridor` is "Entrance", as §6.3, §12.5 and the renders say. home.json is a byte copy and never
 * edited, so the fixtures rename the room here, as engine M2's seed does (its Spec Ruling 18).
 */
export const OWNER_ROOM_NAMES: Partial<Record<Id, string>> = { corridor: 'Entrance' }

/** The rooms with the owner's names. A room home.json already names so is unchanged. */
export function withOwnerNames(rooms: Room[]): Room[] {
  return rooms.map((room) => ({ ...room, name: OWNER_ROOM_NAMES[room.id] ?? room.name }))
}

const { lights: _lights, totals: _totals, ...rawHome } = RAW
export const homeFixture: Home = { ...rawHome, rooms: withOwnerNames(RAW.rooms) }

function need<T>(value: T | undefined, light: RawLight, field: string): T {
  if (value === undefined) throw new Error(`home.json: ${light.id} is a ${light.shape} with no ${field}`)
  return value
}

/** §12.2's LightShape from home.json's flat fields. A grid starts unrotated. */
export function lightShape(raw: RawLight): LightShape {
  switch (raw.shape) {
    case 'point':
      return { kind: 'point', position: need(raw.position, raw, 'position') }
    case 'line': {
      const [from, to] = need(raw.path, raw, 'path')
      return { kind: 'line', path: [from, to] }
    }
    case 'bent-line':
      return { kind: 'bent-line', path: need(raw.path, raw, 'path') }
    case 'cylinder':
      return {
        kind: 'cylinder',
        base: need(raw.base, raw, 'base'),
        height: need(raw.height, raw, 'height'),
        radius: need(raw.radius, raw, 'radius'),
      }
    case 'grid':
      return {
        kind: 'grid',
        center: need(raw.center, raw, 'center'),
        width: need(raw.width, raw, 'width'),
        depth: need(raw.depth, raw, 'depth'),
        rotation: [0, 0, 0],
      }
  }
}

/**
 * The firmware effects a light like this offers, by the engine's display names
 * (effects/firmware_lifx.py, firmware_openrgb.py). The first is what it runs in the firmware scenario.
 */
function builtInEffects(protocol: Protocol, capabilities: Capability[]): string[] {
  if (protocol === 'OpenRGB') return ['OpenRGB mode']
  if (protocol !== 'LIFX') return []
  const matrix = capabilities.includes('matrix')
  const multizone = capabilities.includes('multizone')
  if (matrix && multizone) return ['LIFX Morph', 'LIFX Flame']
  if (matrix) return ['LIFX Flame', 'LIFX Morph']
  if (multizone) return ['LIFX Move']
  return ['LIFX waveform']
}

/** CLAUDE.md's device-type heuristics: LIFX 50 ms, Govee 100 ms, USB 5 ms. Only LIFX can be probed. */
const LATENCY_MS: Record<Protocol, number> = { LIFX: 50, Govee: 100, OpenRGB: 5 }

/**
 * A part's device id. Engine M2 gives each part one (its Spec Ruling 4) and engine M1 serves each
 * as a light; the mock's are made up.
 */
export const partId = (lightId: Id, index: number): Id => `${lightId}-part-${index + 1}`

/** Every light in home.json, idle and off since `since`. Each call builds new objects. */
export function lightFixtures(since: string): Light[] {
  return RAW.lights.map((raw, index): Light => {
    const capabilities = raw.capabilities.map((name) => name.toLowerCase()).filter(isCapability)
    return {
      id: raw.id,
      name: raw.name,
      room: raw.room,
      subZone: raw.subZone,
      model: raw.model,
      protocol: raw.protocol,
      leds: raw.leds,
      capabilities,
      builtInEffects: builtInEffects(raw.protocol, capabilities),
      parts: raw.parts?.map((part, index) => ({ ...part, id: partId(raw.id, index) })) ?? null,
      shape: lightShape(raw),
      ledOrder: raw.ledOrder ?? '',
      confirmed: raw.confirmed,
      status: 'idle',
      statusSince: since,
      ownEffect: null,
      latency: { measuredMs: LATENCY_MS[raw.protocol], overrideMs: null, estimated: raw.protocol !== 'LIFX' },
      sendFps: 0,
      droppedPct: 0,
      address: `192.0.2.${10 + index}`,
      mac: null,
      firmware: null,
      power: false,
      colour: null,
    }
  })
}

/** The handoff's looks as M1 serves its built-ins: `needs` is the look's `inputs`. */
export const lookFixtures: Look[] = RAW_LOOKS.map((raw) => ({
  id: raw.id,
  name: raw.name,
  category: raw.category,
  builtIn: true,
  derivedFrom: null,
  description: raw.description,
  thumbnail: raw.thumbnail,
  scope: raw.scope,
  needs: raw.inputs,
  uses: [],
  starred: false,
  layers: [],
  modifiers: { trailsS: null, downbeatFlash: false, brightnessCap: null, evening: false },
  transition: { kind: 'cut', durationS: 0 },
}))

export function lookName(id: Id): string {
  const look = RAW_LOOKS.find((candidate) => candidate.id === id)
  if (look === undefined) throw new Error(`looks.json has no look ${id}`)
  return look.name
}

/** A room's name as the fixtures serve it: the owner's, where there is one. */
export function roomName(id: Id): string {
  const room = homeFixture.rooms.find((candidate) => candidate.id === id)
  if (room === undefined) throw new Error(`home.json has no room ${id}`)
  return room.name
}

/** The whole home's zone id, as engine M2 names it (its Spec Ruling 2). */
export const HOME_ZONE = 'home'

/** §11.3: "Whole home, each room with lights, sub-zones (Office desk, Kitchen counter)". */
export function zoneFixtures(home: Home, lights: Light[]): Zone[] {
  const ids = (keep: (light: Light) => boolean) => lights.filter(keep).map((light) => light.id)
  return [
    { id: HOME_ZONE, name: 'Whole home', kind: 'home', lights: ids(() => true) },
    ...home.rooms
      .filter((room) => room.hasLights)
      .map((room): Zone => ({ id: room.id, name: room.name, kind: 'room', lights: ids((light) => light.room === room.id) })),
    ...home.subZones.map(
      (sub): Zone => ({ id: sub.id, name: sub.name, kind: 'sub-zone', lights: ids((light) => light.subZone === sub.id) }),
    ),
  ]
}

/** The rooms a zone's lights are in, in the order of its lights: §12.2's `covers`. */
export function coversOf(home: Home, lights: Light[], ids: Id[]): string[] {
  const rooms = new Set<Id>()
  for (const id of ids) {
    const room = lights.find((light) => light.id === id)?.room
    if (room) rooms.add(room)
  }
  return [...rooms].map((id) => home.rooms.find((room) => room.id === id)?.name ?? id)
}
