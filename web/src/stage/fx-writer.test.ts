import { describe, expect, it } from 'vitest'
import { FxStore } from '@/api/fx'
import type { FxParticle, ZoneFx } from '@/api/ws-messages'
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
    fx.apply({ channel: 'fx', zones: [living] })
    expect(writer.write(fx, pick)).toBe(true)
    expect(writer.write(fx, { ...pick, hidden: new Set(['living']) })).toBe(true)
    expect(writer.particles.count).toBe(0)
  })

  // Final review 2: a picture wakes the stage up to 30 times a second, and a write that changed nothing drawn would upload and
  // render the canvas for nothing. The store keeps a zone whose picture is unchanged as the same object (fx.ts).
  it('says nothing changed for a picture that changes only zones it leaves out, or a pick that names the same zones', () => {
    const writer = new FxWriter()
    const fx = store(living, office)
    const focus: FxPick = { preview: null, hidden: new Set(['office']) }
    expect(writer.write(fx, focus)).toBe(true)
    // The hidden office moves; the living room is the same picture.
    fx.apply({ channel: 'fx', zones: [structuredClone(living), { ...office, rings: [] }] })
    expect(writer.write(fx, focus)).toBe(false)
    // Office's preview isn't picked.
    fx.apply({ channel: 'fx', zones: [structuredClone(living), preview] })
    expect(writer.write(fx, focus)).toBe(false)
    // Another pick naming the same zones, and one hiding a zone with nothing to draw.
    expect(writer.write(fx, { preview: null, hidden: new Set(['office']) })).toBe(false)
    expect(writer.write(fx, { preview: null, hidden: new Set(['office', 'kitchen']) })).toBe(false)
    expect(writer.particles.count).toBe(2)
    // Nothing drawn before or after.
    const empty = new FxWriter()
    const none = store()
    expect(empty.write(none, LIVE_ONLY)).toBe(false)
    none.apply({ channel: 'fx', zones: [office] })
    expect(empty.write(none, { preview: null, hidden: new Set(['office']) })).toBe(false)
  })

  it('says it changed for a picked zone that moved, a preview it picks, or a pick that names other zones', () => {
    const writer = new FxWriter()
    const fx = store(living, office, preview)
    const focus: FxPick = { preview: null, hidden: new Set(['office']) }
    writer.write(fx, focus)
    const moved: ZoneFx = { ...living, particles: [[1, 2, 3.5, 0.5, 2, -1, 0.4], living.particles![1]] }
    fx.apply({ channel: 'fx', zones: [moved, office, preview] })
    expect(writer.write(fx, focus)).toBe(true)
    expect(writer.particles.arrays[0][1]).toBe(3.5)
    expect(writer.write(fx, { preview: 'office', hidden: new Set(['office']) })).toBe(true)
    expect(writer.rings.count).toBe(1)
    expect(writer.write(fx, LIVE_ONLY)).toBe(true)
    expect([writer.rings.count, writer.planes.count]).toEqual([1, 1])
  })

  // fx-writer.ts reads the contract's tuple by index: a later optional field past the seventh is never drawn.
  it('reads a particle by index, a longer one included', () => {
    const writer = new FxWriter()
    const longer = [1, 2, 3, 0.5, 0.5, 0.5, 0.4, 9] as unknown as FxParticle
    writer.write(store({ zoneId: 'living', stream: 'live', particles: [longer] }), LIVE_ONLY)
    expect([...writer.particles.arrays[0].slice(0, 3), writer.particles.arrays[2][0]]).toEqual([1, 3, 2, expect.closeTo(0.4)])
  })

  // readFx drops a plane with a zero normal (ws-messages.ts); a picture put in the store some other way mustn't put NaN on the GPU.
  it('leaves out a plane with no normal', () => {
    const writer = new FxWriter()
    const flat: ZoneFx = { zoneId: 'office', stream: 'live', planes: [{ ...office.planes![0], normal: [0, 0, 0] }, office.planes![0]] }
    writer.write(store(flat), LIVE_ONLY)
    expect(writer.planes.count).toBe(1)
    expect(writer.planes.arrays[1].slice(0, 3).every(Number.isFinite)).toBe(true)
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
    // Fewer than before: only those are drawn, and the arrays' tail past them never is.
    expect(writer.particles.count).toBe(3)
    fx.apply({ channel: 'fx', zones: [many(16)] })
    writer.write(fx, LIVE_ONLY)
    expect([writer.particles.generation, writer.particles.arrays]).toEqual([generation, arrays])
    // Just past the capacity: at least double it.
    fx.apply({ channel: 'fx', zones: [many(20)] })
    writer.write(fx, LIVE_ONLY)
    expect([writer.particles.generation, writer.particles.capacity]).toEqual([generation + 1, 32])
    // Further past than double: as many as asked for.
    fx.apply({ channel: 'fx', zones: [many(80)] })
    writer.write(fx, LIVE_ONLY)
    expect([writer.particles.generation, writer.particles.capacity]).toEqual([generation + 2, 80])
    fx.apply({ channel: 'fx', zones: [many(2)] })
    writer.write(fx, LIVE_ONLY)
    expect([writer.particles.capacity, writer.particles.count]).toEqual([80, 2])
  })
})

describe('sameFxPick', () => {
  const pick = (previewed: string | null, ...hidden: string[]): FxPick => ({ preview: previewed, hidden: new Set(hidden) })

  it('takes picks that hide the same zones, in any order, for the same', () => {
    expect(sameFxPick(pick(null, 'a', 'b'), pick(null, 'b', 'a'))).toBe(true)
    expect(sameFxPick(pick(null, 'a'), pick(null, 'b'))).toBe(false)
    expect(sameFxPick(pick(null, 'a'), pick(null, 'a', 'b'))).toBe(false)
  })

  it('takes picks that preview the same zone for the same, and no other', () => {
    expect(sameFxPick(pick('a'), pick('a'))).toBe(true)
    expect(sameFxPick(pick('a', 'a'), pick(null, 'a'))).toBe(false)
    expect(sameFxPick(pick('a'), pick('b'))).toBe(false)
  })
})
