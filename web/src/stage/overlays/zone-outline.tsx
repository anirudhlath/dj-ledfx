// §8.1 "Hover a card → its zone outlines on the stage", drawn as §7.6 compose outlines its chosen zone:
// `text`, on the floor, as wide as the stage's behaviour says; and compose's other rooms, dimmed. Neither
// render sets a line join (Live-PutLookOn's, Phone-PutLookOn's), so the outline sets none.
import type { Id, Vec2 } from '@/api/contract'
import { SPEC } from '../design-numbers'
import { cssColour } from '../palette'

const points = (polygon: readonly Vec2[]) => polygon.map(([x, y]) => `${x},${y}`).join(' ')

export interface ZoneOutlineShape {
  zoneId: Id
  /** On the stage, in CSS px. */
  polygons: readonly (readonly Vec2[])[]
  /** The stroke's width, in CSS px: StageBehaviour's `outlinePx`. */
  widthPx: number
}

export function ZoneOutline({ outline }: { outline: ZoneOutlineShape }) {
  return (
    <g data-outline={outline.zoneId} fill="none" stroke={cssColour('--color-text')} strokeWidth={outline.widthPx}>
      {outline.polygons.map((polygon, index) => (
        <polygon key={index} points={points(polygon)} />
      ))}
    </g>
  )
}

/** §7.6 compose: "Rooms outside the chosen zone dimmed", to SPEC.compose.dimmed: `bg` over their floors at the rest. */
export function ZoneDims({ polygons }: { polygons: readonly (readonly Vec2[])[] }) {
  return (
    <g data-dims fill={cssColour('--color-bg')} fillOpacity={1 - SPEC.compose.dimmed}>
      {polygons.map((polygon, index) => (
        <polygon key={index} points={points(polygon)} />
      ))}
    </g>
  )
}
