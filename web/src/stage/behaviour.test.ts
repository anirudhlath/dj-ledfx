import { describe, expect, it } from 'vitest'
import { LIVE_RENDER, LIVE_SPEC } from '@/design/live-numbers'
import { stageBehaviour, type StageOptions } from './behaviour'
import { SPEC } from './design-numbers'

const behaviour = (options: Partial<StageOptions>) =>
  stageBehaviour({ mode: 'live', variant: 'desktop', reducedMotion: false, labels: true, effects: true, ...options })

describe("the stage's behaviour in each mode (§7.6) and on the phone (§8.10)", () => {
  it('is all there on desktop Live, labels as the Labels switch says', () => {
    expect(behaviour({})).toEqual({
      interactive: true,
      roomClick: 'open',
      framesComposeZone: false,
      overlays: true,
      legend: true,
      labels: true,
      effects: true,
      sunLabel: true,
      greyed: false,
      previewTag: null,
      outlinePx: SPEC.compose.outlinePx,
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
      effects: true,
      sunLabel: false,
      greyed: false,
      previewTag: null,
      outlinePx: LIVE_RENDER.phoneOutlinePx,
      cadenceMs: 1000 / SPEC.phoneFps,
    })
    expect(behaviour({ mode: 'focus' })).toMatchObject({ overlays: false, legend: false, labels: false, cadenceMs: 1000 / SPEC.target.fps })
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
      effects: true,
      sunLabel: true,
      greyed: false,
      previewTag: 'card',
      outlinePx: SPEC.compose.outlinePx,
      cadenceMs: 1000 / SPEC.target.fps,
    })
    // Phone-PutLookOn: the zone framed, a tag on the stage, and no labels or legend, and an outline narrower than the spec's.
    expect(behaviour({ mode: 'compose', variant: 'phone' })).toMatchObject({
      roomClick: 'choose',
      framesComposeZone: true,
      legend: false,
      labels: false,
      previewTag: 'tag',
      outlinePx: LIVE_RENDER.phoneOutlinePx,
    })
  })

  it("has no labels or overlays on the phone, and draws at the phone's rate", () => {
    expect(behaviour({ variant: 'phone' })).toMatchObject({ interactive: true, overlays: false, labels: false, sunLabel: false })
    expect(behaviour({ variant: 'phone' }).cadenceMs).toBeCloseTo(1000 / SPEC.phoneFps)
  })

  // §7.4: the "Effects in space" switch, default on (view-memory.ts). The phone has no switch and draws them
  // (Phone-Live, Phone-Zone); the Reconnecting renders draw none, and §5.4's reduced motion stops particles.
  it('draws the effects in space as the switch says, always on the phone, and never while frozen or still', () => {
    expect(behaviour({ effects: false }).effects).toBe(false)
    expect(behaviour({ mode: 'compose', effects: false }).effects).toBe(false)
    expect(behaviour({ mode: 'focus', effects: false }).effects).toBe(false)
    expect(behaviour({ variant: 'phone', effects: false }).effects).toBe(true)
    expect(behaviour({ mode: 'focus', variant: 'phone', effects: false }).effects).toBe(true)
    expect(behaviour({ mode: 'frozen' }).effects).toBe(false)
    expect(behaviour({ mode: 'frozen', variant: 'phone' }).effects).toBe(false)
    expect(behaviour({ reducedMotion: true }).effects).toBe(false)
    expect(behaviour({ variant: 'phone', reducedMotion: true }).effects).toBe(false)
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
