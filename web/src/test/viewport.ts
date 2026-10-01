// jsdom has no matchMedia. This stand-in answers the two kinds of query the app asks,
// "(width < Nrem)" and "(prefers-reduced-motion: reduce)", and fires "change" when a test resizes
// across one or turns reduced motion on or off.
import { REDUCED_MOTION_QUERY } from '@/lib/use-media-query'

type Listener = () => void

let width = 1440
let reducedMotion = false
const subscribed = new Map<string, Set<Listener>>()

function evaluate(query: string): boolean {
  if (query === REDUCED_MOTION_QUERY) return reducedMotion
  const match = /^\(width < ([\d.]+)rem\)$/.exec(query)
  if (!match) throw new Error(`the test matchMedia can't evaluate "${query}"`)
  return width < Number(match[1]) * 16
}

export function installMatchMedia(): void {
  window.matchMedia = (query: string) =>
    ({
      get matches() {
        return evaluate(query)
      },
      addEventListener: (_type: string, listener: Listener) => {
        const set = subscribed.get(query) ?? new Set<Listener>()
        set.add(listener)
        subscribed.set(query, set)
      },
      removeEventListener: (_type: string, listener: Listener) => {
        subscribed.get(query)?.delete(listener)
      },
    }) as unknown as MediaQueryList
}

/** Changes the fake screen; listeners run only for queries whose answer changed. */
function change(apply: () => void): void {
  const before = new Map([...subscribed.keys()].map((q) => [q, evaluate(q)]))
  apply()
  for (const [query, listeners] of subscribed) {
    if (evaluate(query) !== before.get(query)) listeners.forEach((listener) => listener())
  }
}

/** Resize the fake viewport. */
export function setViewportWidth(next: number): void {
  change(() => (width = next))
}

/** Turn the system's reduced motion on or off. */
export function setReducedMotion(on: boolean): void {
  change(() => (reducedMotion = on))
}
