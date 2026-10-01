import { describe, expect, it } from 'vitest'
import type { Light, LightUpdate } from '@/api/contract'
import { lightFixtures } from '@/api/mocks/fixtures'
import { lightShow, lightState, restingColour } from './show'

const light = (patch: Partial<Light>): Light => ({ ...lightFixtures('2026-09-23T18:04:00-05:00')[0], ...patch })

describe('what the stage draws for a light', () => {
  it.each([
    ['streaming', 'frames'],
    ['own-effect', 'frames'],
    ['streamed-copy', 'frames'],
    ['offline', 'offline'],
    ['switched-off', 'switched-off'],
  ] as const)('a %s light shows %s', (status, show) => {
    expect(lightShow(lightState(light({ status }), undefined))).toBe(show)
  })

  it("shows an idle light's own colour while it's on, and nothing while it's off or unknown", () => {
    expect(lightShow(lightState(light({ status: 'idle', power: true, colour: '#ff8000' }), undefined))).toBe('resting')
    expect(lightShow(lightState(light({ status: 'idle', power: false, colour: '#ff8000' }), undefined))).toBe('dark')
    expect(lightShow(lightState(light({ status: 'idle', power: null, colour: null }), undefined))).toBe('dark')
    expect(lightShow(lightState(light({ status: 'reconnecting', power: true, colour: 'warm' }), undefined))).toBe('dark')
  })

  it("believes the latest push over REST's record", () => {
    const update: LightUpdate = { id: 'x', status: 'offline', statusSince: '2026-09-23T19:00:00-05:00', ownEffect: null, power: null, colour: null }
    expect(lightShow(lightState(light({ status: 'streaming' }), update))).toBe('offline')
    expect(lightState(light({ status: 'streaming' }), update).since).toBe(update.statusSince)
  })

  it('rests on its colour only while it is on', () => {
    expect(restingColour(lightState(light({ power: true, colour: '#102030' }), undefined))).toEqual([16, 32, 48])
    expect(restingColour(lightState(light({ power: false, colour: '#102030' }), undefined))).toBeNull()
  })
})
