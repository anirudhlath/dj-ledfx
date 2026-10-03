// The stage's SVG layer, over the canvas: the lights' marks (§7.3, §9.1), the room labels (§7.6) and
// the sun (§7.4). It depends on the pose, the lights' status, what runs and the sun, never on frames,
// so React draws it only when one of those changes (memo). Every size and colour is SPEC's or RENDER's.
import { memo, useId } from 'react'
import type { Vec2 } from '@/api/contract'
import { LIVE_SPEC } from '@/design/live-numbers'
import { projectPoint, type CameraPose } from '../camera'
import { RENDER, SPEC } from '../design-numbers'
import type { StageLabel } from '../labels'
import type { Mark } from '../marks'
import { cssColour, cssSize } from '../palette'
import type { SunScene } from '../sun'
import { ZoneOutline, type ZoneOutlineShape } from './zone-outline'

export interface StageSvgProps {
  pose: CameraPose
  marks: readonly Mark[]
  /** Null while the Labels switch is off, and on the phone (§8.10). */
  labels: readonly StageLabel[] | null
  /** The sun, with its label where the stage has labels (behaviour.ts). */
  sun: SunScene | null
  /** The zone a card is hovered over, or /live/zones/:zoneId names; null for none. */
  outline?: ZoneOutlineShape | null
}

export const StageSvg = memo(function StageSvg({ pose, marks, labels, sun, outline = null }: StageSvgProps) {
  return (
    <svg aria-hidden="true" className="pointer-events-none absolute inset-0" width={pose.width} height={pose.height}>
      {sun !== null && <SunMark pose={pose} sun={sun} />}
      {outline !== null && <ZoneOutline outline={outline} />}
      {marks.map((mark) => (
        <MarkShape key={mark.key} mark={mark} />
      ))}
      {labels?.map((label) => (
        <RoomLabel key={label.key} label={label} at={projectPoint(pose, label.at)} />
      ))}
    </svg>
  )
})

const line = (colour: string, alpha: number, width: number, dash?: readonly [number, number]) => ({
  stroke: cssColour(colour),
  strokeOpacity: alpha,
  strokeWidth: width,
  strokeDasharray: dash?.join(' '),
  fill: 'none',
})

function MarkShape({ mark }: { mark: Mark }) {
  switch (mark.kind) {
    case 'drop': {
      const { dashPx, gapPx, alpha } = SPEC.dropLine
      const tick = RENDER.floorTick
      return (
        <g>
          <line x1={mark.from[0]} y1={mark.from[1]} x2={mark.to[0]} y2={mark.to[1]} {...line('--color-text', alpha, RENDER.dropLine.widthPx, [dashPx, gapPx])} />
          <circle cx={mark.to[0]} cy={mark.to[1]} r={tick.radiusPx} fill={cssColour(tick.colour)} fillOpacity={tick.alpha} />
        </g>
      )
    }
    case 'switched-off': {
      const { ringPx, fill, colour, alpha, widthPx, slashHalfPx } = RENDER.switchedOff
      const [x, y] = mark.at
      return (
        <g>
          <circle cx={x} cy={y} r={ringPx} {...line(colour, alpha, widthPx)} fill={cssColour(fill)} />
          <path d={`M${x - slashHalfPx} ${y + slashHalfPx} L${x + slashHalfPx} ${y - slashHalfPx}`} {...line(colour, alpha, widthPx)} />
        </g>
      )
    }
    case 'offline': {
      // §9.1 and the legend: a hollow ring in the signal colour, dashed as the render's offline strip.
      const { dashPx, gapPx } = RENDER.offlineStrip
      return <circle cx={mark.at[0]} cy={mark.at[1]} r={RENDER.switchedOff.ringPx} {...line('--color-signal', 1, LIVE_SPEC.swatch.offlinePx, [dashPx, gapPx])} />
    }
    case 'offline-strip': {
      const { colour, alpha, widthPx, dashPx, gapPx } = RENDER.offlineStrip
      return <polyline points={mark.points.map((point) => point.join(',')).join(' ')} {...line(colour, alpha, widthPx, [dashPx, gapPx])} strokeLinecap="round" />
    }
    case 'own-effect': {
      const { ringPx, colour, alpha, widthPx, dashPx, gapPx } = RENDER.ownEffect
      return <circle cx={mark.at[0]} cy={mark.at[1]} r={ringPx} {...line(colour, alpha, widthPx, [dashPx, gapPx])} />
    }
    case 'streamed-copy': {
      const { dxPx, dyPx, risePx, halfPx, rowGapPx, colour, alpha, widthPx } = RENDER.streamedCopy
      const [x, y] = [mark.at[0] + dxPx, mark.at[1] + dyPx]
      const wave = (top: number) => `M${x} ${top} q${halfPx / 2} ${-risePx} ${halfPx} 0 t${halfPx} 0`
      return <path d={`${wave(y)} ${wave(y + rowGapPx)}`} {...line(colour, alpha, widthPx)} strokeLinecap="round" />
    }
  }
}

/** Room caps, and the look running there beneath in serif italic (§7.6, §5.2). */
function RoomLabel({ label, at }: { label: StageLabel; at: Vec2 }) {
  return (
    <g>
      <text x={at[0]} y={at[1]} textAnchor="middle" className="label-caps fill-text-3" style={{ fontSize: SPEC.label.capsPx }}>
        {label.name}
      </text>
      {label.look !== null && (
        <text x={at[0]} y={at[1] + RENDER.label.lineGapPx} textAnchor="middle" className="fill-text font-serif italic" style={{ fontSize: SPEC.label.lookPx }}>
          {label.look}
        </text>
      )}
    </g>
  )
}

/** §7.4: the dashed arc of the sun's recent path, its glow, its disc and its label. */
function SunMark({ pose, sun }: { pose: CameraPose; sun: SunScene }) {
  const glowId = useId()
  const { path, glow, disc, label } = RENDER.sun
  const [x, y] = projectPoint(pose, sun.at)
  const points = sun.path.map((point) => projectPoint(pose, point).join(',')).join(' ')
  return (
    <g>
      <defs>
        <radialGradient id={glowId}>
          {glow.stops.map((stop) => (
            <stop key={stop.at} offset={stop.at} stopColor={cssColour(glow.colour)} stopOpacity={stop.alpha} />
          ))}
        </radialGradient>
      </defs>
      {sun.path.length > 1 && <polyline points={points} {...line(path.colour, path.alpha, path.widthPx, [path.dashPx, path.gapPx])} />}
      <circle cx={x} cy={y} r={glow.radiusPx} fill={`url(#${glowId})`} />
      <circle cx={x} cy={y} r={disc.radiusPx} fill={cssColour(disc.colour)} />
      {sun.label !== null && (
        <text
          x={x}
          y={y + label.dyPx}
          textAnchor="middle"
          className="font-mono"
          style={{ fontSize: cssSize(label.font), fontWeight: label.weight, fill: cssColour(label.colour) }}
        >
          {sun.label}
        </text>
      )}
    </g>
  )
}
