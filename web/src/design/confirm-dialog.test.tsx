import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ConfirmDialog } from './confirm-dialog'

describe('ConfirmDialog', () => {
  it('asks before it acts, as a described alert dialog, and Cancel does nothing', async () => {
    const confirm = vi.fn()
    render(
      <ConfirmDialog
        trigger={<button type="button">Stop all</button>}
        title="Stop all?"
        description="Every zone stops."
        confirm="Stop all"
        onConfirm={confirm}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Stop all' }))
    const dialog = await screen.findByRole('alertdialog', { name: 'Stop all?' })
    expect(dialog).toHaveAccessibleDescription('Every zone stops.')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    expect(confirm).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Stop all' }))
    await userEvent.click(within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Stop all' }))
    expect(confirm).toHaveBeenCalledOnce()
  })
})
