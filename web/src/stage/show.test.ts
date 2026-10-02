import { describe, expect, it } from 'vitest'
import type { Light, LightUpdate } from '@/api/contract'
import { lightFixtures } from '@/api/mocks/fixtures'
import { buildScenario } from '@/api/mocks/scenarios'
import { HERO_NOW, HERO_SINCE } from '@/test/live'
import { isDrawn, isStreamed, lightState, lightStates, newestFirst, restingColour } from './show'

const light = (patch: Partial<Light>): Light => ({ ...lightFixtures(HERO_SINCE)[0], ...patch })

describe('what the stage draws for a light', () => {
  it.each([
    ['streaming', true, true],
    ['own-effect', true, true],
    ['streamed-copy', true, true],
    ['idle', false, true],
    ['offline', false, false],
    ['switched-off', false, false],
  ] as const)('a %s light: streamed %s, drawn %s', (status, streamed, drawn) => {
    const state = lightState(light({ status }), undefined)
    expect([isStreamed(state), isDrawn(state)]).toEqual([streamed, drawn])
  })

  it("believes the latest push over REST's record", () => {
    const update: LightUpdate = { id: 'x', status: 'offline', statusSince: '2026-09-23T19:00:00-05:00', ownEffect: null, power: null, colour: null }
    const state = lightState(light({ status: 'streaming' }), update)
    expect(state.status).toBe('offline')
    expect(state.since).toBe(update.statusSince)
    const [only] = lightStates([light({ id: 'x', status: 'streaming' })], { x: update }).values()
    expect(only).toEqual(state)
  })

  it('rests on its colour only while it is on, and on none it can read', () => {
    expect(restingColour(lightState(light({ power: true, colour: '#102030' }), undefined))).toEqual([16, 32, 48])
    expect(restingColour(lightState(light({ power: false, colour: '#102030' }), undefined))).toBeNull()
    expect(restingColour(lightState(light({ power: null, colour: null }), undefined))).toBeNull()
    expect(restingColour(lightState(light({ power: true, colour: 'warm' }), undefined))).toBeNull()
  })

  it('puts the newest running zone first, and leaves the list it was given alone', () => {
    const running = buildScenario('hero', HERO_NOW).running
    const given = [...running]
    const times = newestFirst(running).map((zone) => Date.parse(zone.since))
    expect(times).toEqual([...given].map((zone) => Date.parse(zone.since)).sort((a, b) => b - a))
    expect(running).toEqual(given)
  })
})
