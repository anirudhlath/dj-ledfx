// /looks (§4.3, §8.4, Looks.png): the library. A filter bar (search, tabs with their counts, "Only ready now", New look), then a section per
// category with its name in serif, its count and its blurb over a grid of `LookCard`s; Firmware and Mine share the last row. The tab and the
// search are the URL's (`?cat=`, `?q=`, F5 ruling 10), so a reload and Back work; the switch is the page's (ruling 12). The page gathers the
// data, REST's looks and zones and the live store's running zones and inputs, and `looks/library-model.ts` decides what to draw of it.
//
// Below the phone breakpoint the page is the desktop's in two columns (ruling 1); Phone-Looks.png is F9's.
import { useQuery } from '@tanstack/react-query'
import { useState, type CSSProperties, type ReactNode } from 'react'
import { useLocation, useNavigationType, useSearchParams } from 'react-router'
import { failureText } from '@/api/actions'
import type { Look, Zone } from '@/api/contract'
import { useLive } from '@/api/live-store'
import { queries } from '@/api/queries'
import { missingInputs } from '@/compose/model'
import { useInputsRead, useRunning } from '@/compose/use-composer'
import { Button } from '@/design/button'
import { cx } from '@/design/cx'
import { LIVE_SPEC } from '@/design/live-numbers'
import { LibraryFilters } from '@/looks/library-filters'
import {
  emptyText,
  librarySections,
  looksContext,
  parentName,
  readTab,
  runningOn,
  switchHidesLooks,
  tabCounts,
  type LibraryFilter,
  type LibrarySection,
  type LibraryTab,
} from '@/looks/library-model'
import { LookCard } from '@/looks/look-card'
import { EmptyState } from './empty-state'

const NO_ZONES: readonly Zone[] = []

/** What the search box's writes to the URL carry in their location state, so that their echoes can be told from anyone else's replace. */
const BOX_WRITE = { writtenBy: 'library-search-box' }
const isBoxWrite = (state: unknown): boolean => typeof state === 'object' && state !== null && 'writtenBy' in state && state.writtenBy === BOX_WRITE.writtenBy

/** The URL for a tab and a search: `cat` is left out for All and `q` for no search, so the two are always in this order. */
function libraryParams(tab: LibraryTab, query: string): URLSearchParams {
  const params = new URLSearchParams()
  if (tab !== 'all') params.set('cat', tab)
  if (query !== '') params.set('q', query)
  return params
}

/**
 * The tab and the search, kept in the URL (§4.3). A tab is a step in the history and the search replaces its entry, so Back leaves the page
 * and doesn't walk back through the keys.
 *
 * The search box shows the text typed, not the URL's. The router's updates are transitions, and a controlled input that waits for one is put
 * back to its old text after every key: its caret jumps to the end, and typed fast it loses characters. So the box and the filter follow the
 * typing, the URL follows them, and a URL that changes under the box is taken, whatever moved it: Back, a link, or anyone's replace. Only the
 * box's own writes are not: each carries a mark in its location state, and a replace with that mark is the box's text coming round, which
 * may be after more has been typed. (Back to an entry the box wrote is a POP, and is taken.)
 */
function useLibraryUrl() {
  const [params, setParams] = useSearchParams()
  const navigation = useNavigationType()
  const { state } = useLocation()
  const tab = readTab(params.get('cat'))
  const urlQuery = params.get('q') ?? ''
  const [query, setQuery] = useState(urlQuery)
  const [seen, setSeen] = useState(urlQuery)
  if (urlQuery !== seen) {
    // React's way to adjust state to a prop.
    setSeen(urlQuery)
    if (navigation !== 'REPLACE' || !isBoxWrite(state)) setQuery(urlQuery)
  }
  return {
    tab,
    query,
    chooseTab: (next: LibraryTab) => setParams(libraryParams(next, query)),
    search: (next: string) => {
      setQuery(next)
      setParams(libraryParams(tab, next), { replace: true, state: BOX_WRITE })
    },
  }
}

/** The header's "29 looks · 3 running" (F5 ruling 9), drawn once the looks and the zones that run are known: before that it says nothing. */
export function LooksContext() {
  const looks = useQuery(queries.looks()).data
  const running = useRunning()
  const heard = useLive((state) => state.running !== null)
  return looks !== undefined && heard ? looksContext(looks, running) : null
}

export function LooksPage() {
  const looksQuery = useQuery(queries.looks())
  const looks = looksQuery.data
  const zones = useQuery(queries.zones()).data ?? NO_ZONES
  const running = useRunning()
  const inputs = useInputsRead()
  const { tab, query, chooseTab, search } = useLibraryUrl()
  const [readyOnly, setReadyOnly] = useState(false)

  if (looks === undefined) {
    // Nothing yet shows nothing: a tab's count of 0 would be a claim.
    if (!looksQuery.isError) return null
    return (
      <EmptyState
        title="No looks to show"
        action={
          <Button variant="outline" icon="refresh" disabled={looksQuery.isFetching} onClick={() => void looksQuery.refetch()}>
            Try again
          </Button>
        }
      >
        {failureText('load the looks', looksQuery.error)}
      </EmptyState>
    )
  }

  const filter: LibraryFilter = { tab, query, readyOnly, inputs }
  const sections = librarySections(looks, filter)
  const card = (look: Look) => (
    <LookCard look={look} running={runningOn(look.id, running, zones)} parent={parentName(look, looks)} missing={missingInputs(look, inputs)} />
  )
  const grids = sections.filter((section) => !section.lastRow)
  const lastRow = sections.filter((section) => section.lastRow)
  // The page frames itself: <main> also holds Live's full-bleed stage, so it can't. Looks.html's main is the content width between 40 px
  // gutters, with 24 px above and 40 below; the phone's gutter is the other phone pages' 16 px.
  return (
    <div className="px-4 pt-6 pb-10 md:px-10">
      <div className="mx-auto flex w-full max-w-(--content-max-w) flex-col gap-10">
        <LibraryFilters
          tab={tab}
          counts={tabCounts(looks)}
          query={query}
          readyOnly={readyOnly}
          onTab={chooseTab}
          onQuery={search}
          onReadyOnly={setReadyOnly}
        />
        {sections.length === 0 && <p className="py-16 text-center text-body text-text-2">{emptyText(filter, switchHidesLooks(looks, filter))}</p>}
        {grids.map((section) => (
          <Section key={section.id} section={section} card={card} />
        ))}
        {/* Looks.html's last row: Firmware and Mine side by side. On the phone they are two sections like the others. */}
        {lastRow.length > 0 && (
          <div className="flex flex-col gap-10 md:flex-row md:flex-wrap md:gap-12">
            {lastRow.map((section) => (
              <Section key={section.id} section={section} card={card} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

interface SectionProps {
  section: LibrarySection
  card: (look: Look) => ReactNode
}

/**
 * A section (§8.4): its name in serif at the spec's size, how many looks it holds where it says, and its blurb, over the cards. A grid
 * section fills the content width in columns of at least the card's width (F5 ruling 20: six at the design's 1288 px, two on the phone).
 * The last row's sections keep the card's width, as Looks.html draws them, and wrap when they don't fit.
 */
function Section({ section, card }: SectionProps) {
  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-baseline gap-3">
        <h2 className="font-serif" style={{ fontSize: LIVE_SPEC.looksPage.sectionNamePx }}>
          {section.name}
        </h2>
        {section.counted && <span className="font-mono text-meta text-text-3">{section.looks.length}</span>}
        <span className="text-size-control text-text-3">{section.blurb}</span>
      </div>
      <div
        className={cx(
          'grid grid-cols-2 gap-x-4 gap-y-7',
          section.lastRow ? 'md:flex md:flex-wrap' : 'md:grid-cols-[repeat(auto-fill,minmax(var(--card-min),1fr))]',
        )}
        style={{ '--card-min': `${LIVE_SPEC.lookCard.px}px` } as CSSProperties}
      >
        {section.looks.map((look) => (
          <div key={look.id} className={cx('min-w-0', section.lastRow && 'md:w-(--card-min)')}>
            {card(look)}
          </div>
        ))}
      </div>
    </section>
  )
}
