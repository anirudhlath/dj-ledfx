// When the stage draws (§7.5): only once a frame has arrived since its last draw, and no more often
// than its rate, the stage behaviour's cadenceMs (behaviour.ts); none at all while that's null (§7.6
// frozen). It rides the browser's animation frames, so a hidden tab draws nothing (§7.5, "pause
// rendering when the tab is hidden"). It is the stage's one draw tick: the canvas draws on it, and
// whatever else shows the frames (the light tooltip) follows it through onStageDraw().
import { useEffect, useEffectEvent } from 'react'
import { frames } from '@/api/live'

/** Half a 60 Hz animation frame: the slack until the cadence has measured the screen's. */
const DEFAULT_SLACK_MS = 1000 / 60 / 2

/**
 * On each animation frame, whether the stage draws. Each draw is due a whole interval after the last
 * one was due, not after it was drawn, and the animation frame nearest that time draws it, so the
 * rate holds on a 120 or 144 Hz screen as on a 60 Hz one.
 */
export class Cadence {
  private readonly intervalMs: number
  private version = -1
  private dueAt = Number.NEGATIVE_INFINITY
  private frameAt: number | null = null
  /** Half the screen's animation-frame interval, as last measured. */
  private slackMs = DEFAULT_SLACK_MS

  constructor(intervalMs: number) {
    this.intervalMs = intervalMs
  }

  /** `now` is the animation frame's time; `version` the frame store's. */
  due(now: number, version: number): boolean {
    if (this.frameAt !== null && now > this.frameAt) this.slackMs = (now - this.frameAt) / 2
    this.frameAt = now
    if (version === this.version || now < this.dueAt - this.slackMs) return false
    this.version = version
    this.dueAt += this.intervalMs
    // Behind, after a wait for frames or on a slow screen: the next draw is due an interval from now.
    if (this.dueAt - this.slackMs <= now) this.dueAt = now + this.intervalMs
    return true
  }
}

const listeners = new Set<() => void>()

/** Calls `listener` right after each of the stage's draws; returns what stops it. */
export function onStageDraw(listener: () => void): () => void {
  listeners.add(listener)
  return () => void listeners.delete(listener)
}

/**
 * Calls `draw` whenever the cadence says a draw is due, in that same animation frame. (The canvas
 * draws with R3F's advance(): invalidate() would wait for the next one, and R3F's demand loop would
 * then draw every other.)
 */
export function useCadence(intervalMs: number | null, draw: (now: number) => void): void {
  const due = useEffectEvent((now: number) => {
    draw(now)
    for (const listener of listeners) listener()
  })
  useEffect(() => {
    if (intervalMs === null) return
    const cadence = new Cadence(intervalMs)
    let handle = requestAnimationFrame(function tick(now) {
      handle = requestAnimationFrame(tick)
      if (cadence.due(now, frames.version)) due(now)
    })
    return () => cancelAnimationFrame(handle)
  }, [intervalMs])
}
