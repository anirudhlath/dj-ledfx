// The chrome's reads from the live store, one slice each (F0 review: "so a beat doesn't re-render
// all of the chrome"). Each is null until its channel has spoken, and the part that draws it draws
// nothing until then (F0 review: no "All good" before the server's first data).
import type { AttentionItem } from '@/api/contract'
import { useLive, useLiveShallow, type Connection } from '@/api/live-store'
import { HERO_CHROME, type AttentionCounts, type TempoState } from './state'

/** The tempo module's values. BPM to one decimal (§10); the beat in the bar only while it moves. */
export function useTempo(): TempoState | null {
  return useLiveShallow(({ beat }) =>
    beat === null
      ? null
      : {
          source: beat.source,
          bpm: Math.round(beat.bpm * 10) / 10,
          beat: beat.playing ? beat.beatInBar : null,
          bar: beat.bar,
          stale: beat.stale,
        },
  )
}

export function useConnection(): Connection {
  return useLive((state) => state.connection)
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

export function useAttentionCounts(): AttentionCounts | null {
  return useLiveShallow(({ attention }) => (attention === null ? null : countAttention(attention)))
}

/** The fixture until F3 wires the switch to the server (decision 10). */
export function usePreviewOnly(): boolean {
  return HERO_CHROME.previewOnly
}

/** The fixture until F6 (decision 10). */
export function useServerName(): string {
  return HERO_CHROME.server
}

/** The fixture until F6 (decision 10). */
export function useSunset(): string {
  return HERO_CHROME.sunset
}
