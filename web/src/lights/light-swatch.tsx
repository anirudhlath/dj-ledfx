// §6.6 LightSwatch: "The one way a light's live colour appears outside the stage." The light's state
// gives its shape (a circle, or a pill for a multizone or matrix light), its outline or its hollow, and
// its accessible name (F3 decision 31); its colour follows the frame store through the swatch writer,
// never through React (§7.5). Every number is LIVE_SPEC.swatch's, or the renders' (LIVE_RENDER).
import { useLayoutEffect, useRef, type CSSProperties } from 'react'
import type { Light, LightStatus } from '@/api/contract'
import { LIVE_RENDER, LIVE_SPEC } from '@/design/live-numbers'
import { useReducedMotion } from '@/lib/use-media-query'
import type { LightState } from '@/stage/show'
import { registerSwatch } from './swatch-writer'

/** "card" in a ZoneCard, "phone" on the phone, "table" in a list of lights, "row" in a ZoneRow. */
export type SwatchSize = 'card' | 'phone' | 'table' | 'row'

const { swatch } = LIVE_SPEC

const SIZE_PX: Record<SwatchSize, number> = {
  card: swatch.px,
  phone: swatch.phonePx,
  table: swatch.tablePx,
  // §6.3 ZoneRow's "small swatches": the spec gives no size, so they're State-Problems' (F3 decision 34).
  row: LIVE_RENDER.rowSwatchPx,
}

/** What the name says after the light's own (F3 decision 31; §6.6: "Candle 2, switched off elsewhere"). */
const WORDS: Partial<Record<LightStatus, string>> = {
  'own-effect': 'running its own effect',
  'streamed-copy': 'a streamed copy',
  offline: 'offline',
  'switched-off': 'switched off elsewhere',
  reconnecting: 'reconnecting',
}

/** §6.6's outlines and hollows, by state. */
const LOOK: Partial<Record<LightStatus, CSSProperties>> = {
  'own-effect': { outlineWidth: swatch.ownEffectPx, outlineStyle: 'dotted', outlineColor: 'var(--color-text-2)', outlineOffset: swatch.ownEffectOffsetPx },
  'streamed-copy': { outlineWidth: swatch.streamedPx, outlineStyle: 'dashed', outlineColor: 'var(--color-text-3)', outlineOffset: swatch.streamedOffsetPx },
  offline: { borderWidth: swatch.offlinePx, borderStyle: 'dashed', borderColor: 'var(--color-signal)' },
  'switched-off': { borderWidth: swatch.switchedOffPx, borderStyle: 'solid', borderColor: 'var(--color-text-3)' },
}

const isHollow = (status: LightStatus) => status === 'offline' || status === 'switched-off'

export interface LightSwatchProps {
  light: Light
  state: LightState
  size?: SwatchSize
}

export function LightSwatch({ light, state, size = 'card' }: LightSwatchProps) {
  const ref = useRef<HTMLSpanElement>(null)
  const calm = useReducedMotion()
  const hollow = isHollow(state.status)
  // A hollow light is a circle whatever it is (Main.png's offline Rope).
  const pill = !hollow && (light.capabilities.includes('multizone') || light.capabilities.includes('matrix'))
  useLayoutEffect(() => {
    if (hollow || ref.current === null) return
    return registerSwatch({ element: ref.current, lightId: light.id, state, pill, calm })
  }, [hollow, light.id, state, pill, calm])

  const px = SIZE_PX[size]
  const words = WORDS[state.status]
  return (
    <span
      ref={ref}
      role="img"
      aria-label={words === undefined ? light.name : `${light.name}, ${words}`}
      title={words === undefined ? light.name : `${light.name} · ${words}`}
      className="relative box-border inline-block shrink-0"
      style={{ width: pill ? Math.floor(px * swatch.pillRatio) : px, height: px, borderRadius: px / 2, ...LOOK[state.status] }}
    >
      {state.status === 'switched-off' && (
        <span aria-hidden="true" className="absolute -top-px -bottom-px left-1/2 rotate-45 bg-text-3" style={{ width: swatch.switchedOffPx }} />
      )}
    </span>
  )
}
