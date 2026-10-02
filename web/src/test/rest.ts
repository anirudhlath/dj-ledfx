// REST's answers for a scenario, put straight into the app's query cache: a page under test reads
// them as if it had fetched them, with no server. The shared setup clears the cache after each test.
import { queries, queryClient } from '@/api/queries'
import { buildScenario, type ScenarioName, type ScenarioState } from '@/api/mocks/scenarios'
import { HERO_NOW } from './live'

export function seedRest(name: ScenarioName = 'hero', now: Date = HERO_NOW): ScenarioState {
  const state = buildScenario(name, now)
  queryClient.setQueryData(queries.home().queryKey, state.home)
  queryClient.setQueryData(queries.lights().queryKey, state.lights)
  queryClient.setQueryData(queries.zones().queryKey, state.zones)
  return state
}
