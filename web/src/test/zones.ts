// A scenario's zone world, as the cards see it once REST and the socket have both answered.
import type { Id, RunningZone } from '@/api/contract'
import { buildScenario, type ScenarioName, type ScenarioState } from '@/api/mocks/scenarios'
import { zoneWorld, type ZoneWorld } from '@/zones/zone-view'
import { HERO_NOW } from './live'

/** The scenario at HERO_NOW, after `change` edits it, and the world its cards read. */
export function scenarioWorld(name: ScenarioName, change?: (state: ScenarioState) => void): { state: ScenarioState; world: ZoneWorld } {
  const state = buildScenario(name, HERO_NOW)
  change?.(state)
  const { zones, looks, lights, beat, running, attention } = state
  return { state, world: zoneWorld({ zones, looks, lights, updates: null, beatSource: beat.source, running, attention }) }
}

/** The zone running in `zoneId`; the scenario must run one there. */
export function runningIn(state: ScenarioState, zoneId: Id): RunningZone {
  const zone = state.running.find((each) => each.zoneId === zoneId)
  if (zone === undefined) throw new Error(`Nothing runs in ${zoneId}`)
  return zone
}
