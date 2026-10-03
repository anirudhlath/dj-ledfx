import { describe, expect, it } from 'vitest'
import type { ScenarioState } from '@/api/mocks/scenarios'
import { HERO_NOW } from '@/test/live'
import { runningIn, scenarioWorld } from '@/test/zones'
import { zoneView } from '@/zones/zone-view'
import { effectWord, firmwareGroups, firmwareWords } from './firmware'

/** The firmware scenario's whole home: its lights as its card has them, after `change`. */
function homeLights(change?: (state: ScenarioState) => void) {
  const { state, world } = scenarioWorld('firmware', change)
  return zoneView(runningIn(state, 'home'), world, HERO_NOW).lights
}

const named = (state: ScenarioState, name: string) => state.lights.find((light) => light.name === name)!

describe('effectWord', () => {
  // §9.1: "Streamed copy · Govee has no Flame".
  it("drops the protocol's word from an effect's name, and only that", () => {
    expect(effectWord('LIFX Flame')).toBe('Flame')
    expect(effectWord('LIFX waveform')).toBe('waveform')
    expect(effectWord('Flame')).toBe('Flame')
    expect(effectWord('LIFX')).toBe('LIFX')
  })
})

describe('firmwareGroups', () => {
  // State-Firmware: "Own effect 7", "Own effect · waveform 11", "Streamed copy 1".
  it('groups the lights by state, and folds an effect that four or more lights run', () => {
    const groups = firmwareGroups(homeLights())
    expect(groups.map(({ title, lights, folded }) => [title, lights.length, folded])).toEqual([
      ['Own effect', 7, null],
      ['Own effect · waveform', 11, '11 lights · LIFX waveform'],
      ['Streamed copy', 1, null],
    ])
    // Three candles on one effect stay a row each.
    expect(groups[0].lights.filter(({ state }) => state.ownEffect === 'LIFX Flame')).toHaveLength(3)
    expect(firmwareWords(groups[0].lights[0].state)).toBe(groups[0].lights[0].state.ownEffect)
    expect(firmwareWords(groups[2].lights[0].state)).toBe('Streamed copy of Flame')
  })

  it('folds at four, and leaves out a light that streams the look', () => {
    const groups = firmwareGroups(
      homeLights((state) => {
        Object.assign(named(state, 'TV Lamp'), { ownEffect: 'LIFX Flame' })
        Object.assign(named(state, 'Corner Lamp'), { status: 'streaming', ownEffect: null })
      }),
    )
    expect(groups.find(({ title }) => title === 'Own effect · Flame')).toMatchObject({ folded: '4 lights · LIFX Flame' })
    expect(groups.find(({ title }) => title === 'Own effect')!.lights.map(({ light }) => light.name)).not.toContain('TV Lamp')
    expect(groups.some(({ status }) => status === 'streamed-copy')).toBe(false)
  })
})
