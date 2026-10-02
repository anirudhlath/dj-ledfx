// jsdom has no ResizeObserver. The shared setup installs this stand-in, which reports a size only
// when a test gives one: resizeObserved() sends it to every element being observed, as a layout
// would. Wrap the call in act().
const observers = new Set<FakeResizeObserver>()

class FakeResizeObserver implements ResizeObserver {
  private readonly callback: ResizeObserverCallback
  private readonly targets = new Set<Element>()

  constructor(callback: ResizeObserverCallback) {
    this.callback = callback
    observers.add(this)
  }

  observe(target: Element): void {
    this.targets.add(target)
  }

  unobserve(target: Element): void {
    this.targets.delete(target)
  }

  disconnect(): void {
    this.targets.clear()
    observers.delete(this)
  }

  report(width: number, height: number): void {
    const entries = [...this.targets].map((target) => ({ target, contentRect: { width, height } }) as unknown as ResizeObserverEntry)
    if (entries.length > 0) this.callback(entries, this)
  }
}

export function installResizeObserver(): void {
  window.ResizeObserver = FakeResizeObserver
}

/** Gives every observed element this content size. */
export function resizeObserved(width: number, height: number): void {
  for (const observer of observers) observer.report(width, height)
}

/** Forgets the observers a test left behind. */
export function resetResizeObservers(): void {
  observers.clear()
}
