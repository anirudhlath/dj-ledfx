// jsdom has no matchMedia. This stand-in answers the one kind of query the app asks,
// "(width < Nrem)", and fires "change" when a test resizes across it.
type Listener = () => void

let width = 1440
const subscribed = new Map<string, Set<Listener>>()

function evaluate(query: string): boolean {
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

/** Resize the fake viewport; listeners run only for queries whose answer changed. */
export function setViewportWidth(next: number): void {
  const before = new Map([...subscribed.keys()].map((q) => [q, evaluate(q)]))
  width = next
  for (const [query, listeners] of subscribed) {
    if (evaluate(query) !== before.get(query)) listeners.forEach((listener) => listener())
  }
}
