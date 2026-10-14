// §7.6's modes table in code: what the stage does in each mode, on each variant (§8.10's phone).
// StageView asks once and hands the answers down; nothing else checks the mode or the variant. The
// mode F7 brings (map) extends it.
import { LIVE_RENDER, LIVE_SPEC } from '@/design/live-numbers'
import { SPEC } from './design-numbers'

/**
 * §7.6's modes so far: `live`; `compose`, the composer's (§8.2); `focus`, framed on one zone (Zone
 * detail; the editor's preview and the phone's tweak later); and `frozen` while the link is down (§9.4
 * Reconnecting), on any of them.
 */
export type StageMode = 'live' | 'compose' | 'focus' | 'frozen'
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
   * Live's interactive layer: §8.1's hover tooltip, the overlays, the zones' tags and the rooms' links.
   * §7.6 frozen has none: "Controls come back when the link does" (§9.4).
   */
  interactive: boolean
  /**
   * A click on a room: Live's opens the composer on it (§8.1), a page of its own; the composer's chooses
   * its zone (§6.3 ZonePicker) in place. Null where a click does nothing.
   */
  roomClick: 'open' | 'choose' | null
  /**
   * The composer frames its zone as focus frames one (§7.2), keeping the other lights: on the phone, whose
   * stage is too small for the whole home (Phone-PutLookOn). Desktop's keeps Live's view (Live-PutLookOn).
   */
  framesComposeZone: boolean
  /** §8.1's overlays: the tools, the sun readout and the view controls, and so the view they keep. */
  overlays: boolean
  /** §8.1's legend: Live's, and the composer's (Live-PutLookOn draws it). */
  legend: boolean
  /**
   * The width, in CSS px, of the outline round the zone the stage draws: SPEC.compose.outlinePx's on
   * desktop, and the narrower one Phone-PutLookOn draws (its render isn't scaled).
   */
  outlinePx: number
  /** The rooms' labels (§7.6). */
  labels: boolean
  /** The sun's mono label (§7.4); Phone-Live.png draws the sun without it. */
  sunLabel: boolean
  /** The picture greyed as SPEC.frozen says (§7.6 frozen). */
  greyed: boolean
  /**
   * §7.6 compose's "PREVIEW ON SCREEN": a card beside the zone (Live-PutLookOn), a tag on the phone's
   * stage (Phone-PutLookOn); null outside the composer.
   */
  previewTag: 'card' | 'tag' | null
  /**
   * Milliseconds between draws: SPEC.target.fps's on desktop and SPEC.phoneFps's on a phone (§7.5),
   * LIVE_SPEC.reducedMotionMs with reduced motion (§5.4); null while frames don't redraw the stage (§7.6
   * frozen: "no animation").
   */
  cadenceMs: number | null
}

export function stageBehaviour({ mode, variant, reducedMotion, labels }: StageOptions): StageBehaviour {
  const live = mode === 'live'
  const compose = mode === 'compose'
  const phone = variant === 'phone'
  // §7.6 focus is the zone's picture alone: what frames it and hides the other lights is StageView's `focus`.
  const focus = mode === 'focus'
  return {
    interactive: live,
    roomClick: live ? 'open' : compose ? 'choose' : null,
    framesComposeZone: phone,
    overlays: !phone && !focus,
    legend: !phone && (live || compose),
    outlinePx: phone ? LIVE_RENDER.phoneOutlinePx : SPEC.compose.outlinePx,
    labels: !phone && !focus && labels,
    sunLabel: !phone && !focus,
    greyed: mode === 'frozen',
    previewTag: compose ? (phone ? 'tag' : 'card') : null,
    cadenceMs: mode === 'frozen' ? null : reducedMotion ? LIVE_SPEC.reducedMotionMs : 1000 / (phone ? SPEC.phoneFps : SPEC.target.fps),
  }
}
