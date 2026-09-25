// The chrome's reads from the live store, one slice each (F0 review: "so a beat doesn't re-render
// all of the chrome"). Each is null until its channel has spoken, and the part that draws it draws
// nothing until then (F0 review: no "All good" before the server's first data).
import type { AttentionItem } from '@/api/contract'
import { useLive, useLiveShallow, type Connection } from '@/api/live-store'
import { HERO_CHROME, type AttentionCounts, type TempoState } from './state'

/**
 * The tempo module's values. BPM to one decimal (§10), or null for §9.3's "No DJ": engine M1 with no
 * DJ sends Pro DJ Link at 0 BPM. The beat in the bar only while it moves.
 */
export function useTempo(): TempoState | null {
  return useLiveShallow(({ beat }) =>
    beat === null
      ? null
      : {
          source: beat.source,
          bpm: beat.source === 'prodjlink' && beat.bpm <= 0 ? null : Math.round(beat.bpm * 10) / 10,
          beat: beat.playing ? beat.beatInBar : null,
          bar: beat.bar,
          stale: beat.stale,
        },
  )
}

export function useConnection(): Connection {
  return useLive((state) => state.connection)
}

/** The link while it isn't live; null while it is, so the phone header ignores the frame rate. */
export function useConnectionUnlessLive(): Connection | null {
  return useLive((state) => (state.connection.status === 'live' ? null : state.connection))
}

/** The link's status alone: the shell's news follows it, and not the frame rate. */
export function useConnectionStatus(): Connection['status'] {
  return useLive((state) => state.connection.status)
}

/** §9.5: the items, and the light and input items apart for the dots on Devices and Inputs. */
export function countAttention(items: readonly AttentionItem[]): AttentionCounts {
  let lights = 0
  let inputs = 0
  for (const item of items) {
    if (item.subject.type === 'light') lights += 1
    else if (item.subject.type === 'input') inputs += 1
  }
  return { total: items.length, lights, inputs }
}

/** How many items need attention; null before the server's first attention snapshot. */
export function useAttentionTotal(): number | null {
  return useLive(({ attention }) => (attention === null ? null : attention.length))
}

/** How many of one kind need attention, for a nav dot; null before the first snapshot. */
export function useAttentionCount(kind: 'lights' | 'inputs'): number | null {
  return useLive(({ attention }) => (attention === null ? null : countAttention(attention)[kind]))
}

/** The server's preview only (its `transport`); null until it has said. F3 wires the switch's action. */
export function usePreviewOnly(): boolean | null {
  return useLive((state) => state.previewOnly)
}

/** The fixture until F6 (decision 10). */
export function useServerName(): string {
  return HERO_CHROME.server
}

/** The fixture until F6 (decision 10). */
export function useSunset(): string {
  return HERO_CHROME.sunset
}
