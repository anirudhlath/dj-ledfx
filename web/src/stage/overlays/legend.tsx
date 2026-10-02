// §8.1 bottom left: the light-state legend, each sample drawn as §6.6 draws that state.
import type { CSSProperties } from 'react'
import { RENDER, SPEC } from '../design-numbers'
import { colourOf, cssColour, cssSize } from '../palette'

const { dotPx, liveSample, ownEffectSample, glowPx, glowAlpha } = RENDER.legend
const sample = (style: CSSProperties): CSSProperties => ({ width: dotPx, height: dotPx, borderRadius: '50%', ...style })
const [r, g, b] = colourOf(liveSample).map((channel) => Math.round(channel * 255))

const ITEMS: { name: string; style: CSSProperties; slash?: true }[] = [
  { name: 'Live colour', style: sample({ background: cssColour(liveSample), boxShadow: `0 0 ${glowPx}px rgb(${r} ${g} ${b} / ${glowAlpha})` }) },
  {
    name: 'Own effect',
    style: sample({
      background: cssColour(ownEffectSample),
      outline: `${SPEC.swatch.ownEffectPx}px dotted var(--color-text-2)`,
      outlineOffset: SPEC.swatch.ownEffectOffsetPx,
    }),
  },
  { name: 'Offline', style: sample({ border: `${SPEC.swatch.offlinePx}px dashed var(--color-signal)` }) },
  { name: 'Switched off elsewhere', style: sample({ border: `${SPEC.swatch.switchedOffPx}px solid var(--color-text-3)` }), slash: true },
]

export function Legend() {
  const { leftPx, bottomPx, gapPx, itemGapPx, font, colour } = RENDER.legend
  return (
    <ul
      aria-label="What the lights show"
      className="absolute flex items-center"
      style={{ left: leftPx, bottom: bottomPx, gap: gapPx, fontSize: cssSize(font), color: cssColour(colour) }}
    >
      {ITEMS.map(({ name, style, slash }) => (
        <li key={name} className="inline-flex items-center" style={{ gap: itemGapPx }}>
          <span aria-hidden="true" className="relative box-border shrink-0" style={style}>
            {slash && <span className="absolute inset-x-0 top-1/2 h-px -rotate-45 bg-text-3" />}
          </span>
          {name}
        </li>
      ))}
    </ul>
  )
}
