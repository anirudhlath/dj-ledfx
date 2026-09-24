// The chrome's data. F1's stores produce these types; the components in this folder draw them.

export type TempoSource = 'prodjlink' | 'music' | 'internal'

export interface TempoState {
  source: TempoSource
  bpm: number
  /** Beat in the bar, 1–4. */
  beat: number
  bar: number
  /** §6.2: the source stopped updating; its label turns signal and the pips stop. */
  stale: boolean
}

export type Connection = { status: 'live'; fps: number } | { status: 'reconnecting'; attempt: number }

export interface AttentionCounts {
  total: number
  /** Light items: the rail dot on Devices. */
  lights: number
  /** Input items: the rail dot on Inputs (the Tempo tab on phone). */
  inputs: number
}

/** Everything the chrome shows. */
export interface ChromeState {
  tempo: TempoState
  previewOnly: boolean
  attention: AttentionCounts
  connection: Connection
  /** The server's name, in the rail footer. */
  server: string
  /** Today's sunset, 24 h, in the phone Live context line. */
  sunset: string
}

/**
 * The §12.5 "hero" scenario, as drawn in Main.png and Phone-Live.png: tempo from Music at 121.8,
 * Rope offline (one light needs attention), connected at 60 fps.
 */
export const HERO_CHROME: ChromeState = {
  tempo: { source: 'music', bpm: 121.8, beat: 2, bar: 42, stale: false },
  previewOnly: false,
  attention: { total: 1, lights: 1, inputs: 0 },
  connection: { status: 'live', fps: 60 },
  server: 'homeserver',
  sunset: '19:26',
}

/** F0 shows the hero fixture. F1 and F3 replace this with the live stores. */
export function useChrome(): ChromeState {
  return HERO_CHROME
}
