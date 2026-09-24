import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import { Button, ButtonLink, IconButton } from './button'

describe('Button', () => {
  it('is a real button that runs its action', async () => {
    const onClick = vi.fn()
    render(<Button onClick={onClick}>Stop all</Button>)
    const button = screen.getByRole('button', { name: 'Stop all' })
    expect(button).toHaveAttribute('type', 'button')
    await userEvent.click(button)
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('draws the variant and size classes', () => {
    render(<Button variant="primary" size="cta" icon="plus">Put a look on</Button>)
    const button = screen.getByRole('button', { name: 'Put a look on' })
    expect(button).toHaveClass('bg-text', 'text-on-text', 'h-13', 'w-full')
    expect(button.querySelector('svg')).toHaveAttribute('width', '18')
  })

  it('grows sm and md to the touch minimum on phone', () => {
    render(
      <>
        <Button size="sm">Stop ripple</Button>
        <Button>Change</Button>
      </>,
    )
    expect(screen.getByRole('button', { name: 'Stop ripple' })).toHaveClass('h-7.5', 'max-md:h-(--touch-min)')
    expect(screen.getByRole('button', { name: 'Change' })).toHaveClass('h-9', 'max-md:h-(--touch-min)')
  })

  it('does nothing while disabled', async () => {
    const onClick = vi.fn()
    render(<Button disabled onClick={onClick}>Restart</Button>)
    await userEvent.click(screen.getByRole('button', { name: 'Restart' }))
    expect(onClick).not.toHaveBeenCalled()
  })

  it('renders as a link when it navigates', () => {
    render(
      <MemoryRouter basename="/next" initialEntries={['/next/looks']}>
        <ButtonLink to="/live" variant="outline">Go to Live</ButtonLink>
      </MemoryRouter>,
    )
    expect(screen.getByRole('link', { name: 'Go to Live' })).toHaveAttribute('href', '/next/live')
  })
})

describe('IconButton', () => {
  it('is named by its label and exposes active as pressed', () => {
    const { rerender } = render(<IconButton icon="plan" label="Plan view" />)
    const button = screen.getByRole('button', { name: 'Plan view' })
    expect(button).not.toHaveAttribute('aria-pressed')
    expect(button).toHaveClass('size-8', 'max-md:size-(--touch-min)')
    rerender(<IconButton icon="plan" label="Plan view" active />)
    expect(button).toHaveAttribute('aria-pressed', 'true')
    expect(button).toHaveClass('bg-text', 'text-on-text')
  })
})
