import { describe, expect, it } from 'vitest'
import type { Light, LightShape } from '@/api/contract'
import { lightFixtures } from '@/api/mocks/fixtures'
import { gridColumns, ledAlong, lightBodies, sampleCount, stageBodies, type Body } from './bodies'
import { SPEC } from './design-numbers'

const LIGHTS = lightFixtures('2026-09-23T18:04:00-05:00')
const byId = (id: string): Light => LIGHTS.find((light) => light.id === id)!
const ofKind = (kind: LightShape['kind'], keep: (light: Light) => boolean = () => true): Light =>
  LIGHTS.find((light) => light.shape?.kind === kind && keep(light))!
const tall = (light: Light) => light.shape?.kind === 'cylinder' && light.shape.height > SPEC.samples.cylinderTallerThanM

/** The LEDs each sample averages. */
function bins(body: Body): number[][] {
  return Array.from({ length: body.samples.length }, (_, s) => [...body.leds.slice(body.offsets[s], body.offsets[s + 1])])
}

describe("a light's samples (§7.3)", () => {
  it('samples each shape as §7.3 counts', () => {
    expect(sampleCount(ofKind('point').shape!)).toBe(SPEC.samples.point)
    expect(sampleCount(ofKind('line').shape!)).toBe(SPEC.samples.line)
    expect(sampleCount(ofKind('bent-line').shape!)).toBe(SPEC.samples.bentLine)
    expect(sampleCount(ofKind('grid').shape!)).toBe(SPEC.samples.grid)
    expect(sampleCount(ofKind('cylinder', tall).shape!)).toBe(SPEC.samples.cylinderTall)
    expect(sampleCount(ofKind('cylinder', (light) => !tall(light)).shape!)).toBe(SPEC.samples.cylinderShort)
  })

  it('draws a point and a short cylinder as one light, and the rest as strips', () => {
    expect(lightBodies(ofKind('point'))[0]).toMatchObject({ form: 'compact', wide: false })
    expect(lightBodies(ofKind('cylinder', (light) => !tall(light)))[0].form).toBe('compact')
    expect(lightBodies(ofKind('cylinder', tall))[0].form).toBe('strip')
    expect(lightBodies(ofKind('bent-line'))[0].form).toBe('strip')
    expect(lightBodies(ofKind('grid'))[0]).toMatchObject({ form: 'strip', wide: true })
  })

  it('runs a path from its first point to its last, and a cylinder from its base up', () => {
    const line = ofKind('bent-line')
    const path = (line.shape as Extract<LightShape, { kind: 'bent-line' }>).path
    const [body] = lightBodies(line)
    expect(body.samples[0]).toEqual(path[0])
    body.samples.at(-1)!.forEach((v, axis) => expect(v).toBeCloseTo(path.at(-1)![axis]))

    const tube = ofKind('cylinder', tall)
    const shape = tube.shape as Extract<LightShape, { kind: 'cylinder' }>
    const [cylinder] = lightBodies(tube)
    expect(cylinder.samples[0]).toEqual(shape.base)
    expect(cylinder.samples.at(-1)![2]).toBeCloseTo(shape.base[2] + shape.height)
  })

  it('gives every LED to exactly one sample, the first LED to the first sample', () => {
    for (const light of LIGHTS) {
      for (const body of lightBodies(light)) {
        const all = bins(body).flat()
        if (light.leds >= body.samples.length) expect(new Set(all).size).toBe(all.length)
        expect(Math.max(...all)).toBeLessThan(light.leds)
      }
    }
    const [rope] = lightBodies(ofKind('bent-line'))
    expect(bins(rope)[0]).toContain(0)
    expect(bins(rope).at(-1)).toContain(ofKind('bent-line').leds - 1)
  })

  it('turns the LEDs round for a reversed order', () => {
    const line = ofKind('bent-line')
    const [reversed] = lightBodies({ ...line, ledOrder: 'reverse-path' })
    expect(bins(reversed).at(-1)).toContain(0)
    expect(ledAlong(line.shape!, 'reverse-path', 0, 10)).toBeCloseTo(0.95)
  })

  it('lends a sample with no LEDs of its own the nearest one', () => {
    const tube = ofKind('cylinder', tall)
    const [few] = lightBodies({ ...tube, leds: 2 })
    expect(bins(few).every((bin) => bin.length === 1)).toBe(true)
    expect(bins(few)[0]).toEqual([0])
    expect(bins(few).at(-1)).toEqual([1])
  })

  it('lays a grid out in columns, as the engine does', () => {
    expect(gridColumns(120, 0.9, 0.3)).toBe(Math.ceil(Math.sqrt((120 * 0.9) / 0.3)))
    expect(gridColumns(10, 1, 0)).toBe(10)
    expect(gridColumns(10, 0, 1)).toBe(1)
    const pc = ofKind('grid')
    const [grid] = lightBodies(pc)
    const shape = pc.shape as Extract<LightShape, { kind: 'grid' }>
    const columns = gridColumns(pc.leds, shape.width, shape.depth)
    expect(bins(grid)[0]).toContain(0)
    expect(bins(grid).at(-1)).toContain(columns - 1)
  })

  it("draws a part with its own shape apart, leaving the light's shape the other parts", () => {
    const pc = byId('pc')
    const parts = pc.parts!
    const placed: Light = {
      ...pc,
      parts: parts.map((part, index) => (index === 1 ? { ...part, shape: { kind: 'point', position: [1, 1, 1] } } : part)),
    }
    const [own, part] = lightBodies(placed)
    const start = parts[0].leds
    expect(part.samples).toEqual([[1, 1, 1]])
    expect([...part.leds].sort((a, b) => a - b)).toEqual(Array.from({ length: parts[1].leds }, (_, j) => start + j))
    expect([...own.leds].some((led) => led >= start && led < start + parts[1].leds)).toBe(false)
  })

  it("draws nothing for a light that isn't placed", () => {
    expect(lightBodies({ ...ofKind('point'), shape: null })).toEqual([])
  })

  it("keeps the home's samples within §7.5's pool budget", () => {
    const samples = stageBodies(LIGHTS).reduce((sum, body) => sum + body.samples.length, 0)
    expect(samples).toBeLessThanOrEqual(SPEC.target.pools)
  })
})
