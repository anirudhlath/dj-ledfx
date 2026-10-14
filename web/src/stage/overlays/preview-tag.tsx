// §7.6 compose's "PREVIEW ON SCREEN" tag, which "says the lights are still running the old look": the
// desktop's card beside the chosen zone (Live-PutLookOn) and the phone's tag on its stage
// (Phone-PutLookOn), each shown while the preview stream draws the look. The card's width, type and
// tracking are Live-PutLookOn's measurements, and the tag's are Phone-PutLookOn's.
import { Fragment } from 'react'
import { Icon } from '@/design/icon'
import { cx } from '@/design/cx'
import { useElementSize } from '@/lib/use-element-size'
import { besideZone, type StageBox } from '../zone-shape'

export interface PreviewWords {
  /** The look previewed, and the zone it's previewed on, by name. */
  look: string
  zone: string
  /** The looks the zone's lights still run (labels.ts's looksOn()). */
  running: readonly string[]
}

/** "<A>", "<A> and <B>": serif italic, at the size Live-PutLookOn's card draws a look's name. */
function Looks({ names }: { names: readonly string[] }) {
  return names.map((name, index) => (
    <Fragment key={name}>
      {index === 0 ? '' : index === names.length - 1 ? ' and ' : ', '}
      <span className="font-serif text-[14px] text-text italic">{name}</span>
    </Fragment>
  ))
}

/**
 * Live-PutLookOn's card, placed beside the zone once it and the stage it can use are measured (F4 ruling 15). That's the stage, but for its
 * right side where the composer lies over it (`covered`, the narrow layout), whose own width is `--live-panel-w`: measured, as the stage is,
 * rather than read. The room shares the stage's top left corner, so the zone's box is in its coordinates too.
 */
export function PreviewCard({ zoneBox, covered, look, zone, running }: PreviewWords & { zoneBox: StageBox; covered: boolean }) {
  const [roomRef, room] = useElementSize<HTMLDivElement>()
  const [ref, card] = useElementSize<HTMLDivElement>()
  const [left, top] = besideZone(zoneBox, room, card)
  return (
    <div ref={roomRef} data-preview-room className={cx('pointer-events-none absolute inset-y-0 left-0', covered ? 'right-(--live-panel-w)' : 'right-0')}>
      <div ref={ref} data-preview-card className="absolute" style={{ left, top, visibility: card.width === 0 || room.width === 0 ? 'hidden' : undefined }}>
        <div className="flex w-59 flex-col gap-1 rounded-tile border border-text bg-bg/88 px-3 py-2.5">
          <span className="flex items-center gap-1.5 text-label font-bold tracking-[0.08em] text-text uppercase">
            <Icon name="eye" size={13} />
            Preview on screen
          </span>
          <p className="text-data leading-[1.4] text-text-2">
            {look} on {zone}.{' '}
            {running.length === 0 ? (
              'The lights are as they were.'
            ) : (
              <>
                The lights are still running <Looks names={running} />.
              </>
            )}
          </p>
        </div>
      </div>
    </div>
  )
}

/** Phone-PutLookOn's tag, top left on the stage. */
export function PreviewTag() {
  return (
    <span className="pointer-events-none absolute top-1.5 left-4 inline-flex h-7 items-center gap-1.5 rounded-pill border border-text bg-bg/88 px-2.5 text-label font-bold tracking-[0.06em] text-text uppercase">
      <Icon name="eye" size={13} />
      Preview on screen · lights unchanged
    </span>
  )
}
