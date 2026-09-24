import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { SystemPage } from './system'

// Later milestones copy the specimen. System.png draws Off as an outline button, and §2.1 keeps
// the signal colour for "this needs you", so only the destructive Remove light… is danger.
it('draws Off as an outline button and Remove light… as the danger one', () => {
  render(<SystemPage />)
  const off = screen.getByRole('button', { name: 'Off' })
  expect(off).toHaveClass('border-line-strong')
  expect(off).not.toHaveClass('text-signal')
  expect(screen.getByRole('button', { name: 'Remove light…' })).toHaveClass('text-signal')
})
