// What the socket has said (spec §12.4), in one zustand store. Each value is null until its channel
// has spoken, so nothing claims to know what it hasn't heard (F0 review). Components read it a slice
// at a time through useLive(selector), so a message re-renders only the components whose slice
// changed. Frames don't come here: they go to the FrameStore, which React never watches.
import { useStore } from 'zustand'
import { useShallow } from 'zustand/react/shallow'
import { createStore, type StoreApi } from 'zustand/vanilla'
import { normaliseBeat, type Beat } from './beat'
import type { AttentionItem, Deck, Id, Inputs, LightUpdate, Overlay, RunningZone, SignalValue } from './contract'
import type { DeviceStat, ServerMessage } from './ws-messages'

/** The link: before its first message, live (with the measured frame rate), or retrying. */
export type Connection =
  | { status: 'connecting' }
  | { status: 'live'; fps: number | null }
  | { status: 'reconnecting'; attempt: number }

export interface LiveState {
  connection: Connection
  /** The latest beat message. Motion samples the BeatClock instead (§5.4). */
  beat: Beat | null
  decks: Deck[] | null
  running: { zones: RunningZone[]; overlays: Overlay[] } | null
  lights: Record<Id, LightUpdate> | null
  stats: Record<Id, DeviceStat> | null
  attention: AttentionItem[] | null
  previewOnly: boolean | null
  inputs: Inputs | null
  signals: Record<string, SignalValue> | null
}

export const EMPTY_LIVE: LiveState = {
  connection: { status: 'connecting' },
  beat: null,
  decks: null,
  running: null,
  lights: null,
  stats: null,
  attention: null,
  previewOnly: null,
  inputs: null,
  signals: null,
}

export type LiveStore = StoreApi<LiveState>

export function createLiveStore(): LiveStore {
  return createStore<LiveState>()(() => ({ ...EMPTY_LIVE }))
}

/** The app's store. The shared test setup resets it after every test. */
export const liveStore = createLiveStore()

export function resetLiveStore(store: LiveStore = liveStore): void {
  store.setState({ ...EMPTY_LIVE }, true)
}

function byId<T extends { id: Id }>(items: T[]): Record<Id, T> {
  return Object.fromEntries(items.map((item) => [item.id, item]))
}

/** Stores one message. A channel the stores don't keep (ack, error, status, fx, or one not known yet) changes nothing. */
export function applyMessage(store: LiveStore, message: ServerMessage, receivedAt: number): void {
  switch (message.channel) {
    case 'beat':
      store.setState({ beat: normaliseBeat(message, receivedAt) })
      return
    case 'decks':
      store.setState({ decks: message.decks })
      return
    case 'running':
      store.setState({ running: { zones: message.zones, overlays: message.overlays ?? [] } })
      return
    case 'lights':
      store.setState({ lights: byId(message.lights) })
      return
    case 'stats':
      store.setState({ stats: byId(message.devices) })
      return
    case 'attention':
      store.setState({ attention: message.items })
      return
    case 'transport':
      store.setState({ previewOnly: message.state === 'simulating' })
      return
    case 'inputs':
      store.setState({ inputs: message.inputs })
      return
    case 'signals':
      store.setState({ signals: message.values })
      return
    default:
      return
  }
}

/** One slice of the live store; the component re-renders when that slice changes. */
export function useLive<T>(selector: (state: LiveState) => T): T {
  return useStore(liveStore, selector)
}

/** useLive for a selector that builds an object: it re-renders only when one of its fields changed. */
export function useLiveShallow<T>(selector: (state: LiveState) => T): T {
  return useStore(liveStore, useShallow(selector))
}
