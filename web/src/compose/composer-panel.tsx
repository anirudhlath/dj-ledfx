// §8.2 Put a look on (desktop; Live-PutLookOn): the composer takes the Running panel's place and the
// stage goes into `compose` mode. Where: the zone chips along the top of the stage (ComposerWhere). What:
// the search, the category chips and the LookTile grid, where choosing a tile previews its look on the
// stage at once. How: the transition, the consequence line, Cancel and Start <Look>. Keyboard (F4
// ruling 12): the arrows move through the tiles, previewing each, and Enter starts the look previewed;
// the page's L and Esc are useComposerKeys()'s.
import { useId, useRef, type CSSProperties } from 'react'
import { Button, IconButton } from '@/design/button'
import { cx } from '@/design/cx'
import { Icon } from '@/design/icon'
import { Select } from '@/design/select'
import { ConsequenceText } from './consequence-text'
import { LookTile } from './look-tile'
import { CATEGORIES } from './model'
import { useComposeChoice, useRunning } from './use-composer'
import { useComposerView, type LookSteps } from './use-composer-view'
import { ZonePicker } from './zone-picker'

/** Live-PutLookOn's grid: two tiles a row, so Up and Down move by two. */
const GRID_STEPS: LookSteps = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -2, ArrowDown: 2 }

/** §8.2 "Where": the zone chips along the top of the stage, under preview only's label when it shows. */
export function ComposerWhere({ style }: { style?: CSSProperties }) {
  const { zones, zone, locked, choose } = useComposeChoice()
  const running = useRunning()
  if (zones === undefined || zone === undefined) return null
  return (
    <div className="absolute top-[calc(1rem+var(--stage-top-shift,0px))] right-5 left-5 z-10" style={style}>
      <ZonePicker zones={zones} running={running} selected={zone.id} locked={locked} onSelect={choose} variant="desktop" />
    </div>
  )
}

export function ComposerPanel({ className }: { className?: string }) {
  const grid = useRef<HTMLDivElement>(null)
  const view = useComposerView(GRID_STEPS, grid)
  const { looks, zone, look, consequence: said } = view
  const searchId = useId()

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
            {/* 38 px: the render's 36 px and its border, as its HTML sets no box-sizing; the chips and tiles are drawn 2 px lower for it. */}
            <div className="flex h-9.5 items-center gap-2 rounded-control border border-line bg-control px-3 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-text">
              <Icon name="search" size={15} className="text-text-3" />
              <label htmlFor={searchId} className="sr-only">
                Search looks
              </label>
              <input
                id={searchId}
                type="search"
                value={view.query}
                placeholder={`Search ${looks.length} looks`}
                className="min-w-0 grow bg-transparent text-size-control text-text outline-none placeholder:text-text-3"
                onChange={(event) => view.search(event.target.value)}
                onKeyDown={(event) => {
                  // A search's Esc clears it first, and the page's Esc leaves a key handled alone.
                  if (event.key !== 'Escape' || !view.searching) return
                  event.preventDefault()
                  view.search('')
                }}
              />
            </div>
            {/* The row clips, as drawn, which would cut a focused chip's ring (2 px and its 2 px offset, tokens.css) and the hit area
                touch-target grows: it pads by their reach and pulls back by as much, moving nothing (as ZonePicker's phone row does). */}
            <div role="group" aria-label="Categories" className="-mx-1 -my-2 flex gap-1.5 overflow-hidden px-1 py-2">
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
          <div className="min-h-0 grow overflow-y-auto px-5 pt-1 pb-4">
            {view.shown.length === 0 ? (
              <p className="text-meta text-text-3">
                {view.searching
                  ? `No looks match “${view.query.trim()}”.`
                  : `No ${CATEGORIES.find((each) => each.id === view.category)?.label.toLowerCase()} looks yet.`}
              </p>
            ) : (
              <div ref={grid} role="group" aria-label="Looks" className="grid grid-cols-2 gap-x-3 gap-y-4" onKeyDown={view.onListKey}>
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
