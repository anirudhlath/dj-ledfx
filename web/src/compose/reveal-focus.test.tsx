import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { focusByKeyboard, focusVisibleAs, watchScrolling } from '@/test/scroll'
import { revealKeyboardFocus } from './reveal-focus'

function row() {
  render(
    <div role="group" aria-label="Row" onFocus={revealKeyboardFocus}>
      <button type="button">First</button>
      <button type="button">Last</button>
      <input aria-label="Field" />
    </div>,
  )
  return { first: screen.getByRole('button', { name: 'First' }), last: screen.getByRole('button', { name: 'Last' }) }
}

describe('revealKeyboardFocus', () => {
  // Chromium leaves a button that is 32 px or more in view where it is, which cuts the ring the row clips at its edge.
  it('scrolls the button the keyboard focuses wholly into view, to the nearest edge, and only that one', () => {
    const scrolled = watchScrolling()
    const { first, last } = row()
    focusByKeyboard(last)
    expect(scrolled).toEqual([[last, { block: 'nearest', inline: 'nearest' }]])
    focusByKeyboard(first)
    expect(scrolled).toEqual([
      [last, { block: 'nearest', inline: 'nearest' }],
      [first, { block: 'nearest', inline: 'nearest' }],
    ])
  })

  // The ring is drawn for :focus-visible only, and a press on a partly cut button must not move the row under the pointer.
  it('leaves a row alone when a press focuses a button, which draws no ring', async () => {
    const scrolled = watchScrolling()
    const { last } = row()
    focusVisibleAs(last, false)
    await userEvent.click(last)
    expect(last).toHaveFocus()
    expect(scrolled).toEqual([])
  })

  it('takes whatever takes focus in the row, not only buttons', () => {
    const scrolled = watchScrolling()
    row()
    const field = screen.getByRole('textbox', { name: 'Field' })
    focusByKeyboard(field)
    expect(scrolled).toEqual([[field, { block: 'nearest', inline: 'nearest' }]])
  })

  it('does nothing where the browser has no scrollIntoView, as jsdom has none', () => {
    const { last } = row()
    expect(() => focusByKeyboard(last)).not.toThrow()
    expect(last).toHaveFocus()
  })
})
