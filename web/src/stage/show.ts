// What the stage draws for a light (§7.3, §9.1), from its REST record and the latest `lights`
// push. A light being streamed shows its frames; one that is only on shows its own colour; offline
// and switched-off lights show only their marks (the overlay's rings), never a glow.
import type { Light, LightUpdate } from '@/api/contract'
import { parseHex, type RGB } from './light-maths'

export type LightShow = 'frames' | 'resting' | 'dark' | 'offline' | 'switched-off'

/** The fields the stage reads, the push's where there is one. */
export interface LightState {
  status: Light['status']
  /** When it took that status. */
  since: string
  power: boolean | null
  colour: RGB | null
  ownEffect: string | null
}

/** The engine streams these lights' frames (an own effect's too, while the live stream is watched). */
const STREAMED: ReadonlySet<Light['status']> = new Set(['streaming', 'own-effect', 'streamed-copy'])

export function lightState(light: Light, update: LightUpdate | undefined): LightState {
  const from = update ?? light
  return {
    status: from.status,
    since: from.statusSince,
    power: from.power ?? null,
    colour: parseHex(from.colour),
    ownEffect: from.ownEffect ?? null,
  }
}

export function lightShow(state: LightState): LightShow {
  if (state.status === 'offline') return 'offline'
  if (state.status === 'switched-off') return 'switched-off'
  if (STREAMED.has(state.status)) return 'frames'
  return state.power === true && state.colour !== null ? 'resting' : 'dark'
}

/** The colour to draw without a frame: the light's own while it's on; null draws it dark. */
export function restingColour(state: LightState): RGB | null {
  return state.power === true ? state.colour : null
}
