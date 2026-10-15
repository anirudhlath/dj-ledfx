import { describe, expect, it } from 'vitest'
import type { LightShape } from '../contract'
import { parseMessage } from '../ws-messages'
import { lookFixtures } from './fixtures'
import { drawsInSpace, zoneFx, type FxZone } from './mock-fx'

const SHAPES: LightShape[] = [
  { kind: 'point', position: [1, 1, 1] },
  { kind: 'cylinder', base: [3, 2, 0], height: 1.5, radius: 0.1 },
]
const zone = (lookId: string, extra: Partial<FxZone> = {}): FxZone => ({
  zoneId: 'living',
  stream: 'live',
  look: lookFixtures.find((look) => look.id === lookId)!,
  shapes: SHAPES,
  brightness: 1,
  frozen: false,
  ...extra,
})

// §12.4's "What draws what (M8's first slice)".
const PARTICLE_LOOKS = ['fireflies', 'embers', 'rain', 'snow', 'spotlights', 'bursts', 'fountain', 'flock', 'vortex', 'comets', 'ball']

describe('zoneFx', () => {
  it.each(PARTICLE_LOOKS)('draws particles for %s', (lookId) => {
    const fx = zoneFx(zone(lookId), 3, 6)!
    expect(fx.particles!.length).toBeGreaterThan(0)
    expect(fx.rings).toBeUndefined()
    expect(fx.planes).toBeUndefined()
  })

  it('draws Shockwave as a shell and a beam with a ray, Speaker waves as a shell, Ripples as level circles and Scanner as a level plane', () => {
    const shockwave = zoneFx(zone('shockwave'), 3, 6.5)!
    expect(shockwave.rings!.map((ring) => ring.form)).toEqual(['sphere'])
    expect(shockwave.planes![0].ray).toBeDefined()
    expect(zoneFx(zone('speakers'), 3, 6.5)!.rings!.map((ring) => ring.form)).toEqual(['sphere'])
    const ripples = zoneFx(zone('ripples'), 3, 6.5)!
    expect(ripples.rings!.map((ring) => [ring.form, ring.center[2]])).toEqual([['circle', 0], ['circle', 0]])
    const scanner = zoneFx(zone('scanner'), 3, 6.5)!.planes!
    expect(scanner.map((plane) => [plane.normal, plane.ray])).toEqual([[[0, 0, 1], undefined]])
    // Between the zone's lowest and highest points.
    expect(scanner[0].point[2]).toBeGreaterThanOrEqual(0)
    expect(scanner[0].point[2]).toBeLessThanOrEqual(1.5)
  })

  it('draws nothing for a look with nothing in space, a zone with no placed lights or one at no brightness', () => {
    expect(drawsInSpace({ id: 'homesunset' })).toBe(false)
    expect(zoneFx(zone('homesunset'), 3, 6)).toBeNull()
    expect(zoneFx(zone('fireflies', { shapes: [] }), 3, 6)).toBeNull()
    expect(zoneFx(zone('fireflies', { brightness: 0 }), 3, 6)).toBeNull()
  })

  it('moves with time and the beat, holds a crashed zone, and scales its colours by the brightness', () => {
    expect(zoneFx(zone('fireflies'), 3, 6)).not.toEqual(zoneFx(zone('fireflies'), 3.5, 6))
    expect(zoneFx(zone('scanner'), 3, 6)).not.toEqual(zoneFx(zone('scanner'), 3, 6.5))
    expect(zoneFx(zone('comets', { frozen: true }), 3, 6)).toEqual(zoneFx(zone('comets', { frozen: true }), 9, 13))
    const full = zoneFx(zone('scanner'), 3, 6)!.planes![0].rgb
    const half = zoneFx(zone('scanner', { brightness: 0.5 }), 3, 6)!.planes![0].rgb
    half.forEach((channel, i) => expect(channel).toBeCloseTo(full[i] / 2, 2))
  })

  // The mock speaks what the client reads: every picture survives parseMessage whole.
  it.each([...PARTICLE_LOOKS, 'shockwave', 'speakers', 'ripples', 'scanner'])('sends %s as the client reads it, rounded to 3 decimals', (lookId) => {
    const zones = [zoneFx(zone(lookId), 3.21, 7.3)!]
    const text = JSON.stringify({ channel: 'fx', zones })
    expect(parseMessage(text)).toEqual({ channel: 'fx', zones })
    for (const number of text.match(/-?\d+\.\d+/g) ?? []) expect(number.split('.')[1].length).toBeLessThanOrEqual(3)
  })
})
