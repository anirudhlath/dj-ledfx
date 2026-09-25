// The chrome's data. The live store (src/api/live-store.ts) produces it; hooks.ts reads it one slice
// at a time, and the components in this folder draw it.
import type { TempoSource } from '@/api/contract'
import type { Connection } from '@/api/live-store'

export type { Connection, TempoSource }

export interface TempoState {
  source: TempoSource
  bpm: number
  /** Beat in the bar, 1–4. null: the beat doesn't move (stopped, stale, or 0 BPM), so no pip lights. */
  beat: number | null
  /** null: the source counts no bars (engine M1's beat), and the module leaves "bar N" out. */
  bar: number | null
  /** §6.2: the source stopped updating; its label turns signal and the pips stop. */
  stale: boolean
}

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
 * The §12.5 "hero" scenario's chrome, as drawn in Main.png and Phone-Live.png. The System specimen
 * draws it, and hooks.ts serves its preview only, server name and sunset until F3 and F6 own them
 * (decision 10).
 */
export const HERO_CHROME: ChromeState = {
  tempo: { source: 'music', bpm: 121.8, beat: 2, bar: 42, stale: false },
  previewOnly: false,
  attention: { total: 1, lights: 1, inputs: 0 },
  connection: { status: 'live', fps: 60 },
  server: 'homeserver',
  sunset: '19:26',
}
