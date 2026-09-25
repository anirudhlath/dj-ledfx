import { act, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { liveStore } from '@/api/live-store'
import { attentionAbout, seedLive } from '@/test/live'
import { linkNames, renderAt as at } from '@/test/router'
import { PhoneHeader } from './phone-header'
import { Rail } from './rail'
import { TabBar } from './tab-bar'
import { TopBar } from './top-bar'

describe('Rail', () => {
  it('has the logo, then the six places in order, and the server in the footer', () => {
    seedLive()
    at('/live', <Rail server="homeserver" />)
    const rail = screen.getByRole('navigation', { name: 'Main' })
    expect(linkNames(rail)).toEqual(['', 'Live', 'Looks', 'Map', 'Devices, needs attention', 'Inputs', 'Settings'])
    expect(within(rail).getByRole('link', { name: 'dj-ledfx home' })).toHaveAttribute('href', '/next/live')
    expect(within(rail).getByRole('link', { name: 'Live' })).toHaveAttribute('aria-current', 'page')
    expect(rail).toHaveTextContent('dj-ledfx · homeserver')
  })

  it('marks the section of a nested path as current', () => {
    seedLive()
    at('/devices/tube', <Rail server="homeserver" />)
    const rail = screen.getByRole('navigation', { name: 'Main' })
    expect(within(rail).getByRole('link', { name: 'Devices, needs attention' })).toHaveAttribute('aria-current', 'page')
    expect(within(rail).getByRole('link', { name: 'Live' })).not.toHaveAttribute('aria-current')
  })

  it('puts the dot where the attention is, and nowhere when nothing needs it', () => {
    liveStore.setState({ attention: [attentionAbout('input', 'home-assistant')] })
    at('/live', <Rail server="homeserver" />)
    expect(linkNames(screen.getByRole('navigation'))).toContain('Inputs, needs attention')
    expect(linkNames(screen.getByRole('navigation'))).toContain('Devices')
    act(() => liveStore.setState({ attention: [] }))
    expect(screen.queryByText(', needs attention')).toBeNull()
  })

  it('puts no dot anywhere before the server speaks', () => {
    at('/live', <Rail server="homeserver" />)
    expect(screen.queryByText(', needs attention')).toBeNull()
  })
})

describe('TabBar', () => {
  it('has five tabs, and Tempo opens the phone view of /inputs', () => {
    liveStore.setState({ attention: [attentionAbout('input', 'home-assistant')] })
    at('/inputs', <TabBar />)
    const tabs = screen.getByRole('navigation', { name: 'Main' })
    expect(linkNames(tabs)).toEqual(['Live', 'Looks', 'Devices', 'Tempo, needs attention', 'Settings'])
    const tempo = within(tabs).getByRole('link', { name: 'Tempo, needs attention' })
    expect(tempo).toHaveAttribute('href', '/next/inputs')
    expect(tempo).toHaveAttribute('aria-current', 'page')
  })
})

describe('TopBar', () => {
  it('shows the title, the context and the cluster', () => {
    seedLive()
    at('/live', <TopBar title="Live" context="Wed 23 Sep · 19:14" />)
    const bar = screen.getByRole('banner')
    expect(within(bar).getByRole('heading', { level: 1 })).toHaveTextContent('Live')
    expect(bar).toHaveTextContent('Wed 23 Sep · 19:14')
    expect(within(bar).getByRole('group', { name: 'Tempo' })).toBeInTheDocument()
    expect(within(bar).getByRole('switch', { name: 'Preview only' })).toBeInTheDocument()
    expect(within(bar).getByRole('button', { name: '1 needs attention' })).toBeInTheDocument()
    expect(bar).toHaveTextContent('Live60 fps')
  })

  it('leaves the context out when a page has none', () => {
    at('/settings', <TopBar title="Settings" />)
    // The context line is the title's only sibling.
    expect(screen.getByRole('heading', { level: 1, name: 'Settings' }).nextElementSibling).toBeNull()
  })
})

describe('PhoneHeader', () => {
  it('shows the serif title and context, the eye and the attention count, and no reconnect pill while live', () => {
    seedLive()
    at('/live', <PhoneHeader title="Home" context="Wed 19:14 · sun sets 19:26" />)
    const header = screen.getByRole('banner')
    expect(within(header).getByRole('heading', { level: 1 })).toHaveTextContent('Home')
    expect(within(header).getByRole('heading', { level: 1 })).toHaveClass('font-serif')
    expect(header).toHaveTextContent('Wed 19:14 · sun sets 19:26')
    expect(within(header).getByRole('switch', { name: 'Preview only' })).toBeInTheDocument()
    expect(within(header).getByRole('button', { name: '1 needs attention' })).toBeInTheDocument()
    expect(within(header).queryByText(/Reconnecting/)).toBeNull()
  })

  it('puts the reconnect pill first while reconnecting', () => {
    seedLive()
    liveStore.setState({ connection: { status: 'reconnecting', attempt: 3 } })
    at('/live', <PhoneHeader title="Home" />)
    const pill = screen.getByText('Reconnecting · try 3').parentElement!
    expect(pill).toHaveClass('text-signal')
    expect(pill.compareDocumentPosition(screen.getByRole('switch'))).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
  })

  it('draws its children inside the banner', () => {
    at('/live', (
      <PhoneHeader title="Home">
        <p>strip</p>
      </PhoneHeader>
    ))
    expect(within(screen.getByRole('banner')).getByText('strip')).toBeInTheDocument()
  })
})
