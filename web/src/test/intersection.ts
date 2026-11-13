// jsdom has no IntersectionObserver. The shared setup installs this stand-in, which reports only
// when a test says so: intersect() tells every observer watching an element that it came on screen
// or went off, as scrolling would. A real observer also reports each element once as it starts to
// watch it; this one doesn't, so an element is off screen until a test brings it on. Wrap the call in act().
const observers = new Set<FakeIntersectionObserver>()

class FakeIntersectionObserver implements IntersectionObserver {
  readonly root = null
  readonly rootMargin = '0px'
  readonly thresholds = [0]
  private readonly callback: IntersectionObserverCallback
  private readonly targets = new Set<Element>()

  constructor(callback: IntersectionObserverCallback) {
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

  takeRecords(): IntersectionObserverEntry[] {
    return []
  }

  report(target: Element, visible: boolean): void {
    if (!this.targets.has(target)) return
    const entry = { target, isIntersecting: visible, intersectionRatio: visible ? 1 : 0 } as unknown as IntersectionObserverEntry
    this.callback([entry], this)
  }
}

export function installIntersectionObserver(): void {
  window.IntersectionObserver = FakeIntersectionObserver
}

/** Brings `element` on screen or takes it off, for every observer watching it. */
export function intersect(element: Element, visible: boolean): void {
  // A copy: a callback may disconnect its observer, or start another.
  for (const observer of [...observers]) observer.report(element, visible)
}

/** Forgets the observers a test left behind. */
export function resetIntersectionObservers(): void {
  observers.clear()
}
