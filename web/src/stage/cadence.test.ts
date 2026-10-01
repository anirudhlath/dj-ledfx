import { renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { frames } from '@/api/live'
import { Cadence, useCadence } from './cadence'
import { SPEC } from './design-numbers'

/** A 60 Hz screen. */
const SCREEN_HZ = 60
const SCREEN_MS = 1000 / SCREEN_HZ

describe("the stage's cadence (§7.5)", () => {
  it('draws only when a frame has arrived since the last draw', () => {
    const cadence = new Cadence(1000 / SPEC.target.fps)
    expect(cadence.due(0, 1)).toBe(true)
    expect(cadence.due(SCREEN_MS, 1)).toBe(false)
    expect(cadence.due(2 * SCREEN_MS, 2)).toBe(true)
  })

  it("keeps a phone's rate on a 60 Hz screen: every other animation frame", () => {
    const cadence = new Cadence(1000 / SPEC.phoneFps)
    const drawn = Array.from({ length: SCREEN_HZ }, (_, i) => cadence.due(i * SCREEN_MS, i)).filter(Boolean)
    expect(drawn).toHaveLength(SPEC.phoneFps)
  })

  it('still draws an animation frame that comes a little early', () => {
    const cadence = new Cadence(SCREEN_MS)
    expect(cadence.due(100, 1)).toBe(true)
    expect(cadence.due(100 + SCREEN_MS - 1, 2)).toBe(true)
  })

})

describe('useCadence', () => {
  // Vitest's animation frames: one every 16 ms.
  beforeEach(() => {
    vi.useFakeTimers()
  })

  /** One animation frame, with a new frame in the store before it; its time. */
  function nextFrame(): number {
    frames.version += 1
    vi.advanceTimersToNextFrame()
    return performance.now()
  }

  it('draws in the animation frame a draw is due, given its time', () => {
    const draw = vi.fn()
    renderHook(() => useCadence(1000 / SPEC.target.fps, draw))
    const times = Array.from({ length: 10 }, nextFrame)
    expect(draw.mock.calls.map(([now]) => now)).toEqual(times)
  })

  it('stops when the stage goes', () => {
    const draw = vi.fn()
    const { unmount } = renderHook(() => useCadence(1000 / SPEC.target.fps, draw))
    nextFrame()
    unmount()
    for (let i = 0; i < 10; i++) nextFrame()
    expect(draw).toHaveBeenCalledTimes(1)
  })

  it('draws nothing while frozen', () => {
    const draw = vi.fn()
    renderHook(() => useCadence(null, draw))
    for (let i = 0; i < 10; i++) nextFrame()
    expect(draw).not.toHaveBeenCalled()
    expect(vi.getTimerCount()).toBe(0)
  })
})
