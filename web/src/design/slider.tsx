import { useId, type CSSProperties } from 'react'
import { cx } from './cx'

export interface SliderProps {
  label: string
  value: number
  onValueChange: (value: number) => void
  min?: number
  max?: number
  step?: number
  /** The readout and the value read to assistive tech, e.g. (v) => `${v}%`. */
  format?: (value: number) => string
  className?: string
}

/**
 * §6.1 Slider: a real range input with a mono readout on the right. The root is `relative` for the label, which is `sr-only`, and so
 * absolutely positioned: with no positioned ancestor inside a scroller it escapes the scroller's clip, and a Running panel that scrolls
 * stretches <main>'s own scroll area by the label's place (measured: 27 to 39 px on a short screen).
 */
export function Slider({ label, value, onValueChange, min = 0, max = 100, step = 1, format = String, className }: SliderProps) {
  const id = useId()
  const text = format(value)
  const fill = { '--v': `${((value - min) / (max - min)) * 100}%` } as CSSProperties
  return (
    <div className={cx('relative flex items-center gap-2.5', className)}>
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        aria-valuetext={text}
        onChange={(event) => onValueChange(event.currentTarget.valueAsNumber)}
        className="slider min-w-0 flex-1"
        style={fill}
      />
      <span aria-hidden="true" className="num min-w-9 text-right text-meta text-text-2">
        {text}
      </span>
    </div>
  )
}
