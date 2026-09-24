import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Announcer } from './announcer'
import { Chip, Label, Tag } from './chip'
import { Toast } from './toast'

describe('Chip, Tag and Label', () => {
  it('draw their variants', () => {
    render(
      <>
        <Chip variant="signal" icon="music">Music · 42 s</Chip>
        <Tag variant="plain">OFFLINE</Tag>
        <Label>Running</Label>
      </>,
    )
    expect(screen.getByText('Music · 42 s')).toHaveClass('bg-signal-bg', 'text-signal', 'h-5.5')
    expect(screen.getByText('Music · 42 s').querySelector('svg')).toHaveAttribute('width', '13')
    expect(screen.getByText('OFFLINE')).toHaveClass('bg-bg/88', 'h-6.5')
    expect(screen.getByText('Running')).toHaveClass('label-caps')
  })
})

describe('Toast', () => {
  it('is tinted by the light it is about', () => {
    render(<Toast icon="bell" title="Doorbell" detail="Front door · 19:16" readout="1.8 s" tint="rgb(255, 207, 92)" />)
    const toast = screen.getByText('Doorbell').parentElement!
    expect(toast).toHaveTextContent('DoorbellFront door · 19:161.8 s')
    expect(toast.style.borderColor).toContain('rgb(255, 207, 92)')
    expect(screen.getByText('1.8 s')).toHaveStyle({ color: 'rgb(255, 207, 92)' })
  })

  it('keeps the neutral border and readout without a tint', () => {
    render(<Toast title="Saved" readout="2 s" />)
    expect(screen.getByText('Saved').parentElement!.getAttribute('style')).toBeNull()
    expect(screen.getByText('2 s').getAttribute('style')).toBeNull()
  })

  // A live region that arrives with its text often goes unannounced, so a toast isn't one: it
  // speaks through the lasting status region around it, and later news takes over the region.
  it('is not a live region of its own', () => {
    render(<Toast title="Doorbell" />)
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('says its words through the status region around it', () => {
    const doorbell = <Toast title="Doorbell" detail="Front door · 19:16" readout="1.8 s" />
    const { rerender } = render(<Announcer news="">{doorbell}</Announcer>)
    const status = screen.getByRole('status')
    expect(status).toHaveTextContent(/^Doorbell, Front door · 19:16$/)
    rerender(<Announcer news="Reconnecting">{doorbell}</Announcer>)
    expect(status).toHaveTextContent(/^Reconnecting$/)
  })
})
