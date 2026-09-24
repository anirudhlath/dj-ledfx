import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AttentionButton } from './attention-button'
import { ConnectionIndicator } from './connection-indicator'
import { HERO_CHROME } from './state'
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

  it('stale: the source turns signal, is named stale, and the pips stop', () => {
    render(<TempoModule variant="bar" source="internal" bpm={118} beat={2} bar={7} stale />)
    const source = screen.getByRole('button', { name: 'Internal, stale' })
    expect(source).toHaveClass('text-signal')
    expect(screen.queryByRole('img')).toBeNull()
    expect(screen.getByRole('group', { name: 'Tempo' })).toHaveTextContent('118.0')
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
})

describe('ConnectionIndicator', () => {
  it('shows Live with the frame rate', () => {
    render(<ConnectionIndicator variant="bar" connection={{ status: 'live', fps: 60 }} />)
    expect(screen.getByText('Live')).toBeInTheDocument()
    expect(screen.getByText('60 fps')).toHaveClass('num')
  })

  it('shows Reconnecting with the attempt, in signal', () => {
    render(<ConnectionIndicator variant="bar" connection={{ status: 'reconnecting', attempt: 3 }} />)
    const status = screen.getByRole('status')
    expect(status).toHaveTextContent('Reconnecting· try 3')
    expect(status).toHaveClass('text-signal')
  })

  it('shows nothing on phone while live, and a reconnect pill otherwise', () => {
    const { container, rerender } = render(<ConnectionIndicator variant="header" connection={{ status: 'live', fps: 60 }} />)
    expect(container).toBeEmptyDOMElement()
    rerender(<ConnectionIndicator variant="header" connection={{ status: 'reconnecting', attempt: 3 }} />)
    expect(screen.getByRole('status')).toHaveTextContent('Reconnecting · try 3')
  })
})
