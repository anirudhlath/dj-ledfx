// §8.1 top right: the sun readout (sun.ts's sunReadoutRuns()), while the sun is up (decision 7). As
// Main.png sets it, the elevation and compass point are mono in the text colour, between the
// readout's own words.
import type { SunInput } from '@/api/contract'
import { Icon } from '@/design/icon'
import { RENDER } from '../design-numbers'
import { cssColour, cssSize } from '../palette'
import { sunReadoutRuns } from '../sun'

export function SunReadout({ sun }: { sun: SunInput | null }) {
  const runs = sunReadoutRuns(sun)
  if (runs === null) return null
  const [before, position, after] = runs
  const { rightPx, topPx, gapPx, font, colour, iconPx, iconColour } = RENDER.readout
  return (
    <p className="absolute flex items-center" style={{ right: rightPx, top: topPx, gap: gapPx, fontSize: cssSize(font), color: cssColour(colour) }}>
      <span style={{ color: cssColour(iconColour) }}>
        <Icon name="sun" size={iconPx} />
      </span>
      <span>
        {before}
        <span className="num text-text">{position}</span>
        {after}
      </span>
    </p>
  )
}
