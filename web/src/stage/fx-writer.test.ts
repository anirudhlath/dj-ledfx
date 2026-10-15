import { describe, expect, it } from 'vitest'
import { FxStore } from '@/api/fx'
import type { ZoneFx } from '@/api/ws-messages'
import { FxWriter, LIVE_ONLY, sameFxPick, type FxPick } from './fx-writer'

const living: ZoneFx = {
  zoneId: 'living',
  stream: 'live',
  particles: [
    [1, 2, 3, 0.5, 2, -1, 0.4],
    [4, 5, 6, 0.1, 0.2, 0.3, 0.2],
  ],
}
const office: ZoneFx = {
  zoneId: 'office',
  stream: 'live',
  rings: [{ center: [1, 2, 0], radius: 1.5, width: 0.3, rgb: [1, 0, 0], form: 'circle' }],
  planes: [{ point: [1, 2, 3], normal: [0, 0, 2], width: 0.1, rgb: [0, 1, 0], ray: [1, 0, 0] }],
}
const preview: ZoneFx = { zoneId: 'office', stream: 'preview', rings: [{ center: [0, 0, 1], radius: 1, width: 0.2, rgb: [0, 0, 1], form: 'sphere' }] }

function store(...zones: ZoneFx[]): FxStore {
  const fx = new FxStore()
  fx.apply({ channel: 'fx', zones })
  return fx
}

describe('FxWriter', () => {
  it("writes each particle in three's world, its colour clamped to 0–1", () => {
    const writer = new FxWriter()
    expect(writer.write(store(living), LIVE_ONLY)).toBe(true)
    const [centres, colours, sizes] = writer.particles.arrays
    expect(writer.particles.count).toBe(2)
    expect([...centres.slice(0, 6)]).toEqual([1, 3, 2, 4, 6, 5])
    expect([...colours.slice(0, 3)]).toEqual([0.5, 1, 0])
    expect(sizes[0]).toBeCloseTo(0.4)
  })

  it('writes rings with their form, and planes with a unit normal and their ray', () => {
    const writer = new FxWriter()
    writer.write(store(office), LIVE_ONLY)
    const [centres, , shapes] = writer.rings.arrays
    expect([...centres.slice(0, 3), ...shapes.slice(0, 3)].map((value) => Math.round(value * 10) / 10)).toEqual([1, 0, 2, 1.5, 0.3, 1])
    const [points, normals, rays, , widths] = writer.planes.arrays
    expect([...points.slice(0, 3), ...normals.slice(0, 3), ...rays.slice(0, 3)]).toEqual([1, 3, 2, 0, 1, 0, 1, 0, 0])
    expect(widths[0]).toBeCloseTo(0.1)
  })

  it("draws the preview of the picked zone only, and leaves the hidden zones' live fx out", () => {
    const writer = new FxWriter()
    const fx = store(living, office, preview)
    writer.write(fx, LIVE_ONLY)
    expect([writer.particles.count, writer.rings.count, writer.planes.count]).toEqual([2, 1, 1])
    writer.write(fx, { preview: 'office', hidden: new Set(['office']) })
    expect([writer.particles.count, writer.rings.count, writer.planes.count]).toEqual([2, 1, 0])
    expect(writer.rings.arrays[2][2]).toBe(0) // the preview's sphere
  })

  it('writes nothing again until the store has a new picture or the stage picks other zones', () => {
    const writer = new FxWriter()
    const fx = store(living)
    const pick: FxPick = { preview: null, hidden: new Set() }
    expect(writer.write(fx, pick)).toBe(true)
    expect(writer.write(fx, pick)).toBe(false)
    fx.apply({ channel: 'fx', zones: [] })
    expect(writer.write(fx, pick)).toBe(true)
    expect(writer.particles.count).toBe(0)
    expect(writer.write(fx, { ...pick })).toBe(true)
  })

  // Frame-writer style: a picture as large as one before it allocates nothing.
  it('keeps its arrays as long as they hold the picture, and grows them to the largest', () => {
    const writer = new FxWriter()
    const fx = new FxStore()
    const many = (count: number): ZoneFx => ({
      zoneId: 'living',
      stream: 'live',
      particles: Array.from({ length: count }, (_, i) => [i, 0, 0, 1, 1, 1, 0.2] as [number, number, number, number, number, number, number]),
    })
    fx.apply({ channel: 'fx', zones: [many(10)] })
    writer.write(fx, LIVE_ONLY)
    const [generation, arrays] = [writer.particles.generation, writer.particles.arrays]
    fx.apply({ channel: 'fx', zones: [many(3)] })
    writer.write(fx, LIVE_ONLY)
    fx.apply({ channel: 'fx', zones: [many(16)] })
    writer.write(fx, LIVE_ONLY)
    expect([writer.particles.generation, writer.particles.arrays]).toEqual([generation, arrays])
    fx.apply({ channel: 'fx', zones: [many(40)] })
    writer.write(fx, LIVE_ONLY)
    expect(writer.particles.generation).toBe(generation + 1)
    expect(writer.particles.capacity).toBe(40)
    fx.apply({ channel: 'fx', zones: [many(2)] })
    writer.write(fx, LIVE_ONLY)
    expect(writer.particles.capacity).toBe(40)
  })
})

describe('sameFxPick', () => {
  it('takes picks that name the same preview and the same hidden zones for the same', () => {
    const pick = (previewed: string | null, ...hidden: string[]): FxPick => ({ preview: previewed, hidden: new Set(hidden) })
    expect(sameFxPick(pick(null, 'a', 'b'), pick(null, 'b', 'a'))).toBe(true)
    expect(sameFxPick(pick('a'), pick('a'))).toBe(true)
    expect(sameFxPick(pick(null, 'a'), pick('a', 'a'))).toBe(false)
    expect(sameFxPick(pick(null, 'a'), pick(null, 'b'))).toBe(false)
    expect(sameFxPick(pick(null, 'a'), pick(null, 'a', 'b'))).toBe(false)
  })
})
