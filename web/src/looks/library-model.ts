// The Looks library's model (§8.4, §6.4 LookCard; F5 rulings 9 to 14, 18 and 21): the tabs and their counts, what a search finds, the
// sections the grid is drawn in, each card's input pills, where a look runs, whose variation it is, and the words for an empty grid.
// Pure: the page gathers its data (REST, the live store), and tests build it from a scenario. The words are the spec's and Looks.html's.
import type { Id, InputKind, Inputs, Look, RunningZone, Zone } from '@/api/contract'
import { missingInputs, type MissingInput } from '@/compose/model'
import type { IconName } from '@/design/icons'
import { formatList } from '@/lib/format'
import { INPUTS } from '@/zones/zone-view'
import { LIBRARY, LOOK_CATEGORIES } from './looks-render'

/** A tab of §8.4's filter bar: every built-in look, the starred ones, a category, or the looks the owner saved. */
export type LibraryTab = 'all' | 'starred' | Look['category'] | 'mine'

/** "All, Starred, Ambient, Tempo, Audio, Home, Firmware, Mine" (§8.4, Looks.png), in its order. */
export const LIBRARY_TABS: readonly { id: LibraryTab; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'starred', label: 'Starred' },
  ...LOOK_CATEGORIES.map((category) => ({ id: category.id, label: category.name })),
  { id: 'mine', label: 'Mine' },
]

/** The tab `?cat=` names (§4.3); one the app doesn't know, or none, is All (F5 ruling 10). */
export function readTab(cat: string | null): LibraryTab {
  return LIBRARY_TABS.find((tab) => tab.id === cat)?.id ?? 'all'
}

/**
 * Each tab's count, as Looks.png has them (F5 ruling 9): All the built-in looks, a category its built-ins, Starred every starred look
 * (a saved one too) and Mine the saved ones. The search and the switch change none of them.
 */
export function tabCounts(looks: readonly Look[]): Record<LibraryTab, number> {
  const builtIns = looks.filter((look) => look.builtIn)
  return {
    all: builtIns.length,
    starred: looks.filter((look) => look.starred).length,
    ...(Object.fromEntries(
      LOOK_CATEGORIES.map(({ id }) => [id, builtIns.filter((look) => look.category === id).length]),
    ) as Record<Look['category'], number>),
    mine: looks.length - builtIns.length,
  }
}

/** The inputs a look lists: what it needs, then what it uses, each once, in the look's own order. */
const inputsOf = (look: Look): InputKind[] => [...new Set([...(look.needs ?? []), ...(look.uses ?? [])])]

/** Looks.html writes Home Assistant "HA" on a card, and INPUTS' label everywhere else. */
const cardName = (kind: InputKind): string => (kind === 'home-assistant' ? 'HA' : INPUTS[kind].label)

/**
 * The looks that match a search (F5 ruling 11), ignoring case and the words' edges: a look's name, its layers' names and its inputs'
 * names, the card's and INPUTS' labels alike (Home Assistant is "HA" on a card). Not its description. No words match every look.
 */
export function searchLooks(looks: readonly Look[], query: string): Look[] {
  const words = query.trim().toLowerCase()
  if (words === '') return [...looks]
  const matches = (text: string) => text.toLowerCase().includes(words)
  return looks.filter(
    (look) =>
      matches(look.name) ||
      (look.layers ?? []).some((layer) => matches(layer.name)) ||
      inputsOf(look).some((kind) => matches(cardName(kind)) || matches(INPUTS[kind].label)),
  )
}

/** What the grid shows (F5 rulings 10 and 12): the tab, the search and "Only ready now" with the inputs it judges by. */
export interface LibraryFilter {
  tab: LibraryTab
  query: string
  readyOnly: boolean
  inputs: Pick<Inputs, 'music' | 'homeAssistant'> | null
}

/** A section of the grid. Firmware and Mine are the last row's, with no count, side by side (F5 ruling 20). */
export interface LibrarySection {
  id: Look['category'] | 'mine'
  name: string
  blurb: string
  looks: Look[]
  /** Whether the heading says how many looks it holds. */
  counted: boolean
  /** Whether it shares the last row with the other. */
  lastRow: boolean
}

const LAST_ROW: readonly LibrarySection['id'][] = ['firmware', 'mine']

/** The looks a tab holds, before the search and the switch (F5 ruling 10): a saved look is in Starred and Mine, and in no category. */
function tabLooks(looks: readonly Look[], tab: LibraryTab): Look[] {
  switch (tab) {
    case 'all':
      return [...looks]
    case 'starred':
      return looks.filter((look) => look.starred)
    case 'mine':
      return looks.filter((look) => !look.builtIn)
    default:
      return looks.filter((look) => look.builtIn && look.category === tab)
  }
}

/**
 * The sections the grid draws (F5 ruling 10): the tab, the search and the switch pick the looks, which are grouped into looks.json's
 * categories in its order, then Mine, a section with no look left out. Starred keeps the category sections, a category tab is its one
 * section, and a saved look is only ever in Mine, whatever its category.
 */
export function librarySections(looks: readonly Look[], filter: LibraryFilter): LibrarySection[] {
  const inTab = tabLooks(looks, filter.tab)
  const ready = filter.readyOnly ? inTab.filter((look) => missingInputs(look, filter.inputs).length === 0) : inTab
  const shown = searchLooks(ready, filter.query)
  const section = (id: LibrarySection['id'], name: string, blurb: string, inside: Look[]): LibrarySection => ({
    id,
    name,
    blurb,
    looks: inside,
    counted: !LAST_ROW.includes(id),
    lastRow: LAST_ROW.includes(id),
  })
  return [
    ...LOOK_CATEGORIES.map(({ id, name, blurb }) => section(id, name, blurb, shown.filter((look) => look.builtIn && look.category === id))),
    section('mine', 'Mine', LIBRARY.mineBlurb, shown.filter((look) => !look.builtIn)),
  ].filter((each) => each.looks.length > 0)
}

/** One of a card's input pills (§6.4 LookCard): `INPUTS`' icon and Looks.html's name, in signal when it's missing. */
export interface CardInput {
  kind: InputKind
  name: string
  icon: IconName
  missing: boolean
}

/**
 * A card's input pills (F5 ruling 18): the inputs the look needs, then those it uses, each once, in the look's own order. `missing` is
 * what the page's `missingInputs()` found for the look, so a pill the server can't judge is never in signal.
 */
export function cardInputs(look: Look, missing: readonly MissingInput[]): CardInput[] {
  const absent = new Set<InputKind>(missing)
  return inputsOf(look).map((kind) => ({ kind, name: cardName(kind), icon: INPUTS[kind].icon, missing: absent.has(kind) }))
}

/** The zones a look runs on (F5 ruling 13), named from /api/zones in /api/running's order; a zone /api/zones doesn't name is left out. */
export function runningOn(lookId: Id, running: readonly RunningZone[], zones: readonly Zone[]): string[] {
  return running
    .filter((each) => each.lookId === lookId)
    .flatMap((each) => zones.find((zone) => zone.id === each.zoneId)?.name ?? [])
}

/**
 * The running pill's words (F5 ruling 13): the first zone and how many more are beside it, and for a screen reader all of them, "Running
 * on A and B"; none for a look that runs nowhere.
 */
export function runningPill(names: readonly string[]): { shown: string; spoken: string } | null {
  if (names.length === 0) return null
  return {
    shown: names.length === 1 ? names[0] : `${names[0]} +${names.length - 1}`,
    spoken: `Running on ${formatList(names)}`,
  }
}

/** The look a saved variation was made from (F5 ruling 14); none for a look that isn't one, or whose parent is gone. */
export function parentName(look: Look, looks: readonly Look[]): string | null {
  if (look.derivedFrom == null) return null
  return looks.find((each) => each.id === look.derivedFrom)?.name ?? null
}

/** Why the grid is empty (F5 ruling 21): the search first, then the switch, then the tab. */
export function emptyText(filter: Pick<LibraryFilter, 'tab' | 'query' | 'readyOnly'>): string {
  const query = filter.query.trim()
  if (query !== '') return `No looks match “${query}”.`
  if (filter.readyOnly) return 'No looks are ready now.'
  switch (filter.tab) {
    case 'all':
      return 'No looks yet.'
    case 'starred':
      return 'No starred looks yet.'
    case 'mine':
      return 'No saved looks yet.'
    default:
      return `No ${filter.tab} looks yet.`
  }
}

/** The header's context line (F5 ruling 9): "29 looks · 3 running", the built-in looks and the zones that run one. */
export const looksContext = (looks: readonly Look[], running: readonly RunningZone[]): string =>
  `${tabCounts(looks).all} looks · ${running.length} running`
