// What the stage draws for a light (§7.3, §9.1), from its REST record and the latest `lights`
// push. A light being streamed shows its frames; one that is only on shows its own colour; offline
// and switched-off lights show only their marks (the overlay's rings), never a glow.
import { STREAMED, type Id, type Light, type LightUpdate } from '@/api/contract'
import { parseHex, type RGB } from './light-maths'

/** The fields the stage reads, the push's where there is one. */
export interface LightState {
  status: Light['status']
  /** When it took that status. */
  since: string
  power: boolean | null
  colour: RGB | null
}

export function lightState(light: Light, update: LightUpdate | undefined): LightState {
  const from = update ?? light
  return { status: from.status, since: from.statusSince, power: from.power ?? null, colour: parseHex(from.colour) }
}

/** Each light's state, from its REST record and the latest push's update for it, if any. */
export function lightStates(lights: readonly Light[], updates?: Readonly<Record<Id, LightUpdate>> | null): Map<Id, LightState> {
  return new Map(lights.map((light) => [light.id, lightState(light, updates?.[light.id])]))
}

/** Whether the engine streams the light's frames (an own effect's too, while the live stream is watched). */
export const isStreamed = (state: LightState): boolean => STREAMED.has(state.status)

/** Offline and switched-off lights have only their marks on the stage (§9.1): no glow, no core, no strip. */
export const isDrawn = (state: LightState): boolean => state.status !== 'offline' && state.status !== 'switched-off'

/** The colour to draw without a frame: the light's own while it's on; null draws it dark. */
export function restingColour(state: LightState): RGB | null {
  return state.power === true ? state.colour : null
}
