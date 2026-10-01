import { describe, expect, it } from 'vitest'
import type { SunInput } from '@/api/contract'
import { homeFixture } from '@/api/mocks/fixtures'
import { buildScenario } from '@/api/mocks/scenarios'
import { HERO_NOW } from '@/test/live'
import { bounds } from './plan'
import { compass, sunPoint, sunReadout, sunReadoutRuns, sunScene } from './sun'

const HERO_SUN = buildScenario('hero', HERO_NOW).inputs.sun
/** A sun of this test's own: well up, south of west, setting at 20:05. */
const EVENING: SunInput = {
  elevation: 11.6,
  azimuth: 250,
  sunrise: new Date(2026, 8, 23, 7, 2).toISOString(),
  sunset: new Date(2026, 8, 23, 20, 5).toISOString(),
}

describe('the sun (§7.4)', () => {
  it('names the nearest compass point', () => {
    expect([0, 44, 46, 90, 180, 260, 315, 359, -90].map(compass)).toEqual(['N', 'NE', 'NE', 'E', 'S', 'W', 'NW', 'N', 'W'])
  })

  it("puts the sun a metre outside the home's box, the way its azimuth points, as high as it stands", () => {
    const { min, max } = bounds(homeFixture.outline)
    const due = sunPoint({ ...homeFixture, northOffsetDeg: 0 }, 0, 270)
    expect(due[0]).toBeCloseTo(min[0] - 1)
    expect(due[1]).toBeCloseTo((min[1] + max[1]) / 2)
    const west = sunPoint(homeFixture, 0, 270)
    expect(west[0]).toBeLessThan(min[0])
    expect(west[2]).toBeCloseTo(homeFixture.ceiling)
    const south = sunPoint(homeFixture, 0, 180)
    expect(south[1]).toBeGreaterThan(max[1])
    expect(sunPoint(homeFixture, 30, 270)[2]).toBeGreaterThan(west[2])
    // A home whose plan is turned: north 90° clockwise from plan-up puts a north sun to the plan's east.
    expect(sunPoint({ ...homeFixture, northOffsetDeg: 90 }, 0, 0)[0]).toBeGreaterThan(max[0])
  })

  it('labels the sun, and writes its readout, in whole degrees with the compass point and the sunset', () => {
    expect(sunScene(homeFixture, EVENING)!.label).toBe('SUN 12° · W')
    expect(sunReadout(EVENING)).toBe('Sun 12° · W · sets 20:05')
  })

  // Main.html sets the elevation and the compass point in mono, between the readout's own words.
  it("sets the readout's elevation and compass point apart, as Main.png draws them in mono", () => {
    expect(sunReadoutRuns(EVENING)).toEqual(['Sun ', '12° · W', ' · sets 20:05'])
    expect(sunReadoutRuns(EVENING)!.join('')).toBe(sunReadout(EVENING))
    expect(sunReadoutRuns(null)).toBeNull()
    expect(sunReadoutRuns({ ...EVENING, elevation: -4 })).toBeNull()
  })

  it("draws the hero sun's path above the horizon, ending at the sun", () => {
    const scene = sunScene(homeFixture, HERO_SUN)!
    expect(scene.path.at(-1)).toEqual(scene.at)
    expect(scene.path.length).toBe(HERO_SUN.path!.length + 1)
  })

  // Mi3: engine M6 settles the sun's final shape, so the stage trusts no field of it.
  it('takes a sun without a finite elevation and azimuth for no sun', () => {
    const broken = [
      { ...EVENING, azimuth: undefined },
      { ...EVENING, azimuth: '250' },
      { ...EVENING, elevation: Number.POSITIVE_INFINITY },
      { ...EVENING, elevation: null },
    ] as unknown as SunInput[]
    for (const sun of broken) {
      expect(sunScene(homeFixture, sun)).toBeNull()
      expect(sunReadout(sun)).toBeNull()
    }
  })

  it('draws only the points of the path it can place', () => {
    const path = [...HERO_SUN.path!, { at: HERO_SUN.sunset, elevation: 5, azimuth: Number.NaN }]
    expect(sunScene(homeFixture, { ...HERO_SUN, path })!.path.flat().every(Number.isFinite)).toBe(true)
    expect(sunScene(homeFixture, { ...HERO_SUN, path: 'soon' } as unknown as SunInput)!.path).toHaveLength(1)
  })

  it("leaves the sunset out of the readout when it doesn't parse", () => {
    expect(sunReadout({ ...EVENING, sunset: 'soon' })).toBe('Sun 12° · W')
    expect(sunReadout({ ...EVENING, sunset: null } as unknown as SunInput)).toBe('Sun 12° · W')
  })

  // Review focus 1: engine M2 serves no sun until M6; and at night it's down.
  it('shows no sun and no readout when the server has no sun, or it has set', () => {
    expect(sunScene(homeFixture, null)).toBeNull()
    expect(sunReadout(undefined)).toBeNull()
    const set: SunInput = { ...HERO_SUN, elevation: -4 }
    expect(sunScene(homeFixture, set)).toBeNull()
    expect(sunReadout(set)).toBeNull()
    const noPath: SunInput = { ...HERO_SUN, path: undefined }
    expect(sunScene(homeFixture, noPath)!.path).toHaveLength(1)
  })
})
