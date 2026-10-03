// §6.7 DeckSlot as Phone-Tempo draws it: the deck's number in a circle, the player and its state (cued or
// playing, with its track's BPM and pitch), and a MASTER badge on the deck the clock follows. A slot the
// engine hasn't heard is "Deck N", empty, as Inputs.png names it (F3 decision 26); Phone-Tempo draws it
// solid, where Inputs.png's dashed slots are F6's. Look: Phone-Tempo.html, which sets the number and the status
// in mono.
import type { Deck } from '@/api/contract'
import { cx } from '@/design/cx'
import { formatPitch, formatTrackBpm } from '@/lib/format'

const STATE = { empty: 'Empty', cued: 'Cued', playing: 'Playing' } as const satisfies Record<Deck['state'], string>

/** "Playing · 124.00 · +1.2%": the state, then the track's BPM and pitch while the deck has a track. */
function statusOf(deck: Deck | undefined): string {
  if (deck === undefined || deck.state === 'empty') return STATE.empty
  const said = STATE[deck.state]
  return deck.bpm === null ? said : `${said} · ${formatTrackBpm(deck.bpm)} · ${formatPitch(deck.pitch_percent)}`
}

export function DeckSlot({ number, deck }: { number: number; deck: Deck | undefined }) {
  const master = deck?.master === true
  const empty = deck === undefined || deck.state === 'empty'
  return (
    <li className={cx('flex min-h-13 items-center gap-3 rounded-card border px-3', master ? 'border-text bg-control' : 'border-line')}>
      <span
        className={cx(
          'num inline-flex size-7.5 shrink-0 items-center justify-center rounded-full border text-size-control font-semibold',
          master ? 'border-text' : 'border-line-strong',
        )}
      >
        {number}
      </span>
      <span className="flex min-w-0 grow flex-col gap-0.5">
        <span className={cx('truncate text-body font-semibold', empty ? 'text-text-3' : 'text-text')}>{deck?.player ?? `Deck ${number}`}</span>
        <span className={cx('num text-[11.5px]', master ? 'text-text-2' : 'text-text-3')}>{statusOf(deck)}</span>
      </span>
      {master && (
        <span className="inline-flex h-5.5 shrink-0 items-center rounded-full bg-text px-2 text-[10.5px] font-bold tracking-[0.06em] text-on-text uppercase">
          Master
        </span>
      )}
    </li>
  )
}
