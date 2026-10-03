// §8.1: "If more zones run than fit, older ones collapse to ZoneRows", in two steps (F3 decision 2):
// step 0 draws every zone as a card, step 1 every card compact, and each step k after that turns one more
// zone into a row (k - 1 rows), in rowOrder: healthy zones oldest first, then troubled ones (crashed, slow,
// waiting), then the selected one. The last of rowOrder always stays a card. The panel measures its
// scrolling box whenever the box or the list in it resizes, and takes one step while the list overflows; a
// box that changes size, or zones that change, start again from cards. Pure parts first, then the hook.
import { useEffect, useState } from 'react'
import type { Id, RunningZone } from '@/api/contract'

export type ZoneShape = 'card' | 'compact' | 'row'

const TROUBLED: ReadonlySet<RunningZone['state']> = new Set(['crashed', 'slow', 'waiting'])

/** The order zones turn into rows. `newestFirst` is the panel's order (F3 decision 1). */
export function rowOrder(newestFirst: readonly RunningZone[], selected?: Id): RunningZone[] {
  const rank = (zone: RunningZone) => (zone.zoneId === selected ? 2 : TROUBLED.has(zone.state) ? 1 : 0)
  // Array sort is stable: within a rank the zones stay oldest first.
  return [...newestFirst].reverse().sort((a, b) => rank(a) - rank(b))
}

/** Each zone's shape at `step`. */
export function shapesAt(newestFirst: readonly RunningZone[], step: number, selected?: Id): Map<Id, ZoneShape> {
  const order = rowOrder(newestFirst, selected)
  const rows = new Set(order.slice(0, Math.min(Math.max(step - 1, 0), order.length - 1)).map((zone) => zone.zoneId))
  return new Map(newestFirst.map((zone) => [zone.zoneId, rows.has(zone.zoneId) ? 'row' : step === 0 ? 'card' : 'compact']))
}

/** Changes when the zones, or the order they'd collapse in, change: the collapse starts again from cards. */
export function collapseKey(newestFirst: readonly RunningZone[], selected?: Id): string {
  return JSON.stringify(rowOrder(newestFirst, selected).map((zone) => zone.zoneId))
}

export interface Measure {
  /** The scrolling box changed height since the last measure. */
  boxChanged: boolean
  /** The list is taller than the box. */
  overflows: boolean
  /** The last step: the number of zones. */
  last: number
}

export function nextStep(step: number, { boxChanged, overflows, last }: Measure): number {
  if (boxChanged && step > 0) return 0
  return overflows && step < last ? step + 1 : step
}

export interface Collapse {
  /** Callback refs: the scrolling box, and the list inside it. */
  box: (element: HTMLElement | null) => void
  list: (element: HTMLElement | null) => void
  listElement: HTMLElement | null
  step: number
}

export function useCollapse(key: string, last: number): Collapse {
  const [state, setState] = useState({ key, step: 0 })
  if (state.key !== key) {
    // React's way to adjust state to a prop: other zones start again from cards.
    setState({ key, step: 0 })
  }
  const [box, setBox] = useState<HTMLElement | null>(null)
  const [list, setList] = useState<HTMLElement | null>(null)
  useEffect(() => {
    if (box === null || list === null) return
    let boxHeight = box.clientHeight
    // Fires when the box resizes, and when a step changes the list's height: one step a time.
    const observer = new ResizeObserver(() => {
      const height = box.clientHeight
      const measure = { boxChanged: height !== boxHeight, overflows: box.scrollHeight > height, last }
      boxHeight = height
      setState((current) => {
        const step = nextStep(current.step, measure)
        return step === current.step ? current : { ...current, step }
      })
    })
    observer.observe(box)
    observer.observe(list)
    return () => observer.disconnect()
  }, [box, list, last])
  return { box: setBox, list: setList, listElement: list, step: state.key === key ? state.step : 0 }
}
