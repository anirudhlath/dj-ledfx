// Turns the fx store's pictures into what the GPU draws for "Effects in space" (§7.4, §12.4): each
// particle, ring and plane as one instance, its places in three's world (plan.ts's toWorld) and its
// colour clamped to 0–1. As the frame writer does, it writes into arrays it keeps: they grow to the
// most it has ever written and never shrink, so a picture allocates nothing once the stage has seen
// its largest, and the fx layer hands these very arrays to three. It writes only when what it would
// write could differ: a zone it picks has a new picture (the store keeps an unchanged one as the same
// object, fx.ts), or the stage picks other zones. It says whether it did.
import type { Id } from '@/api/contract'
import type { FxStore } from '@/api/fx'
import type { FxParticle, FxPlane, FxRing, ZoneFx } from '@/api/ws-messages'

/**
 * Which zones the stage draws: every live zone but the hidden ones, and the preview of one zone. A pick
 * is replaced, never changed in place: the writer looks again only for a new object or a new picture.
 */
export interface FxPick {
  /** The zone whose preview stream's fx are drawn (§7.6 compose), or null for none. */
  preview: Id | null
  /** Live zones whose fx aren't drawn: under the composer's preview, or outside focus's zone. */
  hidden: ReadonlySet<Id>
}

export const LIVE_ONLY: FxPick = { preview: null, hidden: new Set() }

/** Two picks naming the same zones: `FxWriter.write()` looks the store over again for a new object, so a caller keeps one. */
export function sameFxPick(a: FxPick, b: FxPick): boolean {
  if (a.preview !== b.preview || a.hidden.size !== b.hidden.size) return false
  for (const id of a.hidden) if (!b.hidden.has(id)) return false
  return true
}

const MIN_CAPACITY = 16
const NONE: readonly never[] = []

/** One kind of instance: its arrays, `sizes` floats each, and how many it holds now. */
export class FxBatch {
  count = 0
  /** Moves whenever the arrays are replaced by larger ones: the meshes then make new attributes. */
  generation = 0
  arrays: Float32Array[]
  private readonly sizes: readonly number[]

  constructor(sizes: readonly number[]) {
    this.sizes = sizes
    this.arrays = sizes.map(() => new Float32Array(0))
  }

  get capacity(): number {
    return this.arrays[0].length / this.sizes[0]
  }

  /** Room for `count`: at least double, so a growing picture makes new arrays only now and then. */
  reserve(count: number): void {
    if (count <= this.capacity) return
    const capacity = Math.max(count, this.capacity * 2, MIN_CAPACITY)
    this.arrays = this.sizes.map((size) => new Float32Array(capacity * size))
    this.generation += 1
  }
}

/** The same zones' pictures, in the same order: the store keeps a zone sent unchanged as the same object. */
function sameZones(a: readonly ZoneFx[], b: readonly ZoneFx[]): boolean {
  if (a.length !== b.length) return false
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false
  return true
}

const clamp01 = (value: number) => Math.min(1, Math.max(0, value))

/** A plan point (x, y, z up) into `out` at `at` as three's world point (x, z, y). */
function world(out: Float32Array, at: number, x: number, y: number, z: number): void {
  out[at] = x
  out[at + 1] = z
  out[at + 2] = y
}

function colour(out: Float32Array, at: number, r: number, g: number, b: number): void {
  out[at] = clamp01(r)
  out[at + 1] = clamp01(g)
  out[at + 2] = clamp01(b)
}

export class FxWriter {
  /** centre (3), colour (3), size: the glow's radius, metres (1). */
  readonly particles = new FxBatch([3, 3, 1])
  /** centre (3), colour (3), shape: radius, width and form, 0 a sphere and 1 a circle (3). */
  readonly rings = new FxBatch([3, 3, 3])
  /**
   * point (3), normal (3), ray (3; 0 for none), colour (3), width (1): a plane's thickness in metres, but with a
   * `ray` (a beam) its angle in radians, its thickness 1 m out (§12.4). Nothing draws it yet (F10 ruling 12).
   */
  readonly planes = new FxBatch([3, 3, 3, 3, 1])
  private version = -1
  private pick: FxPick | null = null
  /** The zones written, and the ones picked next: both reused from write to write. */
  private zones: ZoneFx[] = []
  private picked: ZoneFx[] = []

  /** Writes the store's picture of the picked zones; false when it would write what it wrote last. */
  write(fx: FxStore, pick: FxPick): boolean {
    if (fx.version === this.version && pick === this.pick) return false
    this.version = fx.version
    this.pick = pick
    const picked = this.picked
    picked.length = 0
    for (const zone of fx.live.values()) if (!pick.hidden.has(zone.zoneId)) picked.push(zone)
    const preview = pick.preview === null ? undefined : fx.get(pick.preview, 'preview')
    if (preview !== undefined) picked.push(preview)
    if (sameZones(picked, this.zones)) return false
    this.picked = this.zones
    this.zones = picked
    let particles = 0
    let rings = 0
    let planes = 0
    for (const zone of picked) {
      particles += zone.particles?.length ?? 0
      rings += zone.rings?.length ?? 0
      planes += zone.planes?.length ?? 0
    }
    this.particles.reserve(particles)
    this.rings.reserve(rings)
    this.planes.reserve(planes)
    this.particles.count = 0
    this.rings.count = 0
    this.planes.count = 0
    for (const zone of picked) {
      for (const particle of zone.particles ?? NONE) this.particle(particle)
      for (const ring of zone.rings ?? NONE) this.ring(ring)
      for (const plane of zone.planes ?? NONE) this.plane(plane)
    }
    return true
  }

  private particle([x, y, z, r, g, b, size]: FxParticle): void {
    const i = this.particles.count++
    const [centres, colours, sizes] = this.particles.arrays
    world(centres, i * 3, x, y, z)
    colour(colours, i * 3, r, g, b)
    sizes[i] = size
  }

  private ring({ center, radius, width, rgb, form }: FxRing): void {
    const i = this.rings.count++
    const [centres, colours, shapes] = this.rings.arrays
    world(centres, i * 3, center[0], center[1], center[2])
    colour(colours, i * 3, rgb[0], rgb[1], rgb[2])
    shapes[i * 3] = radius
    shapes[i * 3 + 1] = width
    shapes[i * 3 + 2] = form === 'circle' ? 1 : 0
  }

  private plane({ point, normal, ray, rgb, width }: FxPlane): void {
    const length = Math.hypot(normal[0], normal[1], normal[2])
    // readFx drops a plane with no normal; one put in the store another way would put NaN on the GPU.
    if (length === 0) return
    const i = this.planes.count++
    const [points, normals, rays, colours, widths] = this.planes.arrays
    world(points, i * 3, point[0], point[1], point[2])
    world(normals, i * 3, normal[0] / length, normal[1] / length, normal[2] / length)
    if (ray === undefined) world(rays, i * 3, 0, 0, 0)
    else world(rays, i * 3, ray[0], ray[1], ray[2])
    colour(colours, i * 3, rgb[0], rgb[1], rgb[2])
    widths[i] = width
  }
}
