// Where the stage samples each light (§7.3): sample points along its shape, and which of its LEDs
// each sample averages. LED positions follow the engine's (src/dj_ledfx/home/shapes.py): LED i of n
// sits at (i + 0.5) / n along a path or up a cylinder, and a grid fills rows (or columns) of
// columns. A sample takes the LEDs nearest to it; a sample with none borrows the nearest LED.
import type { GridShape, Id, Light, LightShape, Vec2, Vec3 } from '@/api/contract'
import { SPEC } from './design-numbers'
import { radians } from './plan'

/**
 * compact: a point or a short cylinder, drawn as one light (one core at its top sample, point-sized
 * halos, a drop line when raised). strip: the rest, drawn as segments between its samples.
 */
export type BodyForm = 'compact' | 'strip'

export interface Body {
  lightId: Id
  form: BodyForm
  /** A grid's segments are the spec's widest strip; the others its narrowest. */
  wide: boolean
  /** The light's LEDs, all of its parts: frames carry this many. */
  ledCount: number
  /** Sample points in plan metres, in the shape's own order: along the path, bottom to top, across the grid. */
  samples: Vec3[]
  /** Sample s averages the light's LEDs leds[offsets[s]] to leds[offsets[s + 1] − 1], indices into its frame. */
  offsets: Uint32Array
  leds: Uint32Array
}

const DEFAULT_ORDER: Record<LightShape['kind'], string> = {
  point: '',
  line: 'along-path',
  'bent-line': 'along-path',
  cylinder: 'bottom-to-top',
  grid: 'rows',
}

/** §7.3's sample count for the shape. */
export function sampleCount(shape: LightShape): number {
  switch (shape.kind) {
    case 'point':
      return SPEC.samples.point
    case 'cylinder':
      return shape.height > SPEC.samples.cylinderTallerThanM ? SPEC.samples.cylinderTall : SPEC.samples.cylinderShort
    case 'line':
      return SPEC.samples.line
    case 'bent-line':
      return SPEC.samples.bentLine
    case 'grid':
      return SPEC.samples.grid
  }
}

/** Where along the shape sample `s` of `count` sits: its ends, and evenly between. */
const stepAt = (s: number, count: number) => (count > 1 ? s / (count - 1) : 0.5)

function alongPath(path: readonly Vec3[], t: number): Vec3 {
  const lengths = path.slice(1).map((p, i) => Math.hypot(p[0] - path[i][0], p[1] - path[i][1], p[2] - path[i][2]))
  const total = lengths.reduce((sum, length) => sum + length, 0)
  if (total <= 1e-9) return [...path[0]]
  let left = t * total
  for (let i = 0; i < lengths.length; i++) {
    if (left <= lengths[i] || i === lengths.length - 1) {
      const f = lengths[i] > 0 ? Math.min(1, left / lengths[i]) : 0
      const [a, b] = [path[i], path[i + 1]]
      return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f]
    }
    left -= lengths[i]
  }
  return [...path[path.length - 1]]
}

/** shapes.py's _rotation: roll about y, then tilt about x, then turn about z, in degrees. */
function rotate([turn, tilt, roll]: Vec3, [x, y, z]: Vec3): Vec3 {
  const [t, a, r] = [turn, tilt, roll].map(radians)
  const [x1, y1, z1] = [x * Math.cos(r) + z * Math.sin(r), y, -x * Math.sin(r) + z * Math.cos(r)]
  const [x2, y2, z2] = [x1, y1 * Math.cos(a) - z1 * Math.sin(a), y1 * Math.sin(a) + z1 * Math.cos(a)]
  return [x2 * Math.cos(t) - y2 * Math.sin(t), x2 * Math.sin(t) + y2 * Math.cos(t), z2]
}

function gridPoint(shape: GridShape, across: number): Vec3 {
  const [dx, dy, dz] = rotate(shape.rotation ?? [0, 0, 0], [across * shape.width, 0, 0])
  return [shape.center[0] + dx, shape.center[1] + dy, shape.center[2] + dz]
}

/** shapes.py's _columns: how many columns a grid of `count` LEDs has. */
export function gridColumns(count: number, width: number, depth: number): number {
  if (width <= 1e-9 && depth <= 1e-9) return Math.max(1, Math.ceil(Math.sqrt(count)))
  if (depth <= 1e-9) return count
  if (width <= 1e-9) return 1
  return Math.max(1, Math.min(count, Math.ceil(Math.sqrt((count * width) / depth))))
}

/** The shape's sample points. */
export function samplePoints(shape: LightShape): Vec3[] {
  const count = sampleCount(shape)
  const steps = Array.from({ length: count }, (_, s) => stepAt(s, count))
  switch (shape.kind) {
    case 'point':
      return steps.map(() => [...shape.position])
    case 'cylinder':
      return steps.map((t) => [shape.base[0], shape.base[1], shape.base[2] + t * shape.height])
    case 'line':
    case 'bent-line':
      return steps.map((t) => alongPath(shape.path, t))
    case 'grid':
      return steps.map((t) => gridPoint(shape, t - 0.5))
  }
}

/** How far along the shape (0–1, in sample order) LED `i` of `count` sits. */
export function ledAlong(shape: LightShape, order: string, i: number, count: number): number {
  const known = order === '' ? DEFAULT_ORDER[shape.kind] : order
  switch (shape.kind) {
    case 'point':
      return 0.5
    case 'line':
    case 'bent-line': {
      const u = (i + 0.5) / count
      return known === 'reverse-path' ? 1 - u : u
    }
    case 'cylinder': {
      const u = (i + 0.5) / count
      return known === 'top-to-bottom' ? 1 - u : u
    }
    case 'grid': {
      const columns = gridColumns(count, shape.width, shape.depth)
      const rows = Math.ceil(count / columns)
      const column = known === 'columns' ? Math.floor(i / rows) : i % columns
      return (column + 0.5) / columns
    }
  }
}

/** Bins each LED (its frame index and how far along it sits) into its nearest sample. */
function binned(leds: readonly Vec2[], samples: number): Pick<Body, 'offsets' | 'leds'> {
  const bins: number[][] = Array.from({ length: samples }, () => [])
  for (const [led, u] of leds) bins[Math.round(u * (samples - 1))].push(led)
  for (let s = 0; s < samples; s++) {
    if (bins[s].length > 0) continue
    const want = stepAt(s, samples)
    let best = leds[0]
    for (const candidate of leds) if (Math.abs(candidate[1] - want) < Math.abs(best[1] - want)) best = candidate
    bins[s].push(best[0])
  }
  const offsets = new Uint32Array(samples + 1)
  bins.forEach((bin, s) => (offsets[s + 1] = offsets[s] + bin.length))
  return { offsets, leds: Uint32Array.from(bins.flat()) }
}

function body(light: Light, shape: LightShape, leds: readonly Vec2[]): Body {
  const samples = samplePoints(shape)
  const compact = shape.kind === 'point' || (shape.kind === 'cylinder' && shape.height <= SPEC.samples.cylinderTallerThanM)
  return {
    lightId: light.id,
    form: compact ? 'compact' : 'strip',
    wide: shape.kind === 'grid',
    ledCount: light.leds,
    samples,
    ...binned(leds, samples.length),
  }
}

/**
 * Every body the light has: its own shape's, over the LEDs of the parts that have no shape of their
 * own, then one per part that has. A light (or a part) with no shape isn't drawn; nor is one with no LEDs.
 */
export function lightBodies(light: Light): Body[] {
  const order = light.ledOrder
  const parts = light.parts ?? []
  const shaped = new Set<number>()
  const bodies: Body[] = []
  let start = 0
  for (const part of parts) {
    if (part.shape != null && part.leds > 0) {
      const shape = part.shape
      const leds = Array.from({ length: part.leds }, (_, j): Vec2 => [start + j, ledAlong(shape, '', j, part.leds)])
      bodies.push(body(light, shape, leds))
      for (let j = 0; j < part.leds; j++) shaped.add(start + j)
    }
    start += part.leds
  }
  const shape = light.shape
  if (shape != null && light.leds > 0) {
    const leds: Vec2[] = []
    for (let i = 0; i < light.leds; i++) if (!shaped.has(i)) leds.push([i, ledAlong(shape, order, i, light.leds)])
    if (leds.length > 0) bodies.unshift(body(light, shape, leds))
  }
  return bodies
}

/** All the lights' bodies, in the lights' order. */
export function stageBodies(lights: readonly Light[]): Body[] {
  return lights.flatMap(lightBodies)
}
