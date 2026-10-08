// jsdom has no scrollIntoView (the app calls it with ?.). watchScrolling() stands one in for the rest of the
// test, as resize.ts stands in for ResizeObserver, and writes down each call.
import { onTestFinished } from 'vitest'

/** One call: the element asked to scroll into view, and the options it was asked with. */
export type Scroll = readonly [element: Element, options: ScrollIntoViewOptions | boolean | undefined]

/** Stands in for Element.scrollIntoView until the test ends; the calls, in order, are in the array it returns. */
export function watchScrolling(): Scroll[] {
  const scrolled: Scroll[] = []
  const original = Element.prototype.scrollIntoView
  Element.prototype.scrollIntoView = function (this: Element, options?: ScrollIntoViewOptions | boolean) {
    scrolled.push([this, options])
  }
  onTestFinished(() => void (Element.prototype.scrollIntoView = original))
  return scrolled
}
