// §8.10 Put a look on (Phone-PutLookOn): the composer as a sheet under the focused stage, which shows
// the preview with its tag. Where: the zone buttons in a row that scrolls. What: the category chips and
// the look rows (there's no search on the phone). Then the short consequence beside the transition, and
// Start <Look> on <Zone>. The sheet is part of the page, not a dialog: the stage above stays live, and a
// room tapped there chooses its zone. Its title is the page's h1, since the header that holds one steps
// aside (a focused task). Keyboard (F4 ruling 12): Up and Down move through the rows, previewing each,
// and Enter starts the look previewed; the page's Esc closes it. Every way out is view.close (F4 ruling 13).
// Sizes: the render's, from its HTML. The page gives the sheet the screen's height under the stage, so
// only the look list, which takes what the rest leaves, scrolls; but never less than one whole row, with its
// padding on top (`box-content`), so a screen too short for that scrolls the sheet too, and every look and
// Start can be reached. The stage keeps its aspect, so how short depends on the width: under about 670 px
// at 390 wide, 660 at 375 and 700 at 430. <main> never scrolls. The two rows that scroll on their own
// (the chips, the looks) pad by the reach of a focus ring (tokens.css's outline and offset, 4 px) and pull
// back by as much, so a ring is never cut at the row's edge and nothing moves; ZonePicker's row does too.
import { useId, useRef } from 'react'
import { Button } from '@/design/button'
import { cx } from '@/design/cx'
import { Icon } from '@/design/icon'
import { Grabber } from '@/design/overlays'
import { Select } from '@/design/select'
import { ConsequenceText } from './consequence-text'
import { LookRow, ROW_HEIGHT } from './look-row'
import { CATEGORIES } from './model'
import { revealKeyboardFocus } from './reveal-focus'
import { useComposerView, type LookSteps } from './use-composer-view'
import { ZonePicker } from './zone-picker'

/** Phone-PutLookOn's list: one look a row. */
const ROW_STEPS: LookSteps = { ArrowUp: -1, ArrowDown: 1 }

export function ComposerSheet({ className }: { className?: string }) {
  const rows = useRef<HTMLDivElement>(null)
  const title = useId()
  const view = useComposerView(ROW_STEPS, rows)
  const { zones, looks, zone, look, running, consequence: said } = view

  return (
    <section aria-labelledby={title} className={cx('flex flex-col overflow-y-auto rounded-t-sheet border-t border-line bg-panel', className)}>
      <Grabber className="mt-2" />
      <div className="flex items-center justify-between px-4 pt-2">
        <h1 id={title} className="text-title font-semibold">Put a look on</h1>
        <button type="button" aria-label="Close" className="inline-flex size-11 shrink-0 items-center justify-center text-text-2" onClick={view.close}>
          <Icon name="x" size={20} />
        </button>
      </div>
      {zones !== undefined && looks !== undefined && zone !== undefined && (
        <>
          <div className="px-4">
            <ZonePicker zones={zones} running={running} selected={zone.id} locked={view.locked} onSelect={view.choose} variant="phone" />
          </div>
          <div className="flex flex-col gap-2 px-4 pt-3.5">
            <span className="label-caps text-text-3">What</span>
            {/* The chips are drawn smaller than --touch-min; the row's padding keeps their grown hit areas and focus rings in it, and a
                chip the keyboard focuses is scrolled wholly in (revealKeyboardFocus). */}
            <div role="group" aria-label="Categories" className="-m-1 flex scroll-px-1 gap-1.5 overflow-x-auto p-1" onFocus={revealKeyboardFocus}>
              {CATEGORIES.map(({ id, label }) => (
                <button
                  key={id}
                  type="button"
                  aria-pressed={id === view.category}
                  className={cx(
                    'h-9 shrink-0 rounded-pill border px-3.5 text-data font-semibold whitespace-nowrap touch-target',
                    id === view.category ? 'border-text bg-control-hover text-text' : 'border-line text-text-2',
                  )}
                  onClick={() => view.chooseCategory(id)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div
            ref={rows}
            role="group"
            aria-label="Looks"
            className="box-content flex grow scroll-py-1 flex-col gap-0.5 overflow-y-auto px-2 pt-2 pb-1"
            style={{ minHeight: ROW_HEIGHT }}
            onKeyDown={view.onListKey}
          >
            {view.shown.length === 0 ? (
              <p className="px-2 text-meta text-text-3">{`No ${CATEGORIES.find((each) => each.id === view.category)?.label.toLowerCase()} looks yet.`}</p>
            ) : (
              view.shown.map((each) => (
                <LookRow
                  key={each.id}
                  look={each}
                  selected={each.id === look?.id}
                  here={each.id === view.here?.lookId}
                  missing={view.missing(each)}
                  tabbable={each.id === view.tabbable}
                  onSelect={() => view.pick(each.id)}
                />
              ))
            )}
          </div>
          <div className="flex flex-col gap-2.5 border-t border-line-soft px-4 pt-3 pb-7.5">
            <div className="flex items-center justify-between gap-2.5 text-data text-text-3">
              {/* Phone-PutLookOn sets the look's name in serif at 15 px, which is --text-section. */}
              <span data-consequence>{said !== null && <ConsequenceText parts={said.short} lookClassName="font-serif text-section text-text italic" />}</span>
              <Select
                label="Transition"
                value={view.transition}
                items={Object.fromEntries(view.transitions.map((choice) => [choice.key, choice.label]))}
                onValueChange={view.chooseTransition}
                className="h-9! w-37.5 shrink-0 touch-target"
              />
            </div>
            <Button variant="primary" size="cta" icon="play" disabled={view.blocked || view.starting} onClick={view.startChosen}>
              <span className="min-w-0 truncate">{look === undefined ? 'Start' : `Start ${look.name} on ${zone.name}`}</span>
            </Button>
          </div>
        </>
      )}
    </section>
  )
}
