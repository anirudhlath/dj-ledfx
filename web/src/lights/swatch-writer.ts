// LightSwatch's colour (§6.6), without React (§7.5 "No React state per frame"). One loop serves every
// mounted swatch: it sleeps until the frame store has something new (FrameStore.onNextFrame), then, in one
// animation frame, repaints each swatch whose light has a new frame. Under reduced motion a swatch is
// repainted at most once per LIVE_SPEC.reducedMotionMs, as §5.4 has the stage do. The colour comes from the
// stage's own pure modules (stage/tooltip.ts, stage/show.ts), which carry no SPEC, so the first load
// doesn't take the stage's numbers.
import type { Id } from '@/api/contract'
import type { LightFrame } from '@/api/frames'
import { frames } from '@/api/live'
import { LIVE_SPEC } from '@/design/live-numbers'
import { intensityOf, isDark, swatchFill, swatchGlow, type RGB } from '@/lib/light-colour'
import { isStreamed, type LightState } from '@/stage/show'
import { currentColour } from '@/stage/tooltip'

export interface Swatch {
  element: HTMLElement
  lightId: Id
  state: LightState
  /** §6.6 "Multizone or matrix": a gradient of the light's LEDs, left to right. */
  pill: boolean
  /** Reduced motion: repainted at most once per LIVE_SPEC.reducedMotionMs. */
  calm: boolean
  /** Where the light's words go: "glowing" while it's lit, "waiting" while it's dark (Phone-Zone; F3 decision 24). */
  words?: HTMLElement | null
}

interface Painted {
  /** The frame painted last: its seq; null for the resting colour; undefined before the first paint. */
  seq: number | null | undefined
  /** When, on performance.now(). */
  at: number
}

/** The most stops a pill samples: State-Firmware's Rope pill has ten, the most any render draws. */
const PILL_STOPS = 10
const BLACK: RGB = [0, 0, 0]
/** One LED's colour, reused for each stop (RGB is read-only, so this one is typed as the tuple it fills). */
const led: [number, number, number] = [0, 0, 0]

const swatches = new Map<Swatch, Painted>()
let frame: number | null = null
let sleeping: (() => void) | null = null
let timer: ReturnType<typeof setTimeout> | null = null

/** A pill's fill (§6.6): up to PILL_STOPS of its LEDs, evenly spaced from its first to its last, each a swatch's fill. */
export function pillFill({ rgb, count }: LightFrame): string {
  const stops = Math.min(count, PILL_STOPS)
  const parts: string[] = []
  for (let i = 0; i < stops; i++) {
    const at = Math.round((i * (count - 1)) / (stops - 1)) * 3
    led[0] = rgb[at]
    led[1] = rgb[at + 1]
    led[2] = rgb[at + 2]
    parts.push(`${swatchFill(led)} ${Math.floor((i * 100) / (stops - 1))}%`)
  }
  return `linear-gradient(90deg, ${parts.join(', ')})`
}

function write(swatch: Swatch, lightFrame: LightFrame | undefined): void {
  const rgb = currentColour(lightFrame, swatch.state) ?? BLACK
  const { style } = swatch.element
  style.background = swatch.pill && lightFrame !== undefined && lightFrame.count > 1 ? pillFill(lightFrame) : swatchFill(rgb)
  style.boxShadow = swatchGlow(rgb, LIVE_SPEC.swatch.glowPx)
  if (swatch.words != null) {
    const words = isDark(intensityOf(rgb)) ? 'waiting' : 'glowing'
    if (swatch.words.textContent !== words) swatch.words.textContent = words
  }
}

/** Paints a swatch whose light has something new. Returns how long a calm one must wait first, else Infinity. */
function paint(swatch: Swatch, painted: Painted, now: number): number {
  const lightFrame = isStreamed(swatch.state) ? frames.get(swatch.lightId) : undefined
  const seq = lightFrame?.seq ?? null
  if (seq === painted.seq) return Infinity
  const wait = swatch.calm && painted.seq !== undefined ? painted.at + LIVE_SPEC.reducedMotionMs - now : 0
  if (wait > 0) return wait
  painted.seq = seq
  painted.at = now
  write(swatch, lightFrame)
  return Infinity
}

function draw(): void {
  frame = null
  const now = performance.now()
  let soonest = Infinity
  for (const [swatch, painted] of swatches) soonest = Math.min(soonest, paint(swatch, painted, now))
  if (swatches.size === 0) return
  sleeping ??= frames.onNextFrame(woken)
  if (soonest !== Infinity) timer ??= setTimeout(due, soonest)
}

/** The frame store has something new. */
function woken(): void {
  sleeping = null
  frame ??= requestAnimationFrame(draw)
}

/** A calm swatch may be repainted now. */
function due(): void {
  timer = null
  frame ??= requestAnimationFrame(draw)
}

/** Paints a swatch now and whenever its light's frame changes, until the returned function stops it. */
export function registerSwatch(swatch: Swatch): () => void {
  const painted: Painted = { seq: undefined, at: 0 }
  swatches.set(swatch, painted)
  paint(swatch, painted, performance.now())
  sleeping ??= frames.onNextFrame(woken)
  return () => {
    swatches.delete(swatch)
    if (swatches.size > 0) return
    sleeping?.()
    sleeping = null
    if (frame !== null) cancelAnimationFrame(frame)
    frame = null
    if (timer !== null) clearTimeout(timer)
    timer = null
  }
}
