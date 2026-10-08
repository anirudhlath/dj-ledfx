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
      roomClick: 'open',
      framesComposeZone: false,
      overlays: true,
      legend: true,
      labels: true,
      sunLabel: true,
      greyed: false,
      previewTag: null,
      cadenceMs: 1000 / SPEC.target.fps,
    })
    expect(behaviour({ labels: false })).toMatchObject({ labels: false, sunLabel: true })
  })

  // §7.6 focus: "Framed on one zone, other zones' lights hidden, soft vignette": the picture alone.
  it('draws the picture alone in focus, at the rate of its variant', () => {
    expect(behaviour({ mode: 'focus', variant: 'phone' })).toEqual({
      interactive: false,
      roomClick: null,
      framesComposeZone: true,
      overlays: false,
      legend: false,
      labels: false,
      sunLabel: false,
      greyed: false,
      previewTag: null,
      cadenceMs: 1000 / SPEC.phoneFps,
    })
    expect(behaviour({ mode: 'focus' })).toMatchObject({ overlays: false, labels: false, cadenceMs: 1000 / SPEC.target.fps })
  })

  // §7.6 compose; Live-PutLookOn keeps the labels, the sun and the legend, and draws a PREVIEW ON SCREEN card.
  it('chooses a zone by its room and says the preview is on screen only, in compose', () => {
    expect(behaviour({ mode: 'compose' })).toEqual({
      interactive: false,
      roomClick: 'choose',
      framesComposeZone: false,
      overlays: true,
      legend: true,
      labels: true,
      sunLabel: true,
      greyed: false,
      previewTag: 'card',
      cadenceMs: 1000 / SPEC.target.fps,
    })
    // Phone-PutLookOn: the zone framed, a tag on the stage, and no labels or legend.
    expect(behaviour({ mode: 'compose', variant: 'phone' })).toMatchObject({
      roomClick: 'choose',
      framesComposeZone: true,
      legend: false,
      labels: false,
      previewTag: 'tag',
    })
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
    expect(behaviour({ mode: 'frozen', reducedMotion: true })).toMatchObject({
      interactive: false,
      roomClick: null,
      legend: false,
      greyed: true,
      previewTag: null,
      cadenceMs: null,
    })
  })
})
