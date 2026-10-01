import { describe, expect, it } from 'vitest'
import type { Id, Light } from '@/api/contract'
import { decodeFrame, encodeFrame, FrameStore } from '@/api/frames'
import { HOME_TOTALS, homeFixture, lightFixtures } from '@/api/mocks/fixtures'
import { lightBodies, stageBodies, type Body } from './bodies'
import { SPEC } from './design-numbers'
import { FrameWriter, writerEntries, type WriterColours, type WriterEntry } from './frame-writer'
import { coreColour, haloRadiusPx, liftOf, poolRadiusM } from './light-maths'
import { lightState } from './show'

const LIGHTS = lightFixtures('2026-09-23T18:04:00-05:00')
const POINT = LIGHTS.find((light) => light.shape?.kind === 'point')!
const STRIP = LIGHTS.find((light) => light.shape?.kind === 'bent-line')!
const GRID = LIGHTS.find((light) => light.shape?.kind === 'grid')!
// The writer's two dark colours, as the palette would pass them. Any two distinct colours do.
const COLOURS: WriterColours = { lightOff: [0.1, 0.2, 0.3], stripDark: [0.4, 0.5, 0.6] }

const bodyOf = (light: Light): Body => lightBodies(light)[0]
const entry = (light: Light, patch: Partial<WriterEntry> = {}): WriterEntry => ({
  body: bodyOf(light),
  show: 'frames',
  resting: null,
  room: 1,
  ...patch,
})

let seq = 0
function stream(frames: FrameStore, id: Id, rgb: ArrayLike<number>): void {
  seq += 1
  decodeFrame(encodeFrame(2, id, seq, Uint8Array.from(rgb)), 2, frames, 0)
}
/** `count` LEDs, every one `rgb`. */
const solid = (count: number, rgb: [number, number, number]) => Array.from({ length: count }, () => rgb).flat()

describe('the frame writer', () => {
  it('lays out a halo and a pool per sample, a core per compact light, and the segments of each strip', () => {
    const writer = new FrameWriter([entry(POINT), entry(STRIP), entry(GRID)], COLOURS)
    const [point, strip, grid] = [POINT, STRIP, GRID].map((light) => bodyOf(light).samples.length)
    expect(writer.glows).toBe(point + strip + grid)
    expect(writer.cores).toBe(1)
    expect(writer.narrow.segments).toBe(strip - 1)
    expect(writer.wide.segments).toBe(grid - 1)
    // three's world is (x, z, y): the point's core sits at its plan position, turned.
    const [x, y, z] = bodyOf(POINT).samples[0]
    expect([...writer.coreCentres]).toEqual([x, z, y].map(Math.fround))
  })

  it('draws a streamed sample in its hue at its intensity, and lifts the core toward white', () => {
    const frames = new FrameStore()
    stream(frames, POINT.id, solid(POINT.leds, [0, 51, 102]))
    const writer = new FrameWriter([entry(POINT)], COLOURS)
    writer.write(frames)
    const intensity = 102 / 255
    expect([...writer.haloColours].map((v) => +v.toFixed(5))).toEqual([0, 0.5 * intensity, intensity].map((v) => +v.toFixed(5)))
    expect(writer.haloSizes[0]).toBeCloseTo(haloRadiusPx(true, intensity))
    expect(writer.poolRadii[0]).toBeCloseTo(poolRadiusM(bodyOf(POINT).samples[0][2], intensity, 1))
    expect([...writer.coreColours].map((v) => +v.toFixed(5))).toEqual(coreColour([0, 0.5, 1], intensity).map((v) => +v.toFixed(5)))
    expect(writer.coreSizes[0]).toBe(Math.fround(SPEC.core.px))
  })

  it('averages the LEDs each sample takes', () => {
    const frames = new FrameStore()
    const body = bodyOf(STRIP)
    const rgb = new Uint8Array(STRIP.leds * 3)
    // One of the first sample's LEDs full red, the rest black.
    const first = [...body.leds.slice(body.offsets[0], body.offsets[1])]
    expect(first.length).toBeGreaterThan(1)
    rgb[first[0] * 3] = 255
    stream(frames, STRIP.id, rgb)
    const writer = new FrameWriter([entry(STRIP)], COLOURS)
    writer.write(frames)
    expect(writer.haloColours[0]).toBeCloseTo(1 / first.length)
  })

  it('shows a dark compact light as a light-off dot, with no halo or pool', () => {
    const frames = new FrameStore()
    stream(frames, POINT.id, solid(POINT.leds, [2, 2, 2]))
    const writer = new FrameWriter([entry(POINT)], COLOURS)
    writer.write(frames)
    expect(writer.haloSizes[0]).toBe(0)
    expect(writer.poolRadii[0]).toBe(0)
    expect([...writer.coreColours]).toEqual(COLOURS.lightOff.map(Math.fround))
    expect(writer.coreSizes[0]).toBe(Math.fround(SPEC.core.darkPx))
  })

  it("rests on the light's own colour until its frames come, and draws a dark light dark", () => {
    const frames = new FrameStore()
    const waiting = new FrameWriter([entry(POINT, { resting: [255, 0, 0] })], COLOURS)
    waiting.write(frames)
    expect(waiting.haloColours[0]).toBeCloseTo(1)
    const resting = new FrameWriter([entry(POINT, { show: 'resting', resting: [255, 0, 0] })], COLOURS)
    resting.write(frames)
    expect(resting.haloColours[0]).toBeCloseTo(1)
    const dark = new FrameWriter([entry(POINT, { show: 'dark', resting: [255, 0, 0] })], COLOURS)
    dark.write(frames)
    expect(dark.haloSizes[0]).toBe(0)
  })

  it('gives offline and switched-off lights nothing to draw', () => {
    const writer = new FrameWriter([entry(POINT, { show: 'offline' }), entry(STRIP, { show: 'switched-off' })], COLOURS)
    expect([writer.glows, writer.cores, writer.narrow.segments, writer.wide.segments]).toEqual([0, 0, 0, 0])
  })

  it('lights no floor for a light in no room', () => {
    const frames = new FrameStore()
    stream(frames, POINT.id, solid(POINT.leds, [255, 255, 255]))
    const writer = new FrameWriter([entry(POINT, { room: 0 })], COLOURS)
    writer.write(frames)
    expect(writer.haloSizes[0]).toBeGreaterThan(0)
    expect(writer.poolRadii[0]).toBe(0)
  })

  // Review focus 2: §15.1's LED counts are estimates, so frames may not match the map.
  it("draws a frame shorter or longer than the map's LED count without reading past it", () => {
    const frames = new FrameStore()
    const half = Math.floor(STRIP.leds / 2)
    stream(frames, STRIP.id, solid(half, [255, 255, 255]))
    const writer = new FrameWriter([entry(STRIP)], COLOURS)
    writer.write(frames)
    const sizes = [...writer.haloSizes]
    expect(sizes[0]).toBeGreaterThan(0)
    expect(sizes.at(-1)).toBe(0)
    expect([...writer.haloColours, ...writer.narrow.colours].every(Number.isFinite)).toBe(true)
    expect(writer.leds).toBe(half)

    stream(frames, STRIP.id, solid(STRIP.leds * 2, [255, 255, 255]))
    writer.write(frames)
    expect([...writer.haloSizes].every((size) => size > 0)).toBe(true)
    expect(writer.leds).toBe(STRIP.leds)
  })

  it('colours a strip from the dark strip colour toward its hue, and keeps it visible when dark', () => {
    const frames = new FrameStore()
    stream(frames, STRIP.id, solid(STRIP.leds, [0, 0, 0]))
    const writer = new FrameWriter([entry(STRIP)], COLOURS)
    writer.write(frames)
    expect([...writer.narrow.colours.slice(0, 6)]).toEqual([...COLOURS.stripDark, ...COLOURS.stripDark].map(Math.fround))
    stream(frames, STRIP.id, solid(STRIP.leds, [255, 0, 0]))
    writer.write(frames)
    expect([...writer.narrow.colours.slice(0, 3)]).toEqual([1, 0, 0])
  })

  it("counts a light's LEDs once, however many bodies it has, and only from frames", () => {
    const pc = LIGHTS.find((light) => light.parts !== null)!
    const placed: Light = {
      ...pc,
      parts: pc.parts!.map((part, index) => (index === 0 ? { ...part, shape: { kind: 'point', position: [1, 1, 1] } } : part)),
    }
    const frames = new FrameStore()
    stream(frames, pc.id, solid(pc.leds, [9, 9, 9]))
    const writer = new FrameWriter(lightBodies(placed).map((body) => ({ body, show: 'frames', resting: null, room: 1 })), COLOURS)
    writer.write(frames)
    expect(writer.leds).toBe(pc.leds)
    writer.write(new FrameStore())
    expect(writer.leds).toBe(0)
  })

  it("draws the whole home's LEDs 600 times well inside a second", () => {
    const frames = new FrameStore()
    for (const light of LIGHTS) stream(frames, light.id, solid(light.leds, [200, 120, 40]))
    const states = new Map(LIGHTS.map((light) => [light.id, lightState({ ...light, status: 'streaming' }, undefined)]))
    const writer = new FrameWriter(writerEntries(stageBodies(LIGHTS), LIGHTS, states, homeFixture.rooms), COLOURS)
    const started = performance.now()
    for (let i = 0; i < 600; i++) writer.write(frames)
    expect(performance.now() - started).toBeLessThan(1000)
    expect(writer.leds).toBe(HOME_TOTALS.leds)
  })
})

describe('the writer entries', () => {
  it("give each body its light's show, resting colour and room", () => {
    const light: Light = { ...POINT, status: 'idle', power: true, colour: '#00ff00' }
    const states = new Map([[light.id, lightState(light, undefined)]])
    const [only] = writerEntries(lightBodies(light), [light], states, homeFixture.rooms)
    expect(only).toMatchObject({ show: 'resting', resting: [0, 255, 0] })
    expect(homeFixture.rooms[only.room - 1].id).toBe(light.room)
    expect(liftOf(0)).toBe(SPEC.core.liftBase)
  })
})
