// §8.1 top right: the sun readout, while the sun is up (decision 7): where it stands (sun.ts's
// sunPosition()) and when it sets. As Main.png sets it, the position is mono in the text colour,
// between the readout's own words; a sunset that doesn't parse is left out. Under Live's preview-only
// label, as the stage's tools are (`--stage-top-shift`, stage-tools.tsx).
import type { SunInput } from '@/api/contract'
import { Icon } from '@/design/icon'
import { RENDER } from '../design-numbers'
import { cssColour, cssSize } from '../palette'
import { sunPosition, sunsetTime } from '../sun'

export function SunReadout({ sun }: { sun: SunInput | null }) {
  const position = sunPosition(sun)
  if (sun === null || position === null) return null
  const sets = sunsetTime(sun)
  const { rightPx, topPx, gapPx, font, colour, iconPx, iconColour } = RENDER.readout
  return (
    <p
      className="absolute flex items-center"
      style={{ right: rightPx, top: `calc(var(--stage-top-shift, 0px) + ${topPx}px)`, gap: gapPx, fontSize: cssSize(font), color: cssColour(colour) }}
    >
      <span style={{ color: cssColour(iconColour) }}>
        <Icon name="sun" size={iconPx} />
      </span>
      <span>
        Sun <span className="num text-text">{position}</span>
        {sets !== null && ` · sets ${sets}`}
      </span>
    </p>
  )
}
