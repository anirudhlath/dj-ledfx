import { describe, expect, it } from 'vitest'
import { SPEC } from './design-numbers'
import { coreOf, haloRadiusPx, liftOf, poolRadiusM } from './light-maths'

// Expected values are worked from SPEC, never typed: SPEC is the handoff's own numbers.
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
