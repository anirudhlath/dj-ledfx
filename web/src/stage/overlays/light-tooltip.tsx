// §8.1 "Hover a light → tooltip": its name, its colour now (hex and intensity), the look and zone,
// the model and latency, with a leader to the light as Main.png draws it. The colour line and the
// swatch follow the frames without React: they're painted on mount, then after each of the stage's
// draws (cadence.ts), so they change as the canvas does, and only when the light has a new frame
// that says something new. A frozen stage has no tooltip (§7.6).
import { useEffect, useRef } from 'react'
import type { Light, Vec2 } from '@/api/contract'
import { frames } from '@/api/live'
import { cx } from '@/design/cx'
import { TOOLTIP_SURFACE } from '@/design/overlays'
import type { Size } from '../camera'
import { onStageDraw } from '../cadence'
import { RENDER } from '../design-numbers'
import { swatchFill, swatchGlow, type RGB } from '../light-maths'
import { cssColour } from '../palette'
import type { LightState } from '../show'
import { colourLine, currentColour, type TooltipText } from '../tooltip'

const BLACK: RGB = [0, 0, 0]

export interface LightTooltipProps {
  light: Light
  state: LightState
  text: TooltipText
  /** The light, in CSS px on the stage. */
  at: Vec2
  stage: Size
}

export function LightTooltip({ light, state, text, at, stage }: LightTooltipProps) {
  const swatch = useRef<HTMLSpanElement>(null)
  const colour = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let seq: number | null = null
    let painted: string | null | undefined
    const paint = () => {
      const frame = frames.get(light.id)
      if (frame !== undefined && frame.seq === seq) return
      seq = frame?.seq ?? null
      const rgb = currentColour(frame, state)
      const line = colourLine(state, rgb)
      if (line === painted || swatch.current === null || colour.current === null) return
      painted = line
      swatch.current.style.background = swatchFill(rgb ?? BLACK)
      swatch.current.style.boxShadow = swatchGlow(rgb ?? BLACK, RENDER.tooltip.swatchGlowPx)
      colour.current.textContent = line
      colour.current.hidden = line === null
    }
    paint()
    return onStageDraw(paint)
  }, [light.id, state])

  const { dxPx, dyPx, widthPx, nameGapPx, swatchPx, leader } = RENDER.tooltip
  // Past the stage's right edge, the box and its leader turn to the light's left.
  const flip = at[0] + dxPx + widthPx > stage.width
  const left = flip ? at[0] - dxPx - widthPx : at[0] + dxPx
  return (
    <>
      <div
        aria-hidden="true"
        className="pointer-events-none absolute origin-top-left"
        style={{
          left: at[0],
          top: at[1],
          width: leader.lengthPx,
          height: leader.widthPx,
          background: cssColour(leader.colour),
          transform: `rotate(${flip ? 180 - leader.angleDeg : leader.angleDeg}deg)`,
        }}
      />
      <div role="tooltip" className={cx(TOOLTIP_SURFACE, 'pointer-events-none absolute')} style={{ left, top: Math.max(0, at[1] + dyPx), width: widthPx }}>
        <div className="flex items-center" style={{ gap: nameGapPx }}>
          <span ref={swatch} className="shrink-0 rounded-full" style={{ width: swatchPx, height: swatchPx }} />
          <span className="text-size-control font-semibold">{text.name}</span>
        </div>
        <div ref={colour} className="num text-text-2" />
        {text.running !== null && <div className="text-text-2">{text.running}</div>}
        <div className="text-text-2">{text.device}</div>
      </div>
    </>
  )
}
