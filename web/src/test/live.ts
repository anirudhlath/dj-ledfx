import type { AttentionItem, Id } from '@/api/contract'
import { applyMessage, liveStore } from '@/api/live-store'
import { beatMessage, snapshotMessages } from '@/api/mocks/mock-server'
import { buildScenario, type ScenarioName } from '@/api/mocks/scenarios'

/** The hero moment (§12.5): Wednesday 23 September 2026, 19:14. */
export const HERO_NOW = new Date(2026, 8, 23, 19, 14)

/** Fills the app's live store as a scenario's server does on connect: snapshots, a beat, and 60 fps. */
export function seedLive(name: ScenarioName = 'hero', now: Date = HERO_NOW): void {
  const state = buildScenario(name, now)
  const at = now.getTime() / 1000
  for (const message of snapshotMessages(state, 2)) applyMessage(liveStore, message, at)
  applyMessage(liveStore, beatMessage(state, 0, at, 2), at)
  liveStore.setState({ connection: { status: 'live', fps: 60 } })
}

const KIND = { light: 'light-offline', zone: 'zone-crashed', input: 'input-disconnected' } as const

/** One attention item about a light, a zone or an input. */
export function attentionAbout(type: keyof typeof KIND, id: Id): AttentionItem {
  return {
    id: `${KIND[type]}:${id}`,
    severity: 'normal',
    kind: KIND[type],
    subject: { type, id },
    title: id,
    detail: id,
    since: '2026-09-23T19:02:00-05:00',
    actions: ['details'],
  }
}
