import { describe, expect, it } from 'vitest'
import { LIVE_SPEC } from '@/design/live-numbers'
import { stageBehaviour, type StageOptions } from './behaviour'
import { SPEC } from './design-numbers'

const behaviour = (options: Partial<StageOptions>) =>
  stageBehaviour({ mode: 'live', variant: 'desktop', reducedMotion: false, labels: true, ...options })

describe("the stage's behaviour in each mode (§7.6) and on the phone (§8.10)", () => {
  it('is all there on desktop Live, labels as the Labels switch says', () => {
    expect(behaviour({})).toEqual({
      interactive: true,
      overlays: true,
      labels: true,
      sunLabel: true,
      greyed: false,
      cadenceMs: 1000 / SPEC.target.fps,
    })
    expect(behaviour({ labels: false })).toMatchObject({ labels: false, sunLabel: true })
  })

  it("has no labels or overlays on the phone, and draws at the phone's rate", () => {
    expect(behaviour({ variant: 'phone' })).toMatchObject({ interactive: true, overlays: false, labels: false, sunLabel: false })
    expect(behaviour({ variant: 'phone' }).cadenceMs).toBeCloseTo(1000 / SPEC.phoneFps)
  })

  // §5.4: "The stage still updates light colours, at most once per second."
  it('draws slowly with reduced motion', () => {
    expect(behaviour({ reducedMotion: true }).cadenceMs).toBe(LIVE_SPEC.reducedMotionMs)
    expect(behaviour({ variant: 'phone', reducedMotion: true }).cadenceMs).toBe(LIVE_SPEC.reducedMotionMs)
  })

  // §7.6 frozen: "Last frame, grayscale 85%, brightness 55%, no animation"; §9.4: controls come back with the link.
  it('is greyed, still and out of reach while frozen', () => {
    expect(behaviour({ mode: 'frozen', reducedMotion: true })).toMatchObject({ interactive: false, greyed: true, cadenceMs: null })
  })
})
