// §8.1: "If more zones run than fit, older ones collapse to ZoneRows", in two steps (F3 decision 2), after
// the footer's hint (decision 34): step 0 draws every zone as a card and the hint under Put a look on, step 1
// the cards without the hint, step 2 every card compact, and each step k after that turns one more zone into
// a row (k - 2 rows), in rowOrder: healthy zones oldest first, then troubled ones (crashed, slow, waiting),
// then the selected one. The last of rowOrder always stays a card. The panel measures its scrolling box
// whenever the box, the list in it or the room the box shares with the footer resizes, and takes one step
// while the list overflows. A room that changes size, zones that change, and a list that grows shorter while
// the step stays (an overlay or a transition's bar that ends, a note that goes) start again from cards: what
// went may have made the room they need. The box alone doesn't, since the hint's going gives it the hint's
// room (Main.png's cards fit only then), nor does a step's own shrinking. Pure parts first, then the hook.
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { Id, RunningZone } from '@/api/contract'

export type ZoneShape = 'card' | 'compact' | 'row'

const TROUBLED: ReadonlySet<RunningZone['state']> = new Set(['crashed', 'slow', 'waiting'])

/** The order zones turn into rows. `newestFirst` is the panel's order (F3 decision 1). */
export function rowOrder(newestFirst: readonly RunningZone[], selected?: Id): RunningZone[] {
  const rank = (zone: RunningZone) => (zone.zoneId === selected ? 2 : TROUBLED.has(zone.state) ? 1 : 0)
  // Array sort is stable: within a rank the zones stay oldest first.
  return [...newestFirst].reverse().sort((a, b) => rank(a) - rank(b))
}

/** The step that drops the hint: the cards stay full. */
export const HINT_STEP = 1

/** Each zone's shape at `step`. */
export function shapesAt(newestFirst: readonly RunningZone[], step: number, selected?: Id): Map<Id, ZoneShape> {
  const order = rowOrder(newestFirst, selected)
  const rows = new Set(order.slice(0, Math.min(Math.max(step - HINT_STEP - 1, 0), order.length - 1)).map((zone) => zone.zoneId))
  return new Map(newestFirst.map((zone) => [zone.zoneId, rows.has(zone.zoneId) ? 'row' : step <= HINT_STEP ? 'card' : 'compact']))
}

/** Changes when the zones, or the order they'd collapse in, change: the collapse starts again from cards. */
export function collapseKey(newestFirst: readonly RunningZone[], selected?: Id): string {
  return JSON.stringify(rowOrder(newestFirst, selected).map((zone) => zone.zoneId))
}

export interface Measure {
  /** The room the scrolling box shares with the footer changed height since the last measure. */
  roomChanged: boolean
  /** The list grew shorter since the last measure, at the same step: something in it went. */
  shrank: boolean
  /** The list is taller than the box. */
  overflows: boolean
  /** The last step: the number of zones, plus the hint's step. */
  last: number
  /** Step 0 shows the hint. When it doesn't (decision 34), step 1 would change nothing, so it's skipped. */
  hint: boolean
}

export function nextStep(step: number, { roomChanged, shrank, overflows, last, hint }: Measure): number {
  if ((roomChanged || shrank) && step > 0) return 0
  if (!overflows || step >= last) return step
  return step === 0 && !hint ? Math.min(HINT_STEP + 1, last) : step + 1
}

export interface Collapse {
  /** Callback refs: the room the scrolling box shares with the footer, the box, and the list inside it. */
  room: (element: HTMLElement | null) => void
  box: (element: HTMLElement | null) => void
  list: (element: HTMLElement | null) => void
  listElement: HTMLElement | null
  step: number
}

/** `zones` running, and whether step 0 shows the footer's hint. */
export function useCollapse(key: string, zones: number, hint: boolean): Collapse {
  const [state, setState] = useState({ key, step: 0 })
  if (state.key !== key) {
    // React's way to adjust state to a prop: other zones start again from cards.
    setState({ key, step: 0 })
  }
  const [room, setRoom] = useState<HTMLElement | null>(null)
  const [box, setBox] = useState<HTMLElement | null>(null)
  const [list, setList] = useState<HTMLElement | null>(null)
  const last = zones + HINT_STEP
  const step = state.key === key ? state.step : 0
  // The step the list is drawn at, for the measures, which come after the layout.
  const drawn = useRef(step)
  useLayoutEffect(() => {
    drawn.current = step
  }, [step])
  useEffect(() => {
    if (room === null || box === null || list === null) return
    let roomHeight = room.clientHeight
    let listHeight = list.scrollHeight
    let listStep = drawn.current
    // Fires when the room or the box resizes, and when a step or what's in the list changes the list's or the
    // box's height: one step a time.
    const observer = new ResizeObserver(() => {
      const height = room.clientHeight
      const content = list.scrollHeight
      const shrank = drawn.current === listStep && content < listHeight
      const measure = { roomChanged: height !== roomHeight, shrank, overflows: box.scrollHeight > box.clientHeight, last, hint }
      roomHeight = height
      listHeight = content
      listStep = drawn.current
      setState((current) => {
        const step = nextStep(current.step, measure)
        return step === current.step ? current : { ...current, step }
      })
    })
    observer.observe(room)
    observer.observe(box)
    observer.observe(list)
    return () => observer.disconnect()
  }, [room, box, list, last, hint])
  return { room: setRoom, box: setBox, list: setList, listElement: list, step }
}
