// §6.3 ZonePicker: "chips for Whole home, each room with lights, each sub-zone …, saved custom groups,
// and a dashed 'Pick lights…' chip. Each chip shows what's running there in small text; the selected chip
// is inverted." The zones come in the server's order (F4 ruling 5) with F4 ruling 4's notes. The desktop's
// chips wrap along the top of the stage (§8.2 Where; Live-PutLookOn); the phone's are
// LIVE_SPEC.phoneComposer.zonePx buttons in a row that scrolls (§8.10; Phone-PutLookOn), where the chosen
// one leads the row as the composer opens, as drawn, and a later choice scrolls only as far as it must.
// A note on a chip that isn't chosen is text-2, not the renders' text-3, which on the control fill falls
// short of §14's contrast (F4 ruling 19). Picking lights has no milestone yet, so its chip is drawn but
// can't be used (F4 ruling 6): aria-disabled, with the default cursor where app.css gives every other
// button a pointer. Only Live-PutLookOn draws it; Phone-PutLookOn's row is the zones alone, and the renders
// are the layout's authority, so the phone has none.
// Sizes: the desktop chips are Live-PutLookOn's, with its 11.5 px note (no token has it), and the phone's
// buttons Phone-PutLookOn's. Both are <button>s, which draw border-box, so a render's heights are the ones
// drawn. The desktop chips are under --touch-min, so they keep their face and grow their hit area
// (touch-target). The phone's row scrolls, which clips on both axes, so it pads by the reach of a focus ring
// (tokens.css's outline and offset) and pulls back by as much, moving nothing; scroll-px-1 keeps a button
// snapped where it sits.
import { useId, useLayoutEffect, useRef } from 'react'
import type { Id, RunningZone, Zone } from '@/api/contract'
import { cx } from '@/design/cx'
import { Icon } from '@/design/icon'
import { LIVE_RENDER, LIVE_SPEC } from '@/design/live-numbers'
import { runningOn, zoneNote } from './model'

export interface ZonePickerProps {
  zones: readonly Zone[]
  running: readonly RunningZone[]
  /** The chosen zone. */
  selected: Id
  /** §8.2: "Home looks (whole-home scope) lock the zone to Whole home": the others can't be chosen. */
  locked: boolean
  onSelect: (zoneId: Id) => void
  variant: 'desktop' | 'phone'
}

export function ZonePicker({ zones, running, selected, locked, onSelect, variant }: ZonePickerProps) {
  const label = useId()
  const chosen = useRef<HTMLButtonElement>(null)
  const opened = useRef(false)
  const phone = variant === 'phone'
  // A layout effect, so the row moves in the commit that chooses a zone, before the paint (as collapse.ts and the
  // swatch do): the composer mounts in a navigation, a transition, and an effect could run after the frame that
  // shows the sheet, with the row at its start and a later choice's chip inverted a frame before the row moved.
  useLayoutEffect(() => {
    if (!phone) return
    chosen.current?.scrollIntoView?.({ block: 'nearest', inline: opened.current ? 'nearest' : 'start' })
    opened.current = true
  }, [phone, selected])

  const chips = zones.map((zone) => {
    const on = zone.id === selected
    const note = zoneNote(zone, runningOn(zone, running, zones))
    const tone = on ? 'border-text bg-text text-on-text' : 'border-line bg-control text-text'
    const noteColour = on ? { color: phone ? LIVE_RENDER.selectedZoneNote.button : LIVE_RENDER.selectedZoneNote.chip } : undefined
    return (
      <button
        key={zone.id}
        ref={on ? chosen : undefined}
        type="button"
        aria-pressed={on}
        disabled={locked && zone.kind !== 'home'}
        className={cx(
          'border disabled:opacity-45',
          phone
            ? 'flex shrink-0 snap-start flex-col items-start justify-center gap-0.5 rounded-card px-3.5'
            : 'inline-flex h-8 items-center gap-1.75 rounded-pill px-3 text-size-control font-semibold touch-target',
          tone,
        )}
        style={phone ? { height: LIVE_SPEC.phoneComposer.zonePx } : undefined}
        onClick={() => onSelect(zone.id)}
      >
        {phone ? <span className="text-body font-semibold whitespace-nowrap">{zone.name}</span> : zone.name}
        <span className={cx(phone ? 'text-label whitespace-nowrap' : 'text-[11.5px] font-medium', !on && 'text-text-2')} style={noteColour}>
          {note}
        </span>
      </button>
    )
  })

  if (phone) {
    return (
      <div className="flex flex-col gap-2">
        <span id={label} className="label-caps text-text-3">
          Where
        </span>
        <div role="group" aria-labelledby={label} className="-m-1 flex snap-x snap-proximity scroll-px-1 gap-2 overflow-x-auto p-1">
          {chips}
        </div>
      </div>
    )
  }
  return (
    <div role="group" aria-labelledby={label} className="flex flex-wrap items-center gap-2">
      <span id={label} className="mr-1 text-meta text-text-3">
        Where
      </span>
      {chips}
      <button
        type="button"
        aria-disabled="true"
        className="inline-flex h-8 items-center gap-1.5 rounded-pill border border-dashed border-line-strong px-3 text-size-control font-semibold text-text-2 touch-target aria-disabled:cursor-default"
      >
        <Icon name="plus" size={14} />
        Pick lights…
      </button>
    </div>
  )
}
