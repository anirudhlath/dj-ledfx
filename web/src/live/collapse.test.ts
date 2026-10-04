import { describe, expect, it } from 'vitest'
import type { RunningZone } from '@/api/contract'
import { buildScenario } from '@/api/mocks/scenarios'
import { newestFirst } from '@/stage/show'
import { HERO_NOW } from '@/test/live'
import { collapseKey, nextStep, rowOrder, shapesAt } from './collapse'

const problems = newestFirst(buildScenario('problems', HERO_NOW).running)
const ids = (zones: readonly RunningZone[]) => zones.map((zone) => zone.zoneId)
const shapes = (step: number, selected?: string) => Object.fromEntries(shapesAt(problems, step, selected))

describe('the collapse', () => {
  // F3 decisions 1 and 2. State-Problems keeps its crashed and slow zones as cards.
  it('turns healthy zones to rows oldest first, then troubled ones, then the selected, and keeps the last a card', () => {
    expect(ids(problems)).toEqual(['office', 'kitchen', 'living', 'bedroom'])
    expect(ids(rowOrder(problems))).toEqual(['bedroom', 'office', 'living', 'kitchen'])
    expect(ids(rowOrder(problems, 'bedroom'))).toEqual(['office', 'living', 'kitchen', 'bedroom'])
    expect(shapes(0)).toEqual({ office: 'card', kitchen: 'card', living: 'card', bedroom: 'card' })
    // Step 1 drops only the footer's hint (F3 decision 34).
    expect(shapes(1)).toEqual(shapes(0))
    expect(shapes(2)).toEqual({ office: 'compact', kitchen: 'compact', living: 'compact', bedroom: 'compact' })
    expect(shapes(4)).toEqual({ office: 'row', kitchen: 'compact', living: 'compact', bedroom: 'row' })
    expect(shapes(5)).toEqual({ office: 'row', kitchen: 'compact', living: 'row', bedroom: 'row' })
    expect(shapes(10, 'bedroom')).toEqual({ office: 'row', kitchen: 'row', living: 'row', bedroom: 'compact' })
    expect(collapseKey(problems)).not.toBe(collapseKey(problems, 'bedroom'))
    expect(shapesAt([], 3).size).toBe(0)
  })

  it('takes one step at a time while the zones overflow, the hint first, and starts again from cards when the room changes', () => {
    const overflowing = { roomChanged: false, overflows: true, last: 5, hint: true }
    expect(nextStep(0, overflowing)).toBe(1)
    // No hint to drop (a frozen panel, a firmware breakdown): the cards go compact at once.
    expect(nextStep(0, { ...overflowing, hint: false })).toBe(2)
    expect(nextStep(4, overflowing)).toBe(5)
    expect(nextStep(5, overflowing)).toBe(5)
    expect(nextStep(2, { ...overflowing, overflows: false })).toBe(2)
    expect(nextStep(3, { ...overflowing, roomChanged: true })).toBe(0)
    expect(nextStep(0, { ...overflowing, roomChanged: true })).toBe(1)
  })
})
