import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { Button } from './button'
import { Dialog, Popover, Sheet, Tooltip } from './overlays'

describe('overlays', () => {
  it('Popover takes a width, and a count beside its title', async () => {
    render(
      <Popover trigger={<button type="button">Open</button>} title="Needs attention" width={430} aside={<span>4</span>}>
        <p>Items</p>
      </Popover>,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Open' }))
    const dialog = await screen.findByRole('dialog', { name: 'Needs attention' })
    expect(dialog).toHaveTextContent('Needs attention4')
    expect(dialog.style.width).toBe('430px')
  })

  // The tooltip is visual only: the trigger's own label names it, and the popup, loose in <body>,
  // stays out of the accessibility tree (and out of axe's region rule).
  it('Tooltip shows on keyboard focus, out of the accessibility tree', async () => {
    render(
      <Tooltip content="Fit the home">
        <button type="button" aria-label="Fit">x</button>
      </Tooltip>,
    )
    await userEvent.tab()
    const tip = await screen.findByText('Fit the home')
    expect(tip).toBeVisible()
    expect(tip.closest('[aria-hidden="true"]')).not.toBeNull()
  })

  it('Popover opens as a named dialog and closes on Escape', async () => {
    render(
      <Popover trigger={<Button>Open</Button>} title="Needs attention">
        <p>Rope is offline</p>
      </Popover>,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Open' }))
    expect(await screen.findByRole('dialog', { name: 'Needs attention' })).toBeInTheDocument()
    await userEvent.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('Dialog closes from its Close button and returns focus', async () => {
    render(
      <Dialog trigger={<Button>Restore</Button>} title="Restore from a file">
        <p>Everything is replaced.</p>
      </Dialog>,
    )
    const opener = screen.getByRole('button', { name: 'Restore' })
    await userEvent.click(opener)
    expect(await screen.findByRole('dialog', { name: 'Restore from a file' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Close' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(opener).toHaveFocus()
  })

  it('Sheet opens as a named dialog', async () => {
    render(
      <Sheet trigger={<Button>Where</Button>} title="Put a look on">
        <p>Pick a zone</p>
      </Sheet>,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Where' }))
    expect(await screen.findByRole('dialog', { name: 'Put a look on' })).toBeInTheDocument()
  })
})
