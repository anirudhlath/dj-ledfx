import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { SPEC } from './design-numbers'
import {
  DEFAULT_STAGE_VIEW,
  nextRotation,
  nextZoom,
  readStageView,
  useStageView,
  writeStageView,
  ZOOM_STEPS,
  type StoredView,
} from './view-memory'

/** A Storage whose every call throws, as a blocked one does. */
function throwingStorage(): Storage {
  const refuse = () => {
    throw new DOMException('The operation is insecure.', 'SecurityError')
  }
  return { length: 0, clear: refuse, getItem: refuse, key: refuse, removeItem: refuse, setItem: refuse }
}

const PLAN: StoredView = { view: { mode: 'plan', rotateDeg: -SPEC.rotate.stepDeg, zoom: ZOOM_STEPS[2] }, labels: false }

beforeEach(() => {
  window.localStorage.clear()
})

describe('the remembered view (§7.2)', () => {
  it('remembers a view per route', () => {
    const storage = window.localStorage
    writeStageView(storage, 'live', PLAN)
    expect(readStageView(storage, 'live')).toEqual(PLAN)
    expect(readStageView(storage, 'map')).toEqual(DEFAULT_STAGE_VIEW)
  })

  // Review focus 5: an old app's, another tab's or a hand-edited value; private mode; a full disk.
  it("ignores a stored view it can't read, and survives storage that throws", () => {
    const storage = window.localStorage
    for (const junk of ['{', '"plan"', '[]', 'null', '{"mode":"top","rotateDeg":7,"zoom":9,"labels":"yes"}']) {
      storage.setItem('dj-ledfx:stage-view:live', junk)
      expect(readStageView(storage, 'live')).toEqual(DEFAULT_STAGE_VIEW)
    }
    storage.setItem('dj-ledfx:stage-view:live', JSON.stringify({ mode: 'plan', rotateDeg: 'x', zoom: ZOOM_STEPS[1] }))
    expect(readStageView(storage, 'live')).toEqual({ view: { mode: 'plan', rotateDeg: 0, zoom: ZOOM_STEPS[1] }, labels: true })

    const blocked = throwingStorage()
    expect(readStageView(blocked, 'live')).toEqual(DEFAULT_STAGE_VIEW)
    expect(() => writeStageView(blocked, 'live', PLAN)).not.toThrow()
    expect(readStageView(null, 'live')).toEqual(DEFAULT_STAGE_VIEW)
  })

  it('steps the rotation round within its range, and the zoom up to its last step', () => {
    const { stepDeg, maxDeg } = SPEC.rotate
    expect(nextRotation(0)).toBe(stepDeg)
    expect(nextRotation(maxDeg)).toBe(-maxDeg)
    const seen = new Set<number>()
    for (let deg = 0, i = 0; i < 100; i++, deg = nextRotation(deg)) seen.add(deg)
    expect(Math.max(...seen)).toBe(maxDeg)
    expect(Math.min(...seen)).toBe(-maxDeg)
    expect(nextZoom(ZOOM_STEPS[0])).toBe(ZOOM_STEPS[1])
    expect(nextZoom(ZOOM_STEPS[ZOOM_STEPS.length - 1])).toBeNull()
  })

  it('keeps the view in state and in storage', () => {
    const storage = window.localStorage
    const { result } = renderHook(() => useStageView('live', storage))
    expect(result.current[0]).toEqual(DEFAULT_STAGE_VIEW)
    act(() => result.current[1](PLAN))
    expect(result.current[0]).toEqual(PLAN)
    expect(renderHook(() => useStageView('live', storage)).result.current[0]).toEqual(PLAN)
  })
})
