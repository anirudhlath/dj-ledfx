// Phone-Tempo (§8.10 Tempo), the phone's /inputs: the source line, the BPM at 80 in mono, the master deck's
// track BPM and pitch with the bar and the beat, four big pips, a 72 px TAP with what a tap does now, the
// decks padded to four (F3 decision 26), and Music Assistant's note while nothing plays. The pips, the bar
// and the beat are the pip writer's (F3 decision 3), so a beat redraws no React. The hold is said in words,
// with the way back (F3 decision 6), and TAP is off under a Pro DJ Link or Music lock (F3 decision 5). The
// words are F3 decision 40's. Look: Phone-Tempo.html.
import { useRef, useState, type RefObject } from 'react'
import { failureText, setTempoLock } from '@/api/actions'
import type { Deck } from '@/api/contract'
import { useLive } from '@/api/live-store'
import { useTapTempo, useTempo } from '@/chrome/hooks'
import { PIP_STYLE, usePips } from '@/chrome/pip-writer'
import { NO_DJ, TEMPO_SOURCES } from '@/chrome/sources'
import type { TempoState } from '@/chrome/state'
import { useAnnounce } from '@/design/announce'
import { Button } from '@/design/button'
import { cx } from '@/design/cx'
import { Icon } from '@/design/icon'
import { formatBpm, formatPitch, formatTrackBpm } from '@/lib/format'
import { DeckSlot } from './deck-slot'

/** The pip writer's words under the BPM: "bar 17 · beat 3". One function, so the pips register once. */
const BAR_AND_BEAT = (bar: number, beat: number) => `bar ${bar} · beat ${beat}`
/** Four of everything: a bar's beats, and a Pro DJ Link set's decks (F3 decision 26). */
const FOUR = [1, 2, 3, 4]

export function PhoneTempo() {
  const tempo = useTempo()
  const decks = useLive((state) => state.decks)
  const quietMusic = useLive((state) => {
    const music = state.inputs?.music
    return music !== undefined && music.track === null && (music.state === 'idle' || music.state === 'connected')
  })
  if (tempo === null) return null
  const master = decks?.find((deck) => deck.master && deck.state === 'playing')
  return (
    <div className="flex flex-col gap-3 px-4 pt-1 pb-4">
      <Readout {...tempo} master={master} />
      <TapPad {...tempo} />
      <section aria-labelledby="decks" className="flex flex-col gap-2">
        <h2 id="decks" className="label-caps">
          Decks
        </h2>
        <ul className="flex flex-col gap-2">
          {FOUR.map((number) => (
            <DeckSlot key={number} number={number} deck={decks?.find((deck) => deck.number === number)} />
          ))}
        </ul>
      </section>
      {quietMusic && (
        <p className="flex items-center gap-2.5 rounded-card border border-dashed border-line-strong p-3 text-data text-text-3">
          <Icon name="music" size={16} className="shrink-0" />
          Music Assistant: nothing playing. Audio looks wait for music.
        </p>
      )}
    </div>
  )
}

/** The source line, the BPM and the line under it, and the pips. Idle (§9.3), only "No DJ". */
function Readout({ source, bpm, stale, held, bars, master }: TempoState & { master: Deck | undefined }) {
  const bar = useRef<HTMLSpanElement>(null)
  const idle = bpm === null
  const named = idle ? NO_DJ : TEMPO_SOURCES[source]
  const detail = idle ? null : held && source === 'internal' ? 'held' : source === 'prodjlink' && master !== undefined ? `Deck ${master.number}` : null
  const track = source === 'prodjlink' && master?.bpm != null ? `${formatTrackBpm(master.bpm)} ${formatPitch(master.pitch_percent)}` : null
  return (
    <>
      <div className="flex flex-col items-center gap-1 pt-1">
        <span className={cx('inline-flex items-center gap-1.5 text-data font-semibold', idle ? 'text-text-3' : stale ? 'text-signal' : 'text-text-2')}>
          <Icon name={named.icon} size={15} />
          {detail === null ? named.label : `${named.label} · ${detail}`}
          {stale && <span className="sr-only">, stale</span>}
        </span>
        {!idle && <span className="num text-bpm-xl font-medium tracking-[-0.05em]">{formatBpm(bpm)}</span>}
        {!idle && (track !== null || bars) && (
          <span className="text-data text-text-3">
            {track}
            {track !== null && bars && ' · '}
            {bars && <span ref={bar} />}
          </span>
        )}
      </div>
      {!idle && <BigPips stale={stale} bar={bar} />}
    </>
  )
}

/** Phone-Tempo's pips, the downbeat wider. Its own component, so the pips register as they mount. */
function BigPips({ stale, bar }: { stale: boolean; bar: RefObject<HTMLElement | null> }) {
  const row = useRef<HTMLDivElement>(null)
  usePips(row, bar, stale, BAR_AND_BEAT)
  return (
    <div ref={row} {...(stale ? { 'aria-hidden': true } : { role: 'img' })} className="flex justify-center gap-2">
      {FOUR.map((n) => (
        <span key={n} className={cx('h-10 rounded-control', n === 1 ? 'w-17.5' : 'w-14')} style={PIP_STYLE} />
      ))}
    </div>
  )
}

/** TAP, and what a tap does now (F3 decision 40): the hold and a lock each offer Back to Auto. */
function TapPad({ source, lock, held }: TempoState) {
  const onTap = useTapTempo()
  const announce = useAnnounce()
  const [sending, setSending] = useState(false)
  // F3 decision 5: under these locks the engine refuses a tap.
  const lockedTo = lock === 'prodjlink' || lock === 'music' ? TEMPO_SOURCES[lock].label : null
  const backToAuto = () => {
    setSending(true)
    setTempoLock('auto')
      .catch((error: unknown) => announce(failureText(held ? 'give the tempo back' : 'unlock the tempo', error)))
      .finally(() => setSending(false))
  }
  // Internal's lock leaves TAP on: a tap sets the tempo it holds, and only Back to Auto lets a DJ take over.
  const hint = held
    ? 'Internal holds the tempo until a DJ starts again.'
    : lockedTo !== null
      ? `Locked to ${lockedTo}, so tapping is off.`
      : lock === 'internal'
        ? `Locked to ${TEMPO_SOURCES.internal.label}. Tap along to set the tempo.`
        : source === 'prodjlink'
        ? 'The DJ has the tempo. Tapping takes over with Internal.'
        : source === 'music'
          ? 'The music has the tempo. Tapping takes over with Internal.'
          : 'Tap along to set the tempo.'
  return (
    <>
      <button
        type="button"
        disabled={lockedTo !== null}
        onClick={onTap}
        className="h-18 rounded-[18px] border border-line-strong bg-control-hover text-display-xs font-bold tracking-[0.14em] text-text uppercase disabled:pointer-events-none disabled:opacity-45"
      >
        Tap
      </button>
      <div className="-mt-1.5 flex flex-col items-center gap-2">
        <p className="text-center text-meta text-text-3">{hint}</p>
        {(held || lock !== 'auto') && (
          <Button size="sm" disabled={sending} onClick={backToAuto}>
            Back to Auto
          </Button>
        )}
      </div>
    </>
  )
}
