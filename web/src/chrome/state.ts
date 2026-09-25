// The chrome's data. The live store (src/api/live-store.ts) produces it; hooks.ts reads it one slice
// at a time, and the components in this folder draw it.
import type { TempoSource } from '@/api/contract'
import type { Connection } from '@/api/live-store'

export interface TempoState {
  source: TempoSource
  /**
   * null: no DJ (engine M1's beat at 0 BPM), §9.3's Idle. The module says "No DJ" in a quiet chip
   * and draws no BPM or pips; TAP stays.
   */
  bpm: number | null
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
 * draws it, and hooks.ts serves its server name and sunset until F6 owns them (decision 10).
 * Preview only is the server's now (its transport); only the switch's action waits for F3.
 */
export const HERO_CHROME: ChromeState = {
  tempo: { source: 'music', bpm: 121.8, beat: 2, bar: 42, stale: false },
  previewOnly: false,
  attention: { total: 1, lights: 1, inputs: 0 },
  connection: { status: 'live', fps: 60 },
  server: 'homeserver',
  sunset: '19:26',
}
