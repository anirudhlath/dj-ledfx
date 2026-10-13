import type { FocusEvent } from 'react'

/**
 * `onFocus` for a row that scrolls on its own (the category chips, the phone's zone buttons): a button the keyboard focuses is scrolled
 * wholly into the row, with the room its focus ring needs (the row's scroll-px-1). Chromium treats an element 32 px or more in view as in
 * view and leaves the row where it is, which cuts the ring the row clips, and the chip or button at the row's edge is the one it cuts.
 * Only for `:focus-visible`, the focus the ring is drawn for: a press on a button that is partly cut moves nothing under the pointer.
 * A browser without scrollIntoView (jsdom) just doesn't scroll.
 */
export function revealKeyboardFocus(event: FocusEvent<HTMLElement>) {
  const { target } = event
  if (target instanceof HTMLElement && target.matches(':focus-visible')) target.scrollIntoView?.({ block: 'nearest', inline: 'nearest' })
}
