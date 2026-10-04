// The pips and "bar N" (§5.4, §6.2; F3 decisions 3 and 4). One animation-frame loop serves every pip
// row on the page. Each frame it samples the beat clock once and writes the DOM: each pip's --pip,
// 0 to 1, along LIVE_RENDER.pip's curve, and each row's "Beat N of 4" and "bar N", only when they
// change. React never redraws for a beat (§7.5 "No React state per frame").
import { useLayoutEffect, type CSSProperties, type RefObject } from 'react'
import { clientNow, type BeatSample } from '@/api/beat'
import { beatClock } from '@/api/live'
import { LIVE_RENDER } from '@/design/live-numbers'
import { useReducedMotion } from '@/lib/use-media-query'

export interface PipRow {
  /** The four pips, the downbeat first. */
  pips: readonly HTMLElement[]
  /** What carries the row's name, "Beat N of 4". */
  label: HTMLElement
  /** Where the bar goes, if the row shows it: read each frame, since it can come and go. */
  bar: () => HTMLElement | null
  /** The bar's words: "bar 42" unless the row says otherwise. */
  barText?: (bar: number, beat: number) => string
  /** Reduced motion, or a stale beat: the pips stay at rest (F3 decision 4). The name and the bar still move. */
  still: boolean
}

interface Written {
  levels: number[]
  beat: number
}

const { lit, rest, glow, glowPx, glowAlpha, riseBeats, holdBeats, endBeats } = LIVE_RENDER.pip

/** A pip at its --pip, 0 to 1: the fill mixed from rest to lit, and the glow from nothing to the render's. */
export const PIP_STYLE = {
  backgroundColor: `color-mix(in srgb, var(${lit}) calc(var(--pip, 0) * 100%), var(${rest}))`,
  boxShadow: `0 0 ${glowPx}px color-mix(in srgb, var(${glow}) calc(var(--pip, 0) * ${glowAlpha * 100}%), transparent)`,
} as const satisfies CSSProperties

/**
 * A pip's level `beats` after its own beat began: up over the curve's rise, held, then down to rest by its
 * end, to two decimals so a pip isn't written again for a change nobody sees.
 */
export function pipLevel(beats: number): number {
  const level =
    beats < riseBeats ? beats / riseBeats : beats <= holdBeats ? 1 : beats < endBeats ? 1 - (beats - holdBeats) / (endBeats - holdBeats) : 0
  return Math.round(level * 100) / 100
}

const rows = new Map<PipRow, Written>()
const sample: BeatSample = { beatPhase: 0, barPhase: 0, beatInBar: 1, bar: null, bpm: 0, running: false }
let frame: number | null = null

const BAR_TEXT = (bar: number) => `bar ${bar}`

function write(row: PipRow, written: Written): void {
  const withinBar = sample.barPhase * 4
  row.pips.forEach((pip, index) => {
    const level = row.still || !sample.running ? 0 : pipLevel((((withinBar - index) % 4) + 4) % 4)
    if (written.levels[index] === level) return
    written.levels[index] = level
    pip.style.setProperty('--pip', String(level))
  })
  if (written.beat !== sample.beatInBar) {
    written.beat = sample.beatInBar
    row.label.setAttribute('aria-label', `Beat ${sample.beatInBar} of 4`)
  }
  const bar = row.bar()
  const text = sample.bar === null ? '' : (row.barText ?? BAR_TEXT)(sample.bar, sample.beatInBar)
  // The bar is compared with the page, not with what was written: it can mount after the row.
  if (bar !== null && bar.textContent !== text) bar.textContent = text
}

function draw(): void {
  frame = null
  if (rows.size === 0) return
  beatClock.sample(clientNow(), sample)
  for (const [row, written] of rows) write(row, written)
  frame = requestAnimationFrame(draw)
}

/** Writes a row now and on every animation frame after, until the returned function stops it. */
export function registerPips(row: PipRow): () => void {
  const written: Written = { levels: row.pips.map(() => -1), beat: 0 }
  rows.set(row, written)
  beatClock.sample(clientNow(), sample)
  write(row, written)
  frame ??= requestAnimationFrame(draw)
  return () => {
    rows.delete(row)
    if (rows.size === 0 && frame !== null) {
      cancelAnimationFrame(frame)
      frame = null
    }
  }
}

/**
 * A rendered pip row (its children are the pips) and its bar, written while mounted. `row` null: the row
 * is drawn as given (a fixed beat), and nothing is written.
 */
export function usePips(
  row: RefObject<HTMLElement | null> | null,
  bar: RefObject<HTMLElement | null>,
  stale: boolean,
  barText?: PipRow['barText'],
): void {
  const still = useReducedMotion() || stale
  useLayoutEffect(() => {
    const element = row?.current ?? null
    if (element === null) return
    return registerPips({ pips: [...element.children] as HTMLElement[], label: element, bar: () => bar.current, barText, still })
  }, [row, bar, still, barText])
}
