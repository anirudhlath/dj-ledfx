import { describe, expect, it } from 'vitest'
import { SPEC } from './design-numbers'
import {
  coreOf,
  haloRadiusPx,
  hexOf,
  hueOf,
  intensityOf,
  isDark,
  liftOf,
  mix,
  parseHex,
  poolRadiusM,
  swatchFill,
  swatchGlow,
} from './light-maths'

// Expected values are worked from SPEC, never typed: SPEC is the handoff's own numbers.
describe('a colour, split into hue and intensity', () => {
  it('reads and writes hex, in capitals', () => {
    expect(parseHex('#ff8000')).toEqual([255, 128, 0])
    expect(parseHex('FF8000')).toEqual([255, 128, 0])
    expect(parseHex('orange')).toBeNull()
    expect(parseHex(null)).toBeNull()
    expect(hexOf([255, 128.4, -3])).toBe('#FF8000')
  })

  it('takes the intensity from the brightest channel, and the hue from the rest', () => {
    expect(intensityOf([0, 51, 102])).toBeCloseTo(0.4)
    expect([0, 51, 102].map((channel) => hueOf(channel, 102))).toEqual([0, 0.5, 1])
    expect(hueOf(0, 0)).toBe(0)
  })

  it('mixes one channel toward another', () => {
    expect(mix(0.2, 1, 0)).toBe(0.2)
    expect(mix(0.2, 1, 0.5)).toBeCloseTo(0.6)
    expect(mix(0.2, 1, 1)).toBe(1)
  })

  it("calls a light dark at §6.6's line, on the stage too", () => {
    expect(isDark(SPEC.swatch.darkAt)).toBe(true)
    expect(isDark(SPEC.swatch.darkAt + 0.001)).toBe(false)
  })
})

describe('§7.3 per sample', () => {
  it('lifts the core toward white by more as the light brightens', () => {
    expect(liftOf(0)).toBe(SPEC.core.liftBase)
    expect([1, 0, 0].map((hue) => coreOf(hue, 0))).toEqual([1, SPEC.core.liftBase, SPEC.core.liftBase])
    expect(coreOf(0, 1)).toBeCloseTo(SPEC.core.liftBase + SPEC.core.liftPerIntensity)
  })

  it("sizes a compact light's halo as a single point, and a strip sample's smaller", () => {
    expect(haloRadiusPx(true, 1)).toBeCloseTo(SPEC.halo.pointPx * (SPEC.halo.base + SPEC.halo.perIntensity))
    expect(haloRadiusPx(false, 0)).toBeCloseTo(SPEC.halo.stripPx * SPEC.halo.base)
  })

  it('grows a pool with height and intensity, and shrinks it for a light of many samples', () => {
    const { baseM, perZ, intensityBase, perIntensity, multiSample } = SPEC.pool
    expect(poolRadiusM(1, 1, 1)).toBeCloseTo((baseM + perZ) * (intensityBase + perIntensity))
    expect(poolRadiusM(0, 0, 6)).toBeCloseTo(baseM * intensityBase * multiSample)
  })
})

describe('§6.6 swatch maths', () => {
  it('shows the dark colour, with no glow, at or below the dark line', () => {
    expect(swatchFill([0, 0, 0])).toBe(SPEC.swatch.darkColour.toUpperCase())
    expect(swatchGlow([0, 0, 0], SPEC.swatch.glowPx)).toBe('none')
  })

  it('reaches the full hue once mixBase + intensity reaches 1', () => {
    expect(swatchFill([255, 128, 0])).toBe(hexOf([255, 128, 0]))
  })

  it('mixes a dim light from the base colour toward its hue', () => {
    const intensity = 0.2
    const rgb = [0, 0, Math.round(255 * intensity)] as const
    const from = parseHex(SPEC.swatch.fromColour)!
    const t = Math.min(1, SPEC.swatch.mixBase + intensityOf(rgb))
    expect(swatchFill(rgb)).toBe(hexOf([from[0] * (1 - t), from[1] * (1 - t), from[2] + (255 - from[2]) * t]))
  })

  it('glows in the hue, as opaque as the light is bright', () => {
    expect(swatchGlow([0, 0, 102], SPEC.swatch.glowPx)).toBe(`0 0 ${SPEC.swatch.glowPx}px rgba(0, 0, 255, 0.4)`)
  })
})
