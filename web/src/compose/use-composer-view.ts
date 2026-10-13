// What the composer's two faces share (§8.2, §8.10): the desktop panel and the phone's sheet show the
// looks in the server's order (F4 ruling 18), open on the same category (ruling 10), keep a transition
// chosen for the look chosen (ruling 11) and take the same keys (ruling 12): the arrows move through the
// looks by `steps`, choosing each as they go, and Enter on the look chosen starts it. The look chosen,
// else the first, takes the focus as the composer opens. `list` is the face's element that holds the
// looks, each one `[data-look]`.
import { useEffect, useRef, useState, type KeyboardEvent, type RefObject } from 'react'
import type { Id, Look, RunningZone } from '@/api/contract'
import {
  looksShown,
  lookTransition,
  openingCategory,
  runningOn,
  transitionChoices,
  transitionKey,
  type Category,
  type TransitionChoice,
} from './model'
import { useComposer, type Composer } from './use-composer'

/** The element of look `id` among those `list` holds. */
const lookElement = (list: HTMLElement | null, id: Id) =>
  [...(list?.querySelectorAll<HTMLElement>('[data-look]') ?? [])].find((each) => each.dataset.look === id)

/** How far each arrow key moves through the looks. */
export type LookSteps = Partial<Record<string, number>>

export interface ComposerView extends Composer {
  /** What runs on the zone now (F4 ruling 4): its look is the one running here. */
  here: RunningZone | null
  category: Category
  /** Shows a category's looks, ending a search. */
  chooseCategory: (category: Category) => void
  query: string
  search: (query: string) => void
  /** A search is on: it spans every category, so no category is chosen (F4 ruling 10). */
  searching: boolean
  shown: Look[]
  transitions: TransitionChoice[]
  /** The transition chosen, by its key: the look's own until another is chosen for it. */
  transition: string
  chooseTransition: (key: string) => void
  /** Start can't go yet; the consequence line says why. */
  blocked: boolean
  /** The looks' one tab stop: the look chosen, else the first shown. */
  tabbable: Id | undefined
  onListKey: (event: KeyboardEvent<HTMLElement>) => void
  /** Starts the look chosen with the transition chosen. */
  startChosen: () => void
}

export function useComposerView(steps: LookSteps, list: RefObject<HTMLElement | null>): ComposerView {
  const composer = useComposer()
  const { zones, looks, zone, look, running, consequence: said } = composer
  const [category, setCategory] = useState<Category | null>(null)
  const [query, setQuery] = useState('')
  const [chosen, setChosen] = useState<{ lookId: Id | null; key: string } | null>(null)

  const here = zone === undefined || zones === undefined ? null : runningOn(zone, running, zones)
  const shownCategory = category ?? openingCategory(look, looks?.find((each) => each.id === here?.lookId))
  const shown = looks === undefined ? [] : looksShown(looks, shownCategory, query)
  const transitions = transitionChoices(look)
  const key = chosen !== null && chosen.lookId === (look?.id ?? null) ? chosen.key : transitionKey(lookTransition(look))
  const blocked = said?.blocked ?? true
  const tabbable = shown.find((each) => each.id === look?.id)?.id ?? shown[0]?.id
  const startChosen = () => composer.start(transitions.find((choice) => choice.key === key)?.transition ?? lookTransition(look))

  // The look chosen takes the focus once, as the composer opens. Its tile is drawn once the zones have come as well as the looks, in either
  // order, so this tries after every render until the tile is there, and is done only when it has the focus.
  const focused = useRef(false)
  useEffect(() => {
    if (focused.current || tabbable === undefined) return
    const tile = lookElement(list.current, tabbable)
    if (tile === undefined) return
    tile.focus()
    focused.current = true
  })

  const onListKey = (event: KeyboardEvent<HTMLElement>) => {
    const id = event.target instanceof HTMLElement ? event.target.closest<HTMLElement>('[data-look]')?.dataset.look : undefined
    if (id === undefined) return
    if (event.key === 'Enter' && id === look?.id) {
      // Enter on another look chooses it, as a click does.
      event.preventDefault()
      if (!blocked) startChosen()
      return
    }
    const step = steps[event.key]
    if (step === undefined) return
    event.preventDefault()
    const index = shown.findIndex((each) => each.id === id)
    const next = shown[Math.min(Math.max(index + step, 0), shown.length - 1)]
    if (next === undefined || next.id === id) return
    composer.pick(next.id)
    lookElement(list.current, next.id)?.focus()
  }

  return {
    ...composer,
    here,
    category: shownCategory,
    chooseCategory: (next) => {
      setCategory(next)
      setQuery('')
    },
    query,
    search: setQuery,
    searching: query.trim() !== '',
    shown,
    transitions,
    transition: key,
    chooseTransition: (next) => setChosen({ lookId: look?.id ?? null, key: next }),
    blocked,
    tabbable,
    onListKey,
    startChosen,
  }
}
