// §8.2 Put a look on (desktop; Live-PutLookOn): the composer takes the Running panel's place and the
// stage goes into `compose` mode. Where: the zone chips along the top of the stage (ComposerWhere). What:
// the search, the category chips and the LookTile grid, where choosing a tile previews its look on the
// stage at once. How: the transition, the consequence line, Cancel and Start <Look>. Keyboard (F4
// ruling 12): the arrows move through the tiles, previewing each, and Enter starts the look previewed;
// the page's L and Esc are useComposerKeys()'s.
import { useRef } from 'react'
import { Button, IconButton } from '@/design/button'
import { cx } from '@/design/cx'
import { Icon } from '@/design/icon'
import { Select } from '@/design/select'
import { ConsequenceText } from './consequence-text'
import { LookTile } from './look-tile'
import { CATEGORIES } from './model'
import { revealKeyboardFocus } from './reveal-focus'
import { useComposeChoice, useRunning } from './use-composer'
import { useComposerView, type LookSteps } from './use-composer-view'
import { ZonePicker } from './zone-picker'

/** Live-PutLookOn's grid: two tiles a row, which Up and Down move by. */
const COLUMNS = 2
const GRID_STEPS: LookSteps = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -COLUMNS, ArrowDown: COLUMNS }

/**
 * §8.2 "Where": the zone chips along the top of the stage, under preview only's label when it shows. `narrow` is the layout where the
 * composer lies over the stage's right side (§4.4): the chips stop short of it, by its width and the margin they keep from the stage's edge.
 */
export function ComposerWhere({ narrow = false }: { narrow?: boolean }) {
  const { zones, zone, locked, choose } = useComposeChoice()
  const running = useRunning()
  if (zones === undefined || zone === undefined) return null
  return (
    <div
      className={cx(
        'absolute top-[calc(--spacing(4)+var(--stage-top-shift,0px))] left-5 z-10',
        narrow ? 'right-[calc(var(--live-panel-w)+--spacing(5))]' : 'right-5',
      )}
    >
      <ZonePicker zones={zones} running={running} selected={zone.id} locked={locked} onSelect={choose} variant="desktop" />
    </div>
  )
}

export function ComposerPanel({ className }: { className?: string }) {
  const grid = useRef<HTMLDivElement>(null)
  const view = useComposerView(GRID_STEPS, grid)
  const { looks, zone, look, consequence: said } = view

  return (
    <aside aria-label="Put a look on" className={cx('flex min-h-0 flex-col border-l border-line-soft bg-panel', className)}>
      <div className="flex items-center justify-between pt-4 pr-4 pb-2.5 pl-5">
        <h2 className="text-section font-semibold">
          Put a look on{zone !== undefined && <span className="font-medium text-text-3"> {zone.name}</span>}
        </h2>
        <IconButton icon="x" label="Close" className="touch-target" onClick={view.close} />
      </div>
      {zone !== undefined && looks !== undefined && (
        <>
          <div className="flex flex-col gap-2.5 px-5 pb-3">
            {/* 38 px: the render's 36 px and its border, as its HTML sets no box-sizing; the chips and tiles are drawn 2 px lower for it.
                The whole face is the input's label, so a click on its icon or its padding focuses the input too, and touch-target
                grows it to the touch minimum. */}
            <label className="flex h-9.5 cursor-text items-center gap-2 rounded-control border border-line bg-control px-3 touch-target focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-text">
              <Icon name="search" size={15} className="text-text-3" />
              <span className="sr-only">Search looks</span>
              <input
                type="search"
                value={view.query}
                placeholder={`Search ${looks.length} looks`}
                className="min-w-0 grow bg-transparent text-size-control text-text outline-none placeholder:text-text-3 [&::-webkit-search-cancel-button]:appearance-none"
                onChange={(event) => view.search(event.target.value)}
                onKeyDown={(event) => {
                  // A search's Esc clears it first, and the page's Esc leaves a key handled alone.
                  if (event.key !== 'Escape' || !view.searching) return
                  event.preventDefault()
                  view.search('')
                }}
              />
            </label>
            {/* The row clips, as drawn: its last chip is cut at the panel's edge, as in the render. That would cut a focused chip's ring
                (2 px and its 2 px offset, tokens.css) and the hit area touch-target grows, so it pads by their reach on its left, top
                and bottom and pulls back by as much, moving nothing (as ZonePicker's phone row does), and pads its end by it too, so the
                last chip can be scrolled in with its ring whole; scroll-px-1 leaves a chip that is scrolled to that room too. A chip the
                keyboard focuses is scrolled in (revealKeyboardFocus), as the browser leaves a chip that is mostly in view cut. Nothing
                but that scroll moves a clipped row, and no wheel or touch undoes it, so it goes back to its start when focus leaves. */}
            <div
              role="group"
              aria-label="Categories"
              className="-my-2 -ml-1 flex scroll-px-1 gap-1.5 overflow-hidden py-2 pr-1 pl-1"
              onFocus={revealKeyboardFocus}
              onBlur={(event) => {
                if (!event.currentTarget.contains(event.relatedTarget)) event.currentTarget.scrollLeft = 0
              }}
            >
              {CATEGORIES.map(({ id, label }) => {
                const on = !view.searching && id === view.category
                return (
                  <button
                    key={id}
                    type="button"
                    aria-pressed={on}
                    className={cx(
                      'h-7 rounded-pill border px-2.25 text-meta font-semibold whitespace-nowrap touch-target',
                      on ? 'border-text bg-control-hover text-text' : 'border-line text-text-2',
                    )}
                    onClick={() => view.chooseCategory(id)}
                  >
                    {label}
                  </button>
                )
              })}
            </div>
          </div>
          {/* scroll-py-1: a tile the browser scrolls to when the arrows move the focus lands with the room its focus ring needs (4 px, tokens.css),
              which the scroller would clip at its edge. The phone's list does the same. */}
          <div className="min-h-0 grow scroll-py-1 overflow-y-auto px-5 pt-1 pb-4">
            {view.shown.length === 0 ? (
              <p className="text-meta text-text-3">
                {view.searching
                  ? `No looks match “${view.query.trim()}”.`
                  : `No ${CATEGORIES.find((each) => each.id === view.category)?.label.toLowerCase()} looks yet.`}
              </p>
            ) : (
              <div
                ref={grid}
                role="group"
                aria-label="Looks"
                className="grid gap-x-3 gap-y-4"
                style={{ gridTemplateColumns: `repeat(${COLUMNS}, minmax(0, 1fr))` }}
                onKeyDown={view.onListKey}
              >
                {view.shown.map((each) => (
                  <LookTile
                    key={each.id}
                    look={each}
                    selected={each.id === look?.id}
                    here={each.id === view.here?.lookId}
                    missing={view.missing(each)}
                    tabbable={each.id === view.tabbable}
                    onSelect={() => view.pick(each.id)}
                  />
                ))}
              </div>
            )}
          </div>
          <div className="flex flex-col gap-3 border-t border-line-soft px-5 pt-3.5 pb-5">
            <div className="flex items-center justify-between gap-2.5">
              <span className="text-data text-text-2">Transition</span>
              <Select
                label="Transition"
                value={view.transition}
                items={Object.fromEntries(view.transitions.map((choice) => [choice.key, choice.label]))}
                onValueChange={view.chooseTransition}
                className="w-42.5 touch-target"
              />
            </div>
            {said !== null && (
              <p data-consequence className="flex items-start gap-2 text-meta text-text-3">
                <Icon name="layers" size={15} />
                <span>
                  {/* Live-PutLookOn sets the look's name in serif at 14 px, a size tokens.css has no token for. */}
                  <ConsequenceText parts={said.parts} lookClassName="font-serif text-[14px] text-text italic" />
                </span>
              </p>
            )}
            <div className="flex gap-2.5">
              <Button size="lg" onClick={view.close}>
                Cancel
              </Button>
              <Button variant="primary" size="lg" icon="play" className="grow" disabled={view.blocked || view.starting} onClick={view.startChosen}>
                {look === undefined ? 'Start' : `Start ${look.name}`}
              </Button>
            </div>
          </div>
        </>
      )}
    </aside>
  )
}
