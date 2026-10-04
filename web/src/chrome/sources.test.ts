import { describe, expect, it } from 'vitest'
import { inputsOf } from '@/api/mocks/mock-server'
import { buildScenario } from '@/api/mocks/scenarios'
import { HERO_NOW } from '@/test/live'
import { sourceStatuses } from './sources'

describe('sourceStatuses', () => {
  it("says each source's state, as Inputs.png does", () => {
    const hero = buildScenario('hero', HERO_NOW)
    expect(sourceStatuses(inputsOf(hero), hero.decks)).toEqual({
      prodjlink: 'No DJ on the network',
      music: 'Beat of “Rain”',
      internal: '118.0 · tapped 19:10',
    })
  })

  it("names the DJ's master deck, and music with nothing playing", () => {
    const dj = buildScenario('dj-playing', HERO_NOW)
    expect(sourceStatuses(inputsOf(dj), dj.decks)).toMatchObject({ prodjlink: 'Deck 2 · 124.00 +1.2%', music: 'Nothing playing' })
  })

  it('says how the internal BPM was had, and that music is not set up on an engine without it', () => {
    const hero = inputsOf(buildScenario('hero', HERO_NOW))
    const m3 = { ...hero, music: undefined, tempo: { ...hero.tempo, internal: { bpm: 120, how: 'default' as const, at: null } } }
    expect(sourceStatuses(m3, [])).toMatchObject({ music: 'Not set up', internal: '120.0 · default' })
  })
})
