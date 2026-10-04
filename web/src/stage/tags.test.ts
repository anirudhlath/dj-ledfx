import { describe, expect, it } from 'vitest'
import { buildScenario, type ScenarioName } from '@/api/mocks/scenarios'
import { HERO_NOW } from '@/test/live'
import { stageBodies } from './bodies'
import { zoneTags } from './tags'

function tagsOf(name: ScenarioName) {
  const { running, lights } = buildScenario(name, HERO_NOW)
  return zoneTags(running, stageBodies(lights))
}

describe('the zone tags (F3 decision 18)', () => {
  // State-Problems and State-Transition.
  it('tag a crashed, a slow and a moving zone, newest first, and nothing that runs well', () => {
    expect(tagsOf('problems').map(({ zoneId, kind, text }) => ({ zoneId, kind, text }))).toEqual([
      { zoneId: 'kitchen', kind: 'crashed', text: 'Lava stopped · 19:12' },
      { zoneId: 'living', kind: 'slow', text: '38 fps · target 60' },
    ])
    expect(tagsOf('transition')).toEqual([
      expect.objectContaining({ zoneId: 'living', kind: 'transition', text: 'Fireflies → Embers · dissolving', progress: 0.62, durationS: 3 }),
    ])
    expect(tagsOf('hero')).toEqual([])
    // A zone with no placed lights has nowhere to go.
    expect(zoneTags(buildScenario('problems', HERO_NOW).running, [])).toEqual([])
  })
})
