import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { liveStore } from '@/api/live-store'
import { LIVE_SPEC } from '@/design/live-numbers'
import { renderApp } from '@/test/app'
import { HERO_NOW, seedLive, startMockDataLayer } from '@/test/live'
import { seedRest } from '@/test/rest'
import { setViewportWidth } from '@/test/viewport'
import { ReconnectingCard } from './reconnecting'

/** 19:14:32 on the hero's evening: State-Reconnecting's last frame. */
const LAST_FRAME = new Date(2026, 8, 23, 19, 14, 32).getTime()

function dropped(attempt: number) {
  act(() => liveStore.setState({ connection: { status: 'reconnecting', attempt }, lastHeard: LAST_FRAME }))
}

describe('Reconnecting', () => {
  // Review Focus 3, §14 Resilience: within the drop the cards go inert, and Try now doesn't wait out the backoff.
  it('makes the cards inert, and Try now retries at once', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(HERO_NOW)
    seedRest('reconnecting')
    startMockDataLayer({ scenario: 'reconnecting' })
    renderApp('/next/live')
    await act(() => vi.advanceTimersByTimeAsync(200))
    const card = () => screen.getByRole('article', { name: 'Whole home — Home sunset' })
    expect(card().closest('[inert]')).toBeNull()

    // The mock drops the link a second after it connects, and refuses every retry.
    await act(() => vi.advanceTimersByTimeAsync(1000))
    expect(card().closest('[inert]')).toHaveStyle({ opacity: String(LIVE_SPEC.frozenCardsOpacity) })
    expect(screen.getByRole('link', { name: 'Put a look on' }).closest('[inert]')).not.toBeNull()
    const notice = screen.getByRole('region', { name: 'Lost the live link to homeserver' })
    expect(within(notice).getByText('Reconnecting · try 1')).toBeInTheDocument()

    // fireEvent, as chrome/hold.test.tsx does: under Vitest's fake timers user-event never settles (Testing
    // Library's async wrapper waits on a timer only Jest's fake timers would advance).
    fireEvent.click(within(notice).getByRole('button', { name: 'Try now' }))
    await act(() => vi.advanceTimersByTimeAsync(0))
    expect(within(notice).getByText('Reconnecting · try 2')).toBeInTheDocument()
  })

  // State-Reconnecting.
  it('says which try it is and when the last frame came, and goes when the link is back', () => {
    seedRest('hero')
    seedLive('hero')
    renderApp('/next/live')
    expect(screen.getByText('or click a room in the home')).toBeInTheDocument()
    dropped(3)
    const notice = screen.getByRole('region', { name: 'Lost the live link to homeserver' })
    expect(within(notice).getByText('Reconnecting · try 3')).toBeInTheDocument()
    expect(
      within(notice).getByText(
        'Your looks keep running on the server. This is the last frame, from 19:14:32. Controls come back when the link does.',
      ),
    ).toBeInTheDocument()
    // The frozen stage takes no click (§7.6), and State-Reconnecting's footer says none.
    expect(screen.queryByText('or click a room in the home')).toBeNull()
    act(() => liveStore.setState({ connection: { status: 'live', fps: 60 } }))
    expect(screen.queryByRole('region', { name: 'Lost the live link to homeserver' })).toBeNull()
    expect(screen.getByText('or click a room in the home')).toBeInTheDocument()
  })

  // Phone-State-Reconnecting's card; Task 18 puts it under the phone's stage.
  it("the phone's card says it shorter", () => {
    render(<ReconnectingCard variant="phone" />)
    dropped(3)
    const phone = screen.getByRole('region', { name: 'Lost the live link' })
    expect(within(phone).getByText('Reconnecting · try 3')).toBeInTheDocument()
    expect(within(phone).getByText('Your looks keep running on homeserver. Last frame 19:14:32.')).toBeInTheDocument()
    expect(within(phone).getByRole('button', { name: 'Try now' })).toBeInTheDocument()
  })

  it("says so under the phone's title", () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(HERO_NOW)
    setViewportWidth(390)
    seedRest('hero')
    seedLive('hero')
    renderApp('/next/live')
    expect(within(screen.getByRole('banner')).getByText(/sun sets/)).toBeInTheDocument()
    dropped(1)
    expect(within(screen.getByRole('banner')).getByText('last frame 19:14:32')).toBeInTheDocument()
  })
})
