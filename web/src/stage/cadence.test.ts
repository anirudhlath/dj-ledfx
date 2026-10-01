import { renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { frames } from '@/api/live'
import { Cadence, useCadence } from './cadence'
import { SPEC } from './design-numbers'

// useCadence draws through R3F's advance(); this stands in for the canvas's.
const { advance } = vi.hoisted(() => ({ advance: vi.fn() }))
vi.mock('@react-three/fiber', () => ({ useThree: (select: (state: { advance: typeof advance }) => unknown) => select({ advance }) }))

/** A 60 Hz screen. */
const SCREEN_HZ = 60
const SCREEN_MS = 1000 / SCREEN_HZ

/** Its animation frames, run by hand. */
let queued: FrameRequestCallback[] = []
function animationFrame(now: number) {
  const due = queued
  queued = []
  for (const callback of due) callback(now)
}

beforeEach(() => {
  queued = []
  advance.mockClear()
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => queued.push(callback))
  vi.stubGlobal('cancelAnimationFrame', () => {
    queued = []
  })
})

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

  // A draw asked for with invalidate() comes an animation frame late, and R3F's demand loop then
  // draws every other one: half the rate. The stage draws in the animation frame that's due.
  it('draws in the animation frame that is due, every one while frames keep coming', () => {
    const { unmount } = renderHook(() => useCadence(SCREEN_MS))
    for (let i = 0; i < SCREEN_HZ; i += 1) {
      frames.version += 1
      animationFrame(i * SCREEN_MS)
    }
    expect(advance).toHaveBeenCalledTimes(SCREEN_HZ)
    unmount()
    frames.version += 1
    animationFrame(1000)
    expect(advance).toHaveBeenCalledTimes(SCREEN_HZ)
  })

  it('draws nothing while frozen', () => {
    renderHook(() => useCadence(null))
    frames.version += 1
    animationFrame(0)
    expect(queued).toHaveLength(0)
    expect(advance).not.toHaveBeenCalled()
  })
})
