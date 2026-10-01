// What the stage draws (§8.1 "Data: home geometry, frames, running zones, … inputs (sun), …
// connection"), all through src/api: the home, the lights and the zones from REST; what each light
// shows now, what runs, the sun and the link from the live store, a slice at a time. Frames stay in
// the frame store, where only the canvas reads them.
import { useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'
import type { Home, Id, Light, RunningZone, SunInput } from '@/api/contract'
import { useLive } from '@/api/live-store'
import { queries } from '@/api/queries'
import { lightStates, type LightState } from './show'

export interface StageData {
  home: Home
  lights: readonly Light[]
  /** Each light's status, power and colour: the latest push's, else REST's. */
  states: ReadonlyMap<Id, LightState>
  running: readonly RunningZone[]
  /** For the tooltip's "look · zone"; empty until the zones load. */
  zoneNames: ReadonlyMap<Id, string>
  /** Null until the server says (engine M2 has no inputs yet). */
  sun: SunInput | null
  /** The link dropped: §7.6 frozen. */
  frozen: boolean
}

const NOTHING_RUNS: readonly RunningZone[] = []

/** The stage's data; null until the home and the lights have loaded. */
export function useStageData(): StageData | null {
  const home = useQuery(queries.home()).data
  const lights = useQuery(queries.lights()).data
  const zones = useQuery(queries.zones()).data
  const updates = useLive((state) => state.lights)
  const running = useLive((state) => state.running?.zones ?? NOTHING_RUNS)
  const sun = useLive((state) => state.inputs?.sun ?? null)
  const frozen = useLive((state) => state.connection.status === 'reconnecting')
  const states = useMemo(() => lightStates(lights ?? [], updates), [lights, updates])
  const zoneNames = useMemo(() => new Map((zones ?? []).map((zone) => [zone.id, zone.name])), [zones])
  if (home === undefined || lights === undefined) return null
  return { home, lights, states, running, zoneNames, sun, frozen }
}
