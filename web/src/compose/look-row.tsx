// §8.10 Put a look on's look rows (Phone-PutLookOn): the thumb at LIVE_SPEC.phoneComposer.thumb, the
// name in serif, and one line (rowNote()); the chosen row framed in `text` with a check. On the chosen
// row's control fill the line is text-2, not the render's text-3, for §14's contrast (F4 ruling 19). The
// name's 21 px and the line's 11.5 px are Phone-PutLookOn's.
import { cx } from '@/design/cx'
import { Icon } from '@/design/icon'
import { LookThumb } from '@/looks/look-thumb'
import type { LookTileProps } from './look-tile'
import { lookLabel, rowNote } from './model'

export function LookRow({ look, selected, here, missing, tabbable, onSelect }: LookTileProps) {
  const note = rowNote(look, selected, here, missing)
  return (
    <button
      type="button"
      aria-pressed={selected}
      aria-label={lookLabel(look, here, missing)}
      data-look={look.id}
      tabIndex={tabbable ? 0 : -1}
      className={cx(
        'flex w-full items-center gap-3 rounded-card border p-2 text-left',
        selected ? 'border-text bg-control' : 'border-transparent',
      )}
      onClick={onSelect}
    >
      <LookThumb lookId={look.id} size="row" />
      <span className="flex min-w-0 grow flex-col gap-0.5">
        <span className="font-serif text-[21px] leading-[1.1] text-text">{look.name}</span>
        <span className={cx('text-[11.5px]', note.signal ? 'text-signal' : selected ? 'text-text-2' : 'text-text-3')}>{note.text}</span>
      </span>
      {selected && <Icon name="check" size={18} className="shrink-0 text-text" />}
    </button>
  )
}
