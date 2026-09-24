// jsdom has no matchMedia. This stand-in evaluates the width queries the app uses,
// "(width < Nrem)" and "(width >= Nrem)", and fires "change" when a test resizes.
type Listener = () => void

let width = 1440
const subscribed = new Map<string, Set<Listener>>()

function evaluate(query: string): boolean {
  const match = /^\(width (<|>=) ([\d.]+)rem\)$/.exec(query)
  if (!match) throw new Error(`the test matchMedia can't evaluate "${query}"`)
  const px = Number(match[2]) * 16
  return match[1] === '<' ? width < px : width >= px
}

export function installMatchMedia(): void {
  window.matchMedia = (query: string) =>
    ({
      media: query,
      get matches() {
        return evaluate(query)
      },
      onchange: null,
      addEventListener: (_type: string, listener: Listener) => {
        const set = subscribed.get(query) ?? new Set<Listener>()
        set.add(listener)
        subscribed.set(query, set)
      },
      removeEventListener: (_type: string, listener: Listener) => {
        subscribed.get(query)?.delete(listener)
      },
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
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
