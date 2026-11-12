// The Looks library's filter bar (§8.4, Looks.png): a search over looks, layers and inputs, a tab for All, Starred, each category and Mine with
// its count, the "Only ready now" switch and New look. It holds nothing: the page keeps the three choices (F5 rulings 10 to 12) and the counts
// (ruling 9) and passes them in, as the composer's panel does for its own search and chips.
//
// Below the phone breakpoint the bar wraps and the search takes the whole of its row (ruling 1).
import { ButtonLink } from '@/design/button'
import { cx } from '@/design/cx'
import { Icon } from '@/design/icon'
import { Switch } from '@/design/switch'
import { LIBRARY_TABS, type LibraryTab } from './library-model'

export interface LibraryFiltersProps {
  tab: LibraryTab
  /** Each tab's count (`tabCounts()`); the search and the switch change none of them. */
  counts: Record<LibraryTab, number>
  query: string
  readyOnly: boolean
  onTab: (tab: LibraryTab) => void
  onQuery: (query: string) => void
  onReadyOnly: (on: boolean) => void
}

export function LibraryFilters({ tab, counts, query, readyOnly, onTab, onQuery, onReadyOnly }: LibraryFiltersProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div className="flex flex-wrap items-center gap-3 max-md:w-full">
        {/* The composer's search face: the whole of it is the input's label, so a click on its icon or its padding focuses the input too,
            and its ring is the label's, as the input draws none. The render's box is 280 by 36 with its border inside (`box-sizing`
            is border-box here, as it is in Looks.html's search). `relative` at every width is the positioned parent the sr-only name needs
            inside <main>'s scroller (max-md:touch-target sets it on the phone alone), which also grows the box to the touch minimum. */}
        <label className="relative flex h-9 w-70 cursor-text items-center gap-2 rounded-control border border-line bg-control px-3 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-text max-md:w-full max-md:touch-target">
          <Icon name="search" size={15} className="text-text-3" />
          <span className="sr-only">Search looks</span>
          <input
            type="search"
            value={query}
            placeholder="Search looks, layers, inputs"
            className="min-w-0 grow bg-transparent text-size-control text-text outline-none placeholder:text-text-3 [&::-webkit-search-cancel-button]:appearance-none"
            onChange={(event) => onQuery(event.target.value)}
            onKeyDown={(event) => {
              // A search's Esc clears it first, and the page's Esc leaves a key handled alone: a box of spaces has nothing to clear (the
              // composer's `searching` is `query.trim() !== ''` too).
              if (event.key !== 'Escape' || query.trim() === '') return
              event.preventDefault()
              onQuery('')
            }}
          />
        </label>
        <div role="group" aria-label="Categories" className="flex flex-wrap gap-1.5">
          {LIBRARY_TABS.map(({ id, label }) => {
            const on = id === tab
            return (
              <button
                key={id}
                type="button"
                aria-pressed={on}
                className={cx(
                  'inline-flex h-8 items-center gap-1.5 rounded-pill border px-3 text-size-control font-semibold max-md:touch-target',
                  on ? 'border-text bg-control-hover text-text' : 'border-line text-text-2',
                )}
                onClick={() => onTab(id)}
              >
                {label}
                {/* Looks.png draws every count in text-3, which is under §14's contrast on the chosen tab's control-hover fill (F4 ruling 19). */}
                <span className={cx('font-mono text-label', on ? 'text-text-2' : 'text-text-3')}>{counts[id]}</span>
              </button>
            )
          })}
        </div>
      </div>
      <div className="flex items-center gap-4">
        <Switch label="Only ready now" checked={readyOnly} onCheckedChange={onReadyOnly} className="max-md:touch-target" />
        <ButtonLink icon="plus" to="/looks/new">
          New look
        </ButtonLink>
      </div>
    </div>
  )
}
