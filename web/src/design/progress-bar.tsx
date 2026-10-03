// A progress bar: State-Transition's dissolve and Live-Doorbell's overlay. An animation frame can move it
// without React (writeProgress, progress.ts), as the overlay card's does (F3 decision 17).
import type { Ref } from 'react'
import { cx } from './cx'
import { LIVE_RENDER } from './live-numbers'
import { percentOf } from './progress'

export interface ProgressBarProps {
  /** 0–1, clamped. */
  value: number
  label: string
  /** "overlay": an overlay card's gold, LIVE_RENDER.overlay (tokens.css has no colour for it). */
  tone?: 'default' | 'overlay'
  className?: string
  ref?: Ref<HTMLSpanElement>
}

export function ProgressBar({ value, label, tone = 'default', className, ref }: ProgressBarProps) {
  const percent = percentOf(value)
  const overlay = tone === 'overlay'
  return (
    <span
      ref={ref}
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={percent}
      className={cx('block h-1 overflow-hidden rounded-[2px]', !overlay && 'bg-control-hover', className)}
      style={overlay ? { backgroundColor: LIVE_RENDER.overlay.track } : undefined}
    >
      <span
        className={cx('block h-full', !overlay && 'bg-text')}
        style={{ width: `${percent}%`, ...(overlay ? { backgroundColor: LIVE_RENDER.overlay.fill } : {}) }}
      />
    </span>
  )
}
