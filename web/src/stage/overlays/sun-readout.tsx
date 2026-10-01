// §8.1 top right: the sun readout (sun.ts's sunReadout()), while the sun is up (decision 7).
import type { SunInput } from '@/api/contract'
import { Icon } from '@/design/icon'
import { RENDER } from '../design-numbers'
import { cssColour, cssSize } from '../palette'
import { sunReadout } from '../sun'

export function SunReadout({ sun }: { sun: SunInput | null }) {
  const text = sunReadout(sun)
  if (text === null) return null
  const { rightPx, topPx, gapPx, font, colour, iconPx, iconColour } = RENDER.readout
  return (
    <p className="num absolute flex items-center" style={{ right: rightPx, top: topPx, gap: gapPx, fontSize: cssSize(font), color: cssColour(colour) }}>
      <span style={{ color: cssColour(iconColour) }}>
        <Icon name="sun" size={iconPx} />
      </span>
      {text}
    </p>
  )
}
