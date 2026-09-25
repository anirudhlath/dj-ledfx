// Which mock the page asks for (decision 11): in dev only with ?scenario=, in the mock build always.
import { isScenario, type ScenarioName } from './scenarios'

export interface MockChoice {
  scenario: ScenarioName
  /** ?still: the beat holds, for screenshots and render counts. */
  still: boolean
  /** ?protocol=1: speak as engine M1 does today. */
  protocol: 1 | 2
}

/** The mock the URL asks for, or null for the real server. An unknown scenario plays the hero. */
export function mockChoice(search: string, { mockBuild }: { mockBuild: boolean }): MockChoice | null {
  const params = new URLSearchParams(search)
  const asked = params.get('scenario')
  if (asked === null && !mockBuild) return null
  return {
    scenario: asked !== null && isScenario(asked) ? asked : 'hero',
    still: params.has('still'),
    protocol: params.get('protocol') === '1' ? 1 : 2,
  }
}
