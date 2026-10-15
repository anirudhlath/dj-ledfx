// What the mock's zones draw in space (§12.4's `fx` payload), so "Effects in space" can be built and tested
// with no engine. Like the frame generator's motifs, these only keep the stage alive: each look gets a
// simple moving picture of its kind (particles that wander or orbit, Shockwave's shell and beam, Speaker
// waves' fronts, Ripples' drops, Scanner's plane) round the box its lights' placements span. The hues are
// the frame generator's, and the sizes and speeds are picked here; they are no design value, and engine M8
// sends the real looks.
import type { Id, LightShape, Look, Vec3 } from '../contract'
import type { FxParticle, FxPlane, FxRing, ZoneFx } from '../ws-messages'
import { motifFor } from './frame-generator'

/** The kinds of picture the mock draws: one per look that draws in space (§12.4's "What draws what"). */
type FxKind = 'wander' | 'orbit' | 'shockwave' | 'speakers' | 'ripples' | 'scanner'

// M5's eleven particle looks, and M3's four tempo looks and Ripples that send rings and planes.
const KIND_OF: Partial<Record<Id, FxKind>> = {
  fireflies: 'wander',
  embers: 'wander',
  rain: 'wander',
  snow: 'wander',
  spotlights: 'wander',
  bursts: 'wander',
  fountain: 'wander',
  flock: 'wander',
  vortex: 'orbit',
  comets: 'orbit',
  ball: 'orbit',
  shockwave: 'shockwave',
  speakers: 'speakers',
  ripples: 'ripples',
  scanner: 'scanner',
}

/** How many particles a wandering look draws, and how many each orbiting head trails. */
const WANDERERS = 12
const TRAIL = 6
/** A particle's glow, metres: about Fireflies' default glow size. */
const WANDER_SIZE = 0.4
const ORBIT_SIZE = 0.3
/** How thick a shell, a ring or a plane is drawn, metres. */
const SHELL_WIDTH = 0.3
const PLANE_WIDTH = 0.15

/** One zone of the picture: the look it runs (or previews), on which lights, how bright, and whether it's held. */
export interface FxZone {
  zoneId: Id
  stream: ZoneFx['stream']
  look: Pick<Look, 'id' | 'category'>
  shapes: readonly LightShape[]
  brightness: number
  /** A crashed zone holds its picture, as it holds its last frame. */
  frozen: boolean
}

/** Whether a look draws anything in space. */
export const drawsInSpace = (look: Pick<Look, 'id'>): boolean => KIND_OF[look.id ?? ''] !== undefined

/** §12.4: numbers rounded to 3 decimals. */
const round3 = (value: number): number => Math.round(value * 1000) / 1000
const rounded = ([x, y, z]: Vec3): Vec3 => [round3(x), round3(y), round3(z)]

/** A hue at full saturation, as linear 0–1 floats times `level`. */
function hueRgb(hue: number, level: number): Vec3 {
  const h = (((hue % 360) + 360) % 360) / 60
  const x = 1 - Math.abs((h % 2) - 1)
  const [r, g, b]: Vec3 = h < 1 ? [1, x, 0] : h < 2 ? [x, 1, 0] : h < 3 ? [0, 1, x] : h < 4 ? [0, x, 1] : h < 5 ? [x, 0, 1] : [1, 0, x]
  const white = 0.15 // a little white, as the frame generator's 0.85 saturation
  const lift = (channel: number) => ((channel + white) / (1 + white)) * level
  return rounded([lift(r), lift(g), lift(b)])
}

/** The points a light's placement puts it at: enough to find the box its zone spans. */
function shapePoints(shape: LightShape): Vec3[] {
  switch (shape.kind) {
    case 'point':
      return [shape.position]
    case 'line':
    case 'bent-line':
      return shape.path
    case 'cylinder': {
      const [x, y, z] = shape.base
      return [shape.base, [x, y, z + shape.height]]
    }
    case 'grid':
      return [shape.center]
  }
}

/** The box a zone's lights span: its centre, its half-size across, and its lowest and highest points. */
function boxOf(shapes: readonly LightShape[]): { centre: Vec3; reach: number; low: number; high: number } | null {
  const points = shapes.flatMap(shapePoints)
  if (points.length === 0) return null
  const min: Vec3 = [Infinity, Infinity, Infinity]
  const max: Vec3 = [-Infinity, -Infinity, -Infinity]
  for (const point of points) {
    for (let axis = 0; axis < 3; axis++) {
      min[axis] = Math.min(min[axis], point[axis])
      max[axis] = Math.max(max[axis], point[axis])
    }
  }
  const centre: Vec3 = [(min[0] + max[0]) / 2, (min[1] + max[1]) / 2, (min[2] + max[2]) / 2]
  // At least a metre, so one bulb's picture still moves.
  const reach = Math.max(1, Math.hypot(max[0] - min[0], max[1] - min[1]) / 2)
  return { centre, reach, low: min[2], high: Math.max(max[2], min[2] + 0.5) }
}

/**
 * What one zone draws at `t` seconds and `beats` beats into the music, or null for nothing (§12.4: a zone
 * with nothing to draw is left out): a look that draws nothing in space, a zone with no placed lights, or
 * one at no brightness (a zone waiting for its input waits dark).
 */
export function zoneFx(zone: FxZone, t: number, beats: number): ZoneFx | null {
  const kind = KIND_OF[zone.look.id ?? '']
  const box = boxOf(zone.shapes)
  if (kind === undefined || box === null || zone.brightness <= 0) return null
  const at = zone.frozen ? 0 : t
  const beat = zone.frozen ? 0 : beats
  const { hue, spread } = motifFor(zone.look)
  const level = Math.min(1, zone.brightness)
  const [cx, cy, cz] = box.centre
  const out: ZoneFx = { zoneId: zone.zoneId, stream: zone.stream }
  switch (kind) {
    case 'wander': {
      const particles: FxParticle[] = []
      for (let i = 0; i < WANDERERS; i++) {
        const angle = at * 0.3 + i * 2.39
        const swing = box.reach * (0.4 + 0.6 * ((i * 0.618) % 1))
        const [r, g, b] = hueRgb(hue + (spread * i) / WANDERERS, level * (0.5 + 0.5 * Math.sin(at * 1.3 + i)) ** 2)
        const [x, y, z] = rounded([cx + swing * Math.cos(angle), cy + swing * Math.sin(angle * 1.1), cz + 0.4 * Math.sin(at * 0.7 + i)])
        particles.push([x, y, z, r, g, b, WANDER_SIZE])
      }
      out.particles = particles
      break
    }
    case 'orbit': {
      // Two heads opposite, once round a bar, each with a fading trail.
      const particles: FxParticle[] = []
      for (const head of [0, Math.PI]) {
        for (let k = 0; k <= TRAIL; k++) {
          const angle = (beat - k * 0.08) * (Math.PI / 2) + head
          const [r, g, b] = hueRgb(hue + (head === 0 ? 0 : spread), level * (1 - k / (TRAIL + 1)))
          const [x, y, z] = rounded([cx + box.reach * Math.cos(angle), cy + box.reach * Math.sin(angle), cz])
          particles.push([x, y, z, r, g, b, round3(ORBIT_SIZE * (1 - k / (TRAIL + 2)))])
        }
      }
      out.particles = particles
      break
    }
    case 'shockwave': {
      // A shell out from the centre each beat, and a beam turning once a bar.
      const turn = (beat / 4) * 2 * Math.PI
      out.rings = [{ center: rounded(box.centre), radius: round3((beat % 1) * box.reach * 1.5), width: SHELL_WIDTH, rgb: hueRgb(hue, level), form: 'sphere' } satisfies FxRing]
      out.planes = [
        {
          point: rounded(box.centre),
          normal: rounded([-Math.sin(turn), Math.cos(turn), 0]),
          width: PLANE_WIDTH,
          rgb: hueRgb(hue + spread, level),
          ray: rounded([Math.cos(turn), Math.sin(turn), 0]),
        } satisfies FxPlane,
      ]
      break
    }
    case 'speakers':
      // A kick front from the centre each beat.
      out.rings = [{ center: rounded(box.centre), radius: round3((beat % 1) * box.reach), width: SHELL_WIDTH, rgb: hueRgb(hue, level * (1 - (beat % 1))), form: 'sphere' }]
      break
    case 'ripples': {
      // Two drops on the floor, half a cycle apart.
      const rings: FxRing[] = []
      for (const offset of [0, 0.5]) {
        const grown = (at * 0.4 + offset) % 1
        const center = rounded([cx + (offset - 0.25) * box.reach, cy, 0])
        rings.push({ center, radius: round3(grown * box.reach), width: SHELL_WIDTH, rgb: hueRgb(hue + spread * offset, level * (1 - grown)), form: 'circle' })
      }
      out.rings = rings
      break
    }
    case 'scanner': {
      // A level plane up and down the zone's height once a bar.
      const height = box.low + (box.high - box.low) * (0.5 - 0.5 * Math.cos((beat / 4) * 2 * Math.PI))
      out.planes = [{ point: rounded([cx, cy, height]), normal: [0, 0, 1], width: PLANE_WIDTH, rgb: hueRgb(hue, level) }]
      break
    }
  }
  return out
}
