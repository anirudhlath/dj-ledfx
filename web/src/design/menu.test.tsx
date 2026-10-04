import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import { Menu, MenuItem, MenuLinkItem } from './menu'

describe('Menu', () => {
  it('opens a named menu inside <main>, runs an item, and follows a link item', async () => {
    const restart = vi.fn()
    const router = createMemoryRouter([
      {
        path: '/',
        element: (
          <main>
            <Menu trigger={<button type="button">More for Kitchen</button>} label="More for Kitchen">
              <MenuItem onClick={restart}>Restart</MenuItem>
              <MenuLinkItem to="/looks/lava">Edit look</MenuLinkItem>
            </Menu>
          </main>
        ),
      },
      { path: '/looks/lava', element: <p>The look editor</p> },
    ])
    render(<RouterProvider router={router} />)
    await userEvent.click(screen.getByRole('button', { name: 'More for Kitchen' }))
    const menu = await screen.findByRole('menu', { name: 'More for Kitchen' })
    expect(menu.closest('main')).not.toBeNull()
    await userEvent.click(screen.getByRole('menuitem', { name: 'Restart' }))
    expect(restart).toHaveBeenCalledOnce()
    await userEvent.click(screen.getByRole('button', { name: 'More for Kitchen' }))
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Edit look' }))
    expect(await screen.findByText('The look editor')).toBeInTheDocument()
  })
})
