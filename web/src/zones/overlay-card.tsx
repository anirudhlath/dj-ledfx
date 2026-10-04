// §6.3 overlay: "a Home look playing over everything, e.g. Doorbell ripple: gold-tinted card, time left,
// progress bar" (Live-Doorbell). The time left and the bar move from an animation frame, never through
// React, and never count below zero (F3 decision 17, Review Focus 5). The gold is LIVE_RENDER.overlay's:
// tokens.css has no colour for it.
import { useLayoutEffect, useRef } from 'react'
import type { Overlay } from '@/api/contract'
import { Chip } from '@/design/chip'
import { LIVE_RENDER } from '@/design/live-numbers'
import { writeProgress } from '@/design/progress'
import { ProgressBar } from '@/design/progress-bar'
import { formatSecondsLeft } from '@/lib/format'
import { overlayLeftMs, overlayProgress, type InputChip } from './zone-view'

export interface OverlayCardProps {
  overlay: Overlay
  /** Its look's input chips (chipsFor); none while REST doesn't know the look. */
  inputs: readonly InputChip[]
}

export function OverlayCard({ overlay, inputs }: OverlayCardProps) {
  const time = useRef<HTMLSpanElement>(null)
  const bar = useRef<HTMLSpanElement>(null)
  useLayoutEffect(() => {
    const first = overlayLeftMs(overlay, Date.now())
    let frame = 0
    let shown = ''
    const tick = () => {
      const left = overlayLeftMs(overlay, Date.now())
      const text = formatSecondsLeft(left)
      if (time.current !== null && text !== shown) {
        time.current.textContent = text
        shown = text
      }
      if (bar.current !== null) writeProgress(bar.current, overlayProgress(overlay.progress, first, left))
      frame = left > 0 ? requestAnimationFrame(tick) : 0
    }
    tick()
    return () => cancelAnimationFrame(frame)
  }, [overlay])
  const gold = LIVE_RENDER.overlay
  return (
    <article
      aria-label={`${overlay.name} over everything`}
      className="flex flex-col gap-2.5 rounded-card border px-4 py-3.5"
      style={{ backgroundColor: gold.background, borderColor: gold.border }}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-data font-semibold" style={{ color: gold.ink }}>
          Over everything · <span ref={time} />
        </span>
        {inputs.map((input) => (
          <Chip key={input.kind} icon={input.icon}>
            {input.label}
          </Chip>
        ))}
      </div>
      <h3 className="font-serif text-[28px] leading-[1.05]">{overlay.name}</h3>
      <div className="flex gap-1.5">
        <Chip variant="quiet">{overlay.trigger}</Chip>
      </div>
      <ProgressBar ref={bar} value={overlay.progress} label={overlay.name} tone="overlay" />
    </article>
  )
}
