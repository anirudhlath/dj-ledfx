// §7.6's modes table in code: what the stage does in each mode, on each variant (§8.10's phone).
// StageView asks once and hands the answers down; nothing else checks the mode or the variant. The
// modes F4 and F7 bring (compose, map) extend it.
import { LIVE_SPEC } from '@/design/live-numbers'
import { SPEC } from './design-numbers'

/**
 * §7.6's modes so far: `live`; `focus`, framed on one zone (Zone detail; the editor's preview and the
 * phone's tweak later); and `frozen` while the link is down (§9.4 Reconnecting), on either.
 */
export type StageMode = 'live' | 'focus' | 'frozen'
/** The phone's stage is §8.10's: no labels, no overlays. */
export type StageVariant = 'desktop' | 'phone'

export interface StageOptions {
  mode: StageMode
  variant: StageVariant
  /** The system asks for less motion (§5.4). */
  reducedMotion: boolean
  /** The Labels switch (§8.1). */
  labels: boolean
}

export interface StageBehaviour {
  /**
   * The interactive layer: the pointer on the picture (§8.1's hover tooltip and room click), the
   * overlays and the rooms' links. §7.6 frozen has none: "Controls come back when the link does" (§9.4).
   */
  interactive: boolean
  /** §8.1's overlays: the tools, the sun readout, the legend and the view controls. */
  overlays: boolean
  /** The rooms' labels (§7.6). */
  labels: boolean
  /** The sun's mono label (§7.4); Phone-Live.png draws the sun without it. */
  sunLabel: boolean
  /** The picture greyed as SPEC.frozen says (§7.6 frozen). */
  greyed: boolean
  /**
   * Milliseconds between draws: SPEC.target.fps's on desktop and SPEC.phoneFps's on a phone (§7.5),
   * LIVE_SPEC.reducedMotionMs with reduced motion (§5.4); null while frames don't redraw the stage (§7.6
   * frozen: "no animation").
   */
  cadenceMs: number | null
}

export function stageBehaviour({ mode, variant, reducedMotion, labels }: StageOptions): StageBehaviour {
  const live = mode === 'live'
  const phone = variant === 'phone'
  // §7.6 focus is the zone's picture alone: what frames it and hides the other lights is StageView's `focus`.
  const focus = mode === 'focus'
  return {
    interactive: live,
    overlays: !phone && !focus,
    labels: !phone && !focus && labels,
    sunLabel: !phone && !focus,
    greyed: mode === 'frozen',
    cadenceMs: mode === 'frozen' ? null : reducedMotion ? LIVE_SPEC.reducedMotionMs : 1000 / (phone ? SPEC.phoneFps : SPEC.target.fps),
  }
}
