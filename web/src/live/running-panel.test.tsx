import { QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, onTestFinished, vi } from 'vitest'
import type { Id } from '@/api/contract'
import type { ScenarioName } from '@/api/mocks/scenarios'
import { queryClient } from '@/api/queries'
import { api, ApiError } from '@/api/rest'
import { Announcer } from '@/design/announcer'
import { HERO_NOW, seedLive } from '@/test/live'
import { resizeObserved } from '@/test/resize'
import { seedRest } from '@/test/rest'
import { RunningPanel } from './running-panel'

function renderPanel(name: ScenarioName | null, selected?: Id) {
  if (name !== null) {
    seedRest(name)
    seedLive(name)
  }
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Announcer news="">
          <main>
            <RunningPanel selected={selected} />
          </main>
        </Announcer>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return screen.getByRole('complementary', { name: 'Running' })
}

const HEIGHT = { card: 300, compact: 200, row: 50 }
const HINT_TEXT = 'or click a room in the home'

/**
 * jsdom lays nothing out: each zone is as tall as its shape says. The room the scrolling box shares with the
 * footer (which holds Put a look on) is `room.height`, and the box has all of it but `hint` while the footer's
 * hint shows.
 */
function layOut(room: { height: number }, hint = 0) {
  vi.spyOn(Element.prototype, 'scrollHeight', 'get').mockImplementation(function (this: Element) {
    const items = [...this.querySelectorAll<HTMLElement>('[data-shape]')]
    return items.reduce((sum, item) => sum + HEIGHT[item.dataset.shape as keyof typeof HEIGHT], 0)
  })
  vi.spyOn(Element.prototype, 'clientHeight', 'get').mockImplementation(function (this: Element) {
    const shown = document.body.textContent?.includes(HINT_TEXT) === true
    return this.querySelector('a[href="/live/put"]') !== null || !shown ? room.height : room.height - hint
  })
}

/** Each zone's shape, by its name. */
function shapes(panel: HTMLElement) {
  return Object.fromEntries([...panel.querySelectorAll<HTMLElement>('[data-shape]')].map((item) => [item.getAttribute('aria-label'), item.dataset.shape]))
}

/** The panel measures when its box or its list resizes: once a step. */
const settle = (steps: number) => {
  for (let step = 0; step < steps; step += 1) act(() => resizeObserved(0, 0))
}

describe('RunningPanel', () => {
  // Main.png; F3 decision 1: the newest zone on top.
  it('heads the hero with its summary, newest zone first, and the footer says a room can be clicked', () => {
    const panel = renderPanel('hero')
    expect(within(panel).getByRole('heading', { level: 2, name: 'Running' })).toBeInTheDocument()
    expect(within(panel).getByText('3 zones · all 19 lights')).toBeInTheDocument()
    expect(within(panel).getAllByRole('article').map((card) => card.getAttribute('aria-label'))).toEqual([
      'Office desk — Twin comets',
      'Living room — Fireflies',
      'Whole home — Home sunset',
    ])
    expect(within(panel).getByRole('link', { name: 'Put a look on' })).toHaveAttribute('href', '/live/put')
    expect(within(panel).getByText(HINT_TEXT)).toBeInTheDocument()
  })

  // State-Problems; F3 decision 2.
  it('collapses the oldest healthy zones first, then the troubled, and starts again from cards when the box grows', () => {
    const box = { height: 600 }
    layOut(box)
    const panel = renderPanel('problems')
    expect(within(panel).getByText('4 zones · 1 stopped')).toBeInTheDocument()
    settle(4)
    expect(shapes(panel)).toEqual({
      'Office desk — Twin comets': 'row',
      'Kitchen — Lava': 'compact',
      'Living room — Embers': 'compact',
      'Bedroom — Sunset': 'row',
    })
    expect(within(panel).getByRole('link', { name: 'Bedroom — Sunset' })).toHaveAttribute('href', '/live/zones/bedroom')
    expect(within(panel).queryByText(HINT_TEXT)).toBeNull()
    box.height = 2_000
    settle(1)
    expect(new Set(Object.values(shapes(panel)))).toEqual(new Set(['card']))
  })

  // Main.png at 1440 × 900: its three cards fit once the footer's hint goes (F3 decision 34). The box the hint
  // gives back is no reason to start again from the hint, which would squeeze the cards and bring it back.
  it('drops the hint before it squeezes a card, and keeps still once the cards fit', () => {
    layOut({ height: 3 * HEIGHT.card + 10 }, 30)
    const panel = renderPanel('hero')
    expect(within(panel).getByText(HINT_TEXT)).toBeInTheDocument()
    settle(3)
    expect(new Set(Object.values(shapes(panel)))).toEqual(new Set(['card']))
    expect(within(panel).queryByText(HINT_TEXT)).toBeNull()
    settle(2)
    expect(new Set(Object.values(shapes(panel)))).toEqual(new Set(['card']))
  })

  // State-Firmware: the breakdown takes the hint's place, so there's no hint to drop first.
  it('goes straight to compact cards when there is no hint to drop', () => {
    layOut({ height: 100 })
    const panel = renderPanel('firmware')
    expect(within(panel).queryByText(HINT_TEXT)).toBeNull()
    settle(1)
    expect(new Set(Object.values(shapes(panel)))).toEqual(new Set(['compact']))
  })

  // Live-Doorbell: the overlay over everything comes first.
  it('puts an overlay over everything at the top', () => {
    const panel = renderPanel('doorbell')
    expect(within(panel).getByText('3 zones + 1 overlay')).toBeInTheDocument()
    expect(within(panel).getAllByRole('article')[0]).toHaveAccessibleName('Doorbell ripple over everything')
  })

  // State-Nothing-Running; §9.4; F3 decision 35.
  it('says nothing runs, lists what ran last, and starts one again in one tap', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(HERO_NOW)
    const start = vi.spyOn(api, 'start').mockReturnValue(new Promise(() => {}))
    const panel = renderPanel('nothing-running')
    expect(within(panel).getByText('Nothing running')).toHaveClass('text-display-lg')
    expect(within(panel).getByText('Your lights are as they were: 9 on, 10 off. Nothing turns on until you start a look.')).toBeInTheDocument()
    const list = within(panel).getByRole('list')
    expect(within(list).getAllByRole('listitem').map((row) => row.textContent)).toEqual([
      'GoodnightWhole home · yesterday 23:31 – today 07:00',
      'FirefliesLiving room · yesterday 21:10 – 23:31',
      'Home sunsetWhole home · yesterday 18:02 – 23:31',
    ])
    // Decision 35: Goodnight's end shows, so a line too long for its row goes on to a second, balanced, rather than lose its end.
    expect(within(list).getByText('Whole home · yesterday 23:31 – today 07:00')).not.toHaveClass('truncate')
    expect(within(list).getByText('Whole home · yesterday 23:31 – today 07:00')).toHaveClass('text-balance')
    expect(within(panel).queryByRole('button', { name: 'Stop all' })).toBeNull()
    expect(within(panel).queryByText(HINT_TEXT)).toBeNull()
    await userEvent.click(within(list).getByRole('button', { name: 'Start Goodnight on Whole home again' }))
    expect(start).toHaveBeenCalledWith('home', { lookId: 'goodnight' })
  })

  // §11.3: "Stop all does this for every zone after a confirm"; F3 decision 29; Review Focus 1.
  it('stops every zone after a confirm, and says so when the server refuses', async () => {
    const stop = vi.spyOn(api, 'stopAll').mockRejectedValue(new ApiError(500, 'The engine is restarting.', '/api/running/stop-all'))
    const panel = renderPanel('hero')
    await userEvent.click(within(panel).getByRole('button', { name: 'Stop all' }))
    const dialog = await screen.findByRole('alertdialog', { name: 'Stop all?' })
    expect(dialog).toHaveTextContent("Every zone's look stops, and each light goes back to how it was.")
    expect(stop).not.toHaveBeenCalled()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Stop all' }))
    expect(stop).toHaveBeenCalledOnce()
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent("Couldn't stop all. The engine is restarting."))
  })

  // F3 decision 23: /live/zones/:zoneId outlines its zone, which collapses last and scrolls into view.
  it('outlines the selected zone, keeps it a card, and scrolls it into view', () => {
    // jsdom doesn't scroll.
    const scrolled: Element[] = []
    const original = Element.prototype.scrollIntoView
    Element.prototype.scrollIntoView = function (this: Element) {
      scrolled.push(this)
    }
    onTestFinished(() => void (Element.prototype.scrollIntoView = original))
    layOut({ height: 600 })
    const panel = renderPanel('problems', 'bedroom')
    settle(4)
    const bedroom = within(panel).getByRole('article', { name: 'Bedroom — Sunset' })
    expect(bedroom).toHaveClass('outline-2')
    expect(bedroom.dataset.shape).toBe('compact')
    expect(shapes(panel)['Office desk — Twin comets']).toBe('row')
    expect(scrolled.at(-1)).toBe(bedroom)
  })

  // Like the chrome's "never All good before the data" (F0's review): never "Nothing running" before it.
  it("draws only its heading and Put a look on before the server's first data", () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})))
    const panel = renderPanel(null)
    expect(within(panel).getByRole('heading', { name: 'Running' })).toBeInTheDocument()
    expect(within(panel).queryByText('Nothing running')).toBeNull()
    expect(within(panel).queryByRole('article')).toBeNull()
    expect(within(panel).queryByRole('button', { name: 'Stop all' })).toBeNull()
    expect(within(panel).getByRole('link', { name: 'Put a look on' })).toBeInTheDocument()
  })
})
