// §8.1 "Hover a card → its zone outlines on the stage", drawn as §7.6 compose outlines its chosen zone:
// SPEC.compose.outlinePx of `text`, on the floor.
import type { Id, Vec2 } from '@/api/contract'
import { SPEC } from '../design-numbers'
import { cssColour } from '../palette'

export interface ZoneOutlineShape {
  zoneId: Id
  /** On the stage, in CSS px. */
  polygons: readonly (readonly Vec2[])[]
}

export function ZoneOutline({ outline }: { outline: ZoneOutlineShape }) {
  return (
    <g data-outline={outline.zoneId} fill="none" stroke={cssColour('--color-text')} strokeWidth={SPEC.compose.outlinePx} strokeLinejoin="round">
      {outline.polygons.map((polygon, index) => (
        <polygon key={index} points={polygon.map(([x, y]) => `${x},${y}`).join(' ')} />
      ))}
    </g>
  )
}
