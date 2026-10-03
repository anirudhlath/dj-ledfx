import { describe, expect, it } from 'vitest'
import { buildScenario, type ScenarioName } from '@/api/mocks/scenarios'
import { HERO_NOW } from '@/test/live'
import { runningSummary } from './words'

function summaryOf(name: ScenarioName): string {
  const { running, overlays, lights, previewOnly } = buildScenario(name, HERO_NOW)
  return runningSummary(running, overlays.length, lights.length, previewOnly)
}

describe('runningSummary', () => {
  // §8.1 "Running · 3 zones · all 19 lights", and each render's header.
  it("says what runs as each render's header does", () => {
    expect(summaryOf('hero')).toBe('3 zones · all 19 lights')
    expect(summaryOf('firmware')).toBe('1 zone · all 19 lights')
    expect(summaryOf('doorbell')).toBe('3 zones + 1 overlay')
    expect(summaryOf('problems')).toBe('4 zones · 1 stopped')
    expect(summaryOf('preview-only')).toBe('on screen only')
    const { running } = buildScenario('hero', HERO_NOW)
    expect(runningSummary(running.slice(1, 2), 0, 19, false)).toMatch(/^1 zone · \d+ lights?$/)
  })
})
