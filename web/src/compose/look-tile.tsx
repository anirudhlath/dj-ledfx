// §6.4 LookTile (composer, LIVE_SPEC.lookTile.px wide): the look's thumb, its name in serif and the
// icons of the inputs it uses; PREVIEWING while the stage previews it, RUNNING HERE while it runs on the
// chosen zone, and the first input it would wait for in signal (§8.2). Live-PutLookOn draws it, with no
// input on any tile, so the icons (13 px) and the signal line (11.5 px) take the sizes Looks.html's
// LookCard draws its inputs at. The icons say nothing to a screen reader, and the label replaces what the
// button holds, so the look's category and inputs (lookInputs()) are its description, in a visually hidden
// span, which the tile holds with `relative`: an absolutely positioned span with no positioned ancestor in its
// grid escapes the grid's clip and stretches <main>'s scroll area.
import { useId } from 'react'
import type { Look } from '@/api/contract'
import { cx } from '@/design/cx'
import { Icon } from '@/design/icon'
import { LIVE_SPEC } from '@/design/live-numbers'
import { LookThumb } from '@/looks/look-thumb'
import { chipsFor } from '@/zones/zone-view'
import { lookInputs, lookLabel, MISSING_SIGNAL, type MissingInput } from './model'

export interface LookTileProps {
  look: Look
  /** The look the stage previews: aria-pressed. */
  selected: boolean
  /** The look the chosen zone runs now. */
  here: boolean
  /** The inputs it would wait for (missingInputs()). */
  missing: readonly MissingInput[]
  /** The list's one tab stop (F4 ruling 12). */
  tabbable: boolean
  onSelect: () => void
}

// Live-PutLookOn's tags: 8 px in from the thumb's corner, 10.5 px bold caps. PREVIEWING is 20 px high; RUNNING
// HERE is drawn 20 px plus a 1 px border each side (the render sets no box-sizing), so it's 22 px here.
const TAG = 'absolute top-2 left-2 inline-flex items-center rounded-pill px-1.75 text-[10.5px] font-bold tracking-[0.06em] uppercase'

export function LookTile({ look, selected, here, missing, tabbable, onSelect }: LookTileProps) {
  const inputs = useId()
  return (
    <button
      type="button"
      aria-pressed={selected}
      aria-label={lookLabel(look, here, missing)}
      aria-describedby={inputs}
      data-look={look.id}
      tabIndex={tabbable ? 0 : -1}
      className="relative flex min-w-0 flex-col gap-2 text-left"
      onClick={onSelect}
    >
      <LookThumb lookId={look.id} size="tile" className={selected ? 'border-[1.5px] border-text' : 'border-line'}>
        {selected ? (
          <span className={cx(TAG, 'h-5 gap-1.25 bg-text text-on-text')}>
            <Icon name="eye" size={12} />
            Previewing
          </span>
        ) : (
          here && <span className={cx(TAG, 'h-5.5 border border-line bg-bg/80 text-text-2')}>Running here</span>
        )}
      </LookThumb>
      <span className="flex items-center justify-between gap-1.5 px-0.5">
        <span className="font-serif leading-[1.1] text-text" style={{ fontSize: LIVE_SPEC.lookTile.namePx }}>
          {look.name}
        </span>
        <span className="inline-flex gap-1">
          {chipsFor(look, missing).map((chip) => (
            <Icon key={chip.kind} name={chip.icon} size={13} className={chip.waiting ? 'text-signal' : 'text-text-3'} />
          ))}
        </span>
      </span>
      {missing.length > 0 && <span className="px-0.5 text-[11.5px] text-signal">{MISSING_SIGNAL[missing[0]]}</span>}
      <span id={inputs} className="sr-only">
        {lookInputs(look)}
      </span>
    </button>
  )
}
