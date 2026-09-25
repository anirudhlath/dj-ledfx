import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Announcer } from '@/design/announcer'
import { Popover } from '@/design/overlays'
import { AttentionButton } from './attention-button'
import { ConnectionIndicator } from './connection-indicator'
import { useConnectionNews } from './connection-news'
import { HERO_CHROME, type Connection, type TempoState } from './state'
import { PreviewOnlySwitch } from './preview-only-switch'
import { TempoModule } from './tempo-module'

describe('TempoModule', () => {
  it('shows source, BPM, the beat and the bar (desktop)', async () => {
    const onTap = vi.fn()
    render(<TempoModule variant="bar" {...HERO_CHROME.tempo} onTap={onTap} />)
    const tempo = screen.getByRole('group', { name: 'Tempo' })
    expect(within(tempo).getByRole('button', { name: 'Music' })).toHaveAttribute('aria-haspopup', 'dialog')
    expect(tempo).toHaveTextContent('121.8BPM')
    expect(within(tempo).getByRole('img', { name: 'Beat 2 of 4' })).toBeInTheDocument()
    expect(tempo).toHaveTextContent('bar 42')
    await userEvent.click(within(tempo).getByRole('button', { name: 'Tap' }))
    expect(onTap).toHaveBeenCalledOnce()
  })

  it('drops the source button and the bar on the phone strip', () => {
    render(<TempoModule variant="strip" {...HERO_CHROME.tempo} />)
    const tempo = screen.getByRole('group', { name: 'Tempo' })
    expect(within(tempo).queryByRole('button', { name: 'Music' })).toBeNull()
    expect(tempo).toHaveTextContent('Music')
    expect(tempo).not.toHaveTextContent('bar 42')
    expect(within(tempo).getByRole('button', { name: 'Tap' })).toHaveClass('h-10')
  })

  // Decision 7: F3 attaches the tempo source popover without touching the component.
  it('lets a popover wrap the source button (desktop)', async () => {
    render(
      <TempoModule
        variant="bar"
        {...HERO_CHROME.tempo}
        renderSource={(source) => (
          <Popover trigger={source} title="Tempo source">
            <p>Music, from Home Assistant</p>
          </Popover>
        )}
      />,
    )
    const source = screen.getByRole('button', { name: 'Music' })
    await userEvent.click(source)
    expect(await screen.findByRole('dialog', { name: 'Tempo source' })).toBeInTheDocument()
    expect(source).toHaveAttribute('aria-expanded', 'true')
  })

  it('stale: the source turns signal, is named stale, and the pips stop', () => {
    const stale: TempoState = { source: 'internal', bpm: 118, beat: 2, bar: 7, stale: true }
    render(<TempoModule variant="bar" {...stale} />)
    const source = screen.getByRole('button', { name: 'Internal, stale' })
    expect(source).toHaveClass('text-signal')
    expect(screen.queryByRole('img')).toBeNull()
    expect(screen.getByRole('group', { name: 'Tempo' })).toHaveTextContent('118.0')
  })

  // Engine M1's beat counts no bars (decision 9).
  it('leaves the bar out when the source counts none', () => {
    render(<TempoModule variant="bar" {...HERO_CHROME.tempo} bar={null} />)
    // Not even the label: "bar " with no number is what a null left behind.
    expect(screen.getByRole('group', { name: 'Tempo' })).not.toHaveTextContent(/bar/)
  })
})

describe('PreviewOnlySwitch', () => {
  it('is a labelled tape switch on desktop', () => {
    render(<PreviewOnlySwitch variant="bar" on={false} />)
    expect(screen.getByRole('switch', { name: 'Preview only' })).toHaveAttribute('aria-checked', 'false')
  })

  it('is a 44 px eye button on phone that turns to tape when on', async () => {
    const onChange = vi.fn()
    const { rerender } = render(<PreviewOnlySwitch variant="header" on={false} onChange={onChange} />)
    const eye = screen.getByRole('switch', { name: 'Preview only' })
    expect(eye).toHaveClass('size-(--touch-min)')
    await userEvent.click(eye)
    expect(onChange).toHaveBeenCalledWith(true)
    rerender(<PreviewOnlySwitch variant="header" on onChange={onChange} />)
    expect(eye).toHaveClass('tape')
  })
})

describe('AttentionButton', () => {
  it('counts what needs attention', () => {
    render(<AttentionButton variant="bar" count={1} />)
    const button = screen.getByRole('button', { name: '1 needs attention' })
    expect(button).toHaveTextContent('Needs attention1')
    expect(button).toHaveClass('text-signal')
  })

  it('says All good at zero on desktop and hides on phone', () => {
    const { rerender } = render(<AttentionButton variant="bar" count={0} />)
    expect(screen.getByRole('button', { name: 'All good' })).toHaveClass('text-text-3')
    rerender(<AttentionButton variant="header" count={0} />)
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('agrees in number', () => {
    render(<AttentionButton variant="header" count={3} />)
    expect(screen.getByRole('button', { name: '3 need attention' })).toHaveTextContent('3')
  })

  // Decision 7: F3 opens the attention popover (desktop) and sheet (phone) from this button as is.
  it.each(['bar', 'header'] as const)('works as a Popover trigger (%s)', async (variant) => {
    render(
      <Popover trigger={<AttentionButton variant={variant} count={1} />} title="Needs attention">
        <p>Rope is offline</p>
      </Popover>,
    )
    const button = screen.getByRole('button', { name: '1 needs attention' })
    await userEvent.click(button)
    expect(await screen.findByRole('dialog', { name: 'Needs attention' })).toBeInTheDocument()
    expect(button).toHaveAttribute('aria-expanded', 'true')
  })
})

describe('ConnectionIndicator', () => {
  const live: Connection = { status: 'live', fps: 60 }
  const reconnecting: Connection = { status: 'reconnecting', attempt: 3 }

  it('shows Live with the frame rate', () => {
    render(<ConnectionIndicator variant="bar" connection={live} />)
    expect(screen.getByText('Live')).toBeInTheDocument()
    expect(screen.getByText('60 fps')).toHaveClass('num')
  })

  it('shows Reconnecting with the attempt, in signal', () => {
    render(<ConnectionIndicator variant="bar" connection={reconnecting} />)
    const face = screen.getByText('· try 3').parentElement
    expect(face).toHaveTextContent('Reconnecting· try 3')
    expect(face).toHaveClass('text-signal')
  })

  it('shows nothing on phone while live, and a reconnect pill otherwise', () => {
    const { container, rerender } = render(<ConnectionIndicator variant="header" connection={live} />)
    expect(container).toHaveTextContent(/^$/)
    rerender(<ConnectionIndicator variant="header" connection={reconnecting} />)
    expect(screen.getByText('Reconnecting · try 3')).toHaveClass('sr-only')
  })

  // The shell's one status region says the news (below); the indicator only draws.
  it.each(['bar', 'header'] as const)('is not a live region of its own (%s)', (variant) => {
    const { rerender } = render(<ConnectionIndicator variant={variant} connection={live} />)
    expect(screen.queryByRole('status')).toBeNull()
    rerender(<ConnectionIndicator variant={variant} connection={reconnecting} />)
    expect(screen.queryByRole('status')).toBeNull()
  })

  // F0 review: before the server's first word, the link claims nothing.
  it.each(['bar', 'header'] as const)('shows nothing while it first connects (%s)', (variant) => {
    const { container } = render(<ConnectionIndicator variant={variant} connection={{ status: 'connecting' }} />)
    expect(container).toBeEmptyDOMElement()
  })

  // Decision 3: no frames yet, so no frame rate.
  it('shows Live alone until it has measured the frame rate', () => {
    render(<ConnectionIndicator variant="bar" connection={{ status: 'live', fps: null }} />)
    expect(screen.getByText('Live')).toBeInTheDocument()
    expect(screen.queryByText(/fps/)).toBeNull()
  })
})

describe('connection news', () => {
  function Region({ connection }: { connection: Connection }) {
    return <Announcer news={useConnectionNews(connection.status)} />
  }

  // A screen reader reads changes inside a live region, but often not a region that arrives with
  // its text. So one status region is always there, and it carries the news, not every retry.
  it('announces a drop and a recovery through one lasting status region', () => {
    const { rerender } = render(<Region connection={{ status: 'live', fps: 60 }} />)
    const status = screen.getByRole('status')
    expect(status).toBeEmptyDOMElement()
    rerender(<Region connection={{ status: 'reconnecting', attempt: 1 }} />)
    expect(status).toHaveTextContent(/^Reconnecting$/)
    rerender(<Region connection={{ status: 'reconnecting', attempt: 2 }} />)
    expect(status).toHaveTextContent(/^Reconnecting$/)
    rerender(<Region connection={{ status: 'live', fps: 60 }} />)
    expect(status).toHaveTextContent(/^Live again$/)
    expect(screen.getByRole('status')).toBe(status)
  })

  it('says nothing on the first connect, and Reconnecting when it fails', () => {
    const { rerender } = render(<Region connection={{ status: 'connecting' }} />)
    const status = screen.getByRole('status')
    expect(status).toBeEmptyDOMElement()
    rerender(<Region connection={{ status: 'live', fps: null }} />)
    expect(status).toBeEmptyDOMElement()
    rerender(<Region connection={{ status: 'reconnecting', attempt: 1 }} />)
    expect(status).toHaveTextContent(/^Reconnecting$/)
  })
})
