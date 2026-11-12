// The look thumbs' motion (§5.4 "Look thumbnails animate continuously", "Beat-synced motion must follow the
// real beat clock, never a CSS timer"; F5 decisions 4 to 6). A thumb registers while it's on screen
// (use-thumb-motion.ts). An ambient, home or firmware motif runs its own CSS loop while registered. A tempo
// or audio motif stays paused (styles/app.css), and one animation-frame loop, running while any is
// registered, seeks every one of them to the beat: τ beats from where the run began, at Looks.html's
// keyframes of one beat at 121.8 BPM (`beatMs`). The loop samples the beat clock once a frame and writes
// the DOM, so React never redraws for a beat (§7.5 "No React state per frame").
import { clientNow, nearWay, type BeatSample } from '@/api/beat'
import { beatClock } from '@/api/live'
import { liveStore } from '@/api/live-store'
import { LIVE_SPEC } from '@/design/live-numbers'

export interface ThumbMotion {
  /** LookThumb's `<svg class="tb" data-paused>`. */
  svg: SVGSVGElement
  /** Its motif follows the beat (F5 decision 4). */
  beat: boolean
}

/** Where `beats` beats fall in Looks.html's keyframes, which last one beat at the mocks' tempo (decision 4). */
export const beatMs = (beats: number): number => (beats * 60000) / LIVE_SPEC.mockBpm

interface Seeked {
  /** Read once, as the thumb registers: a motif's animations live as long as its markup. */
  animations: readonly Animation[]
  /** The time last written to them, NaN before the first. */
  written: number
}

const beatThumbs = new Map<ThumbMotion, Seeked>()
const sample: BeatSample = { beatPhase: 0, barPhase: 0, beatInBar: 1, bar: null, bpm: 0, running: false }
let frame: number | null = null
/** τ, the beats the run has moved: from the place in the bar its first frame saw. */
let tau = 0
/** The place in the bar the last frame saw, written every frame; null before a run's first. */
let last: number | null = null
/** The last frame's beat moved: running, and not stale. */
let lastFresh = false

function draw(): void {
  frame = null
  if (beatThumbs.size === 0) return
  beatClock.sample(clientNow(), sample)
  const place = sample.barPhase * 4
  // A stopped or stale beat holds τ (decision 6). The first frame after one only takes the place again,
  // so a beat that comes back somewhere else in the bar doesn't jump the motifs there.
  const fresh = sample.running && liveStore.getState().beat?.stale !== true
  if (last === null) tau = place
  else if (fresh && lastFresh) tau += nearWay(place - last)
  last = place
  lastFresh = fresh
  // A clock stepped back early in a run can take τ below 0, where every keyframe is in its before phase and
  // the motif would draw blank: it holds at its start instead, until τ is back past 0.
  const ms = beatMs(Math.max(0, tau))
  for (const seeked of beatThumbs.values()) {
    if (seeked.written === ms) continue
    seeked.written = ms
    for (const animation of seeked.animations) animation.currentTime = ms
  }
  frame = requestAnimationFrame(draw)
}

/**
 * A thumb on screen: an ambient motif runs, and a beat motif follows the beat from the next frame. The
 * returned function stops it, once: an ambient motif pauses again, a beat motif stays where it is.
 */
export function registerThumb(thumb: ThumbMotion): () => void {
  const { svg } = thumb
  if (!thumb.beat) {
    svg.removeAttribute('data-paused')
    let on = true
    return () => {
      if (!on) return
      on = false
      svg.setAttribute('data-paused', '')
    }
  }
  // jsdom has no getAnimations.
  const animations = typeof svg.getAnimations === 'function' ? svg.getAnimations({ subtree: true }) : []
  beatThumbs.set(thumb, { animations, written: Number.NaN })
  frame ??= requestAnimationFrame(draw)
  return () => {
    if (!beatThumbs.delete(thumb) || beatThumbs.size > 0) return
    // The run ends: the next starts again from the place in the bar.
    if (frame !== null) cancelAnimationFrame(frame)
    frame = null
    last = null
    lastFresh = false
  }
}
