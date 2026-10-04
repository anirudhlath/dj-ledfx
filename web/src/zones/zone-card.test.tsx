import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import type { Id } from '@/api/contract'
import { liveStore } from '@/api/live-store'
import type { ScenarioName, ScenarioState } from '@/api/mocks/scenarios'
import { api, ApiError } from '@/api/rest'
import { Announcer } from '@/design/announcer'
import { HERO_NOW } from '@/test/live'
import { runningIn, scenarioWorld } from '@/test/zones'
import { OverlayCard } from './overlay-card'
import { SEND_EVERY_MS } from './use-throttled-value'
import { ZoneCard } from './zone-card'
import { ZoneRow } from './zone-row'
import { chipsFor, zoneView } from './zone-view'

/** Inside a router, the page's status region and <main>, as Live has them. */
function inPage(ui: ReactNode) {
  render(
    <MemoryRouter>
      <Announcer news="">
        <main>{ui}</main>
      </Announcer>
    </MemoryRouter>,
  )
}

function renderCard(name: ScenarioName, zoneId: Id, { compact = false, change }: { compact?: boolean; change?: (state: ScenarioState) => void } = {}) {
  const { state, world } = scenarioWorld(name, change)
  const running = runningIn(state, zoneId)
  const view = zoneView(running, world, HERO_NOW, compact)
  inPage(<ZoneCard running={running} view={view} compact={compact} />)
  return screen.getByRole('article', { name: `${view.name} — ${view.lookName}` })
}

/** The server's answer to a brightness or a restart: the zone as it runs in the hero. */
const answer = async (zoneId: Id) => runningIn(scenarioWorld('hero').state, zoneId)

describe('ZoneCard', () => {
  // §14 Components: "every ZoneCard state". Main.png's living room card.
  it('draws a running zone as Main.png does', () => {
    const card = renderCard('hero', 'living')
    expect(card).toHaveClass('border-line')
    expect(within(card).getByText('11 lights')).toBeInTheDocument()
    expect(within(card).getByRole('heading', { name: 'Fireflies' })).toHaveClass('text-display-md')
    expect(within(card).getByText('No inputs')).toBeInTheDocument()
    expect(within(card).getByText('since 19:05 · 9 m')).toBeInTheDocument()
    expect(within(card).getAllByRole('img')).toHaveLength(11)
    expect(within(card).getByText('Rope offline')).toHaveClass('text-signal')
    expect(card).toHaveTextContent("Rope offline since 17:02 · Candle 2 was switched off elsewhere and rejoins when it's back on")
    expect(within(card).getByRole('slider', { name: 'Brightness for Living room' })).toHaveAttribute('aria-valuetext', '70%')
    expect(within(card).getByRole('button', { name: 'Turn off Living room' })).toHaveTextContent('Off')
  })

  // State-Transition's living room card.
  it('draws a transition: the old look struck through, its kind and its progress', () => {
    const card = renderCard('transition', 'living')
    const heading = within(card).getByRole('heading', { name: 'from Fireflies to Embers' })
    expect(within(heading).getByText('Fireflies').tagName).toBe('S')
    expect(within(card).getByText('Dissolve · 3 s')).toBeInTheDocument()
    expect(within(card).getByText('62%')).toBeInTheDocument()
    expect(within(card).getByRole('progressbar', { name: 'Dissolve · 3 s' })).toHaveAttribute('aria-valuenow', '62')
  })

  // F3 decision 16: the server pushes a transition only as it starts, passes its midpoint and ends.
  it('moves a transition on by itself at its duration, and holds one with no duration', () => {
    vi.useFakeTimers()
    const card = renderCard('transition', 'living')
    const bar = within(card).getByRole('progressbar', { name: 'Dissolve · 3 s' })
    act(() => vi.advanceTimersByTime(600))
    expect(within(card).getByText('82%')).toBeInTheDocument()
    expect(bar).toHaveAttribute('aria-valuenow', '82')
    act(() => vi.advanceTimersByTime(5_000))
    expect(within(card).getByText('100%')).toBeInTheDocument()
    cleanup()
    const held = renderCard('transition', 'living', {
      change: (state) => (runningIn(state, 'living').transition = { from: 'Fireflies', kind: 'fade', progress: 0.25, durationS: 0 }),
    })
    act(() => vi.advanceTimersByTime(600))
    expect(within(held).getByText('25%')).toBeInTheDocument()
  })

  // State-Problems' kitchen card, compact.
  it('draws a crashed zone with a signal border, says why, and offers Restart · Details · Off', async () => {
    const restart = vi.spyOn(api, 'restart').mockImplementation(answer)
    const card = renderCard('problems', 'kitchen', { compact: true })
    expect(card).toHaveClass('border-signal-line')
    expect(within(card).getByRole('heading', { name: 'Lava' })).toHaveClass('text-display-sm')
    expect(within(card).getByText('stopped at 19:12')).toBeInTheDocument()
    const note = within(card).getByText('Layer “Plasma” raised an error at 19:12. The Kitchen lights are holding the last frame.')
    expect(note.closest('p')).toHaveClass('text-signal')
    expect(within(card).queryByRole('slider')).toBeNull()
    expect(within(card).getByRole('link', { name: 'Details' })).toHaveAttribute('href', '/looks/lava')
    expect(within(card).getByRole('button', { name: 'Turn off Kitchen' })).toBeInTheDocument()
    await userEvent.click(within(card).getByRole('button', { name: 'Restart' }))
    expect(restart).toHaveBeenCalledWith('kitchen')
  })

  // State-Problems' living room card, compact.
  it("writes a slow zone's note in signal, its frame rate in mono", () => {
    const card = renderCard('problems', 'living', { compact: true })
    const actual = within(card).getByText('38')
    expect(actual).toHaveClass('num')
    expect(actual.closest('p')).toHaveTextContent('38 of 60 fps for 2 min. The other zones are fine.')
    expect(actual.closest('p')).toHaveClass('text-signal')
    expect(card).toHaveClass('border-line')
  })

  // §6.3 "waiting for an input" (State-Sheet).
  it("turns a waiting zone's missing input signal, and says it waits", () => {
    const card = renderCard('waiting', 'living')
    expect(within(card).getByText('Music')).toHaveClass('text-signal')
    expect(within(card).getByText('Nothing playing on Music Assistant. The look waits dark and starts with the music.').closest('p')).toHaveClass(
      'text-text-3',
    )
  })

  // Review Focus 1.
  it('puts the slider back and says why when the brightness is refused', async () => {
    vi.spyOn(api, 'setBrightness').mockRejectedValue(new ApiError(409, 'The zone is busy.', '/api/zones/living/brightness'))
    const card = renderCard('hero', 'living')
    const slider = within(card).getByRole('slider', { name: 'Brightness for Living room' })
    fireEvent.change(slider, { target: { value: '40' } })
    expect(slider).toHaveAttribute('aria-valuetext', '40%')
    await waitFor(() => expect(slider).toHaveAttribute('aria-valuetext', '70%'))
    expect(screen.getByRole('status')).toHaveTextContent("Couldn't change the brightness of Living room. The zone is busy.")
  })

  // Review Focus 3: the card reads the link from the live store.
  it('sends nothing still queued once the link drops', async () => {
    vi.useFakeTimers()
    const send = vi.spyOn(api, 'setBrightness').mockImplementation(async (zoneId, value) => ({ ...(await answer(zoneId)), brightness: value }))
    const card = renderCard('hero', 'living')
    const slider = within(card).getByRole('slider', { name: 'Brightness for Living room' })
    fireEvent.change(slider, { target: { value: '60' } })
    fireEvent.change(slider, { target: { value: '30' } })
    act(() => liveStore.setState({ connection: { status: 'reconnecting', attempt: 1 } }))
    await act(() => vi.advanceTimersByTimeAsync(SEND_EVERY_MS * 3))
    expect(send.mock.calls).toEqual([['living', 0.6]])
    expect(slider).toHaveAttribute('aria-valuetext', '70%')
  })

  it("turns a zone off, and says so when the server doesn't answer", async () => {
    const off = vi.spyOn(api, 'off').mockRejectedValue(new ApiError(0, '', '/api/zones/living/off'))
    const card = renderCard('hero', 'living')
    await userEvent.click(within(card).getByRole('button', { name: 'Turn off Living room' }))
    expect(off).toHaveBeenCalledWith('living')
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent("Couldn't turn off Living room. The server didn't answer."))
  })

  // Review Focus 5.
  it('draws a zone with no lights', () => {
    const card = renderCard('hero', 'living', { change: (state) => (runningIn(state, 'living').lights = []) })
    expect(within(card).queryAllByRole('img')).toEqual([])
    expect(within(card).getByText('0 lights')).toBeInTheDocument()
    expect(within(card).getByRole('slider', { name: 'Brightness for Living room' })).toBeInTheDocument()
  })

  // §6.3: "More" (Edit look, Change look, Restart, Show lights on the map).
  it('offers Edit look, Change look, Restart and Show lights on the map', async () => {
    const restart = vi.spyOn(api, 'restart').mockImplementation(answer)
    const card = renderCard('hero', 'living')
    await userEvent.click(within(card).getByRole('button', { name: 'More for Living room' }))
    const menu = await screen.findByRole('menu', { name: 'More for Living room' })
    expect(within(menu).getAllByRole('menuitem').map((item) => item.textContent)).toEqual([
      'Edit look',
      'Change look',
      'Restart',
      'Show lights on the map',
    ])
    expect(within(menu).getByRole('menuitem', { name: 'Edit look' })).toHaveAttribute('href', '/looks/fireflies')
    expect(within(menu).getByRole('menuitem', { name: 'Change look' })).toHaveAttribute('href', '/live/put?zone=living')
    expect(within(menu).getByRole('menuitem', { name: 'Show lights on the map' })).toHaveAttribute('href', '/map/living')
    await userEvent.click(within(menu).getByRole('menuitem', { name: 'Restart' }))
    expect(restart).toHaveBeenCalledWith('living')
  })
})

describe('ZoneRow', () => {
  // §6.3 ZoneRow; State-Problems' rows.
  it('draws a zone on one line, linked to its card', () => {
    const { state, world } = scenarioWorld('problems')
    const view = zoneView(runningIn(state, 'bedroom'), world, HERO_NOW, true)
    inPage(<ZoneRow view={view} to="/live/zones/bedroom" />)
    const row = screen.getByRole('link', { name: 'Bedroom — Sunset' })
    expect(row).toHaveAttribute('href', '/live/zones/bedroom')
    expect(within(row).getByText('Sunset')).toHaveClass('text-display-xs')
    expect(within(row).getAllByRole('img')).toHaveLength(view.lights.length)
  })
})

describe('OverlayCard', () => {
  // Live-Doorbell; F3 decision 17; Review Focus 5.
  it('counts an overlay down from an animation frame, and stops at zero with a full bar', () => {
    vi.useFakeTimers()
    vi.setSystemTime(HERO_NOW)
    const { state, world } = scenarioWorld('doorbell')
    const [overlay] = state.overlays
    inPage(<OverlayCard overlay={overlay} inputs={chipsFor(world.looks.get(overlay.lookId)!)} />)
    const card = screen.getByRole('article', { name: 'Doorbell ripple over everything' })
    expect(card).toHaveTextContent('Over everything · 2.4 s left')
    expect(within(card).getByText('Home Assistant')).toBeInTheDocument()
    expect(within(card).getByText(overlay.trigger)).toBeInTheDocument()
    const bar = within(card).getByRole('progressbar', { name: 'Doorbell ripple' })
    expect(bar).toHaveAttribute('aria-valuenow', '40')
    act(() => vi.advanceTimersByTime(1_000))
    expect(card).toHaveTextContent('Over everything · 1.4 s left')
    act(() => vi.advanceTimersByTime(5_000))
    expect(card).toHaveTextContent('Over everything · 0.0 s left')
    expect(bar).toHaveAttribute('aria-valuenow', '100')
  })
})
