import { describe, expect, it } from 'vitest'
import { LIVE_SPEC } from '@/design/live-numbers'
import { hexOf, hueOf, intensityOf, isDark, mix, parseHex, swatchFill, swatchGlow } from './light-colour'

// Expected values are worked from LIVE_SPEC, never typed: LIVE_SPEC is the handoff's own numbers.
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
    expect(isDark(LIVE_SPEC.swatch.darkAt)).toBe(true)
    expect(isDark(LIVE_SPEC.swatch.darkAt + 0.001)).toBe(false)
  })
})

describe('§6.6 swatch maths', () => {
  it('shows the dark colour, with no glow, at or below the dark line', () => {
    expect(swatchFill([0, 0, 0])).toBe(LIVE_SPEC.swatch.darkColour.toUpperCase())
    expect(swatchGlow([0, 0, 0], LIVE_SPEC.swatch.glowPx)).toBe('none')
  })

  it('reaches the full hue once mixBase + intensity reaches 1', () => {
    expect(swatchFill([255, 128, 0])).toBe(hexOf([255, 128, 0]))
  })

  it('mixes a dim light from the base colour toward its hue', () => {
    const intensity = 0.2
    const rgb = [0, 0, Math.round(255 * intensity)] as const
    const from = parseHex(LIVE_SPEC.swatch.fromColour)!
    const t = Math.min(1, LIVE_SPEC.swatch.mixBase + intensityOf(rgb))
    expect(swatchFill(rgb)).toBe(hexOf([from[0] * (1 - t), from[1] * (1 - t), from[2] + (255 - from[2]) * t]))
  })

  it('glows in the hue, as opaque as the light is bright', () => {
    expect(swatchGlow([0, 0, 102], LIVE_SPEC.swatch.glowPx)).toBe(`0 0 ${LIVE_SPEC.swatch.glowPx}px rgba(0, 0, 255, 0.4)`)
  })
})
