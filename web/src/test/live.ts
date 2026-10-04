import { onTestFinished } from 'vitest'
import type { AttentionItem, Id } from '@/api/contract'
import { decodeFrame, encodeFrame, type FrameStore } from '@/api/frames'
import { clientNow, normaliseBeat } from '@/api/beat'
import { beatClock, frames, startDataLayer } from '@/api/live'
import { applyMessage, liveStore } from '@/api/live-store'
import { inMemorySockets } from '@/api/mocks/in-memory-socket'
import { beatMessage, MockServer, snapshotMessages, type MockServerOptions } from '@/api/mocks/mock-server'
import { buildScenario, type ScenarioName } from '@/api/mocks/scenarios'

/** The hero moment (§12.5): Wednesday 23 September 2026, 19:14. */
export const HERO_NOW = new Date(2026, 8, 23, 19, 14)
/** When the hero's lights took the status they have outside its looks: 70 minutes before HERO_NOW, as its scenario has it. */
export const HERO_SINCE = new Date(HERO_NOW.getTime() - 70 * 60_000).toISOString()

/** Fills the app's live store and beat clock as a scenario's server does on connect: snapshots, a beat, and 60 fps. */
export function seedLive(name: ScenarioName = 'hero', now: Date = HERO_NOW): void {
  const state = buildScenario(name, now)
  const at = now.getTime() / 1000
  for (const message of snapshotMessages(state, 2)) applyMessage(liveStore, message, at)
  // The beat goes to the store and to the beat clock, as the live client does: the pips follow the clock.
  const beat = normaliseBeat(beatMessage(state, 0, at, 2), clientNow())
  liveStore.setState({ beat })
  beatClock.receive(beat, null)
  liveStore.setState({ connection: { status: 'live', fps: 60 } })
}

/** A running mock server on Date.now(), which fake timers move; it stops when the test finishes. */
export function startMockServer(options: MockServerOptions = {}): MockServer {
  const server = new MockServer({ clock: () => Date.now(), ...options })
  server.start()
  onTestFinished(() => server.stop())
  return server
}

/** The app's data layer on a mock server, through the in-memory socket; the setup resets it after the test. */
export function startMockDataLayer(options: MockServerOptions = {}): MockServer {
  const server = startMockServer(options)
  startDataLayer({ openSocket: inMemorySockets(server), url: 'mock' })
  return server
}

/** A light's live frame, `rgb` three bytes an LED, decoded as the socket would: into the app's frame store unless given another. */
export function pushFrame(id: Id, seq: number, rgb: ArrayLike<number>, { store = frames, at = 0 }: { store?: FrameStore; at?: number } = {}): void {
  decodeFrame(encodeFrame(2, id, seq, Uint8Array.from(rgb)), 2, store, at)
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
