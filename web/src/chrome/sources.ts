// The tempo's sources (§6.7, §8.8; F3 decision 7): each one's name and icon, and its status line. The
// tempo module, the source chain and the hold's news share them.
import type { Deck, InputState, Inputs, TempoSource } from '@/api/contract'
import type { IconName } from '@/design/icons'
import { formatBpm, formatPitch, formatTime, formatTrackBpm } from '@/lib/format'

/** Each source's name and icon, in the chain's order: Pro DJ Link → Music → Internal. */
export const TEMPO_SOURCES: Record<TempoSource, { label: string; icon: IconName }> = {
  prodjlink: { label: 'Pro DJ Link', icon: 'deck' },
  music: { label: 'Music', icon: 'music' },
  internal: { label: 'Internal', icon: 'tempo' },
}

/** §9.3's Idle: nothing to report, nothing wrong. Where a source is named, it reads "No DJ". */
export const NO_DJ = { label: 'No DJ', icon: 'deck' } as const satisfies (typeof TEMPO_SOURCES)[TempoSource]

/** Music Assistant with no track to follow, by its state (§9.3). */
const MUSIC: Record<InputState, string> = {
  connected: 'Nothing playing',
  idle: 'Nothing playing',
  stale: 'Stale',
  disconnected: "Can't reach it",
}

/** Each source's status line (F3 decision 7): what it drives the clock with, or why it can't. */
export function sourceStatuses(inputs: Inputs, decks: readonly Deck[]): Record<TempoSource, string> {
  const master = decks.find((deck) => deck.master && deck.state === 'playing')
  const deck =
    master === undefined
      ? null
      : master.bpm === null
        ? `Deck ${master.number}`
        : `Deck ${master.number} · ${formatTrackBpm(master.bpm)} ${formatPitch(master.pitch_percent)}`
  const { music } = inputs
  const { internal } = inputs.tempo
  const when = internal.how === 'default' || internal.at === null ? '' : ` ${formatTime(new Date(internal.at))}`
  return {
    prodjlink: deck ?? 'No DJ on the network',
    // Music Assistant is engine M7's: an engine without it serves no `music`.
    music: music === undefined ? 'Not set up' : music.state === 'connected' && music.track !== null ? `Beat of “${music.track.title}”` : MUSIC[music.state],
    internal: `${formatBpm(internal.bpm)} · ${internal.how}${when}`,
  }
}
