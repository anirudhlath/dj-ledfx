import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { liveStore } from '@/api/live-store'
import type { ScenarioName } from '@/api/mocks/scenarios'
import { api, ApiError } from '@/api/rest'
import { renderApp } from '@/test/app'
import { HERO_NOW, seedLive } from '@/test/live'
import { seedRest } from '@/test/rest'
import { setViewportWidth } from '@/test/viewport'

function openPhone(name: ScenarioName = 'hero') {
  setViewportWidth(390)
  seedRest(name)
  seedLive(name)
  return renderApp('/next/live')
}

const main = () => screen.getByRole('main')

describe("the phone's Live (§8.10)", () => {
  // Phone-Live.png, newest zone first (F3 decision 1).
  it('lists the zones under "Running", each linking to its detail, with Put a look on below', async () => {
    const router = openPhone()
    expect(within(main()).getByRole('heading', { name: 'Running' })).toBeInTheDocument()
    expect(within(main()).getByText('3 zones · all 19 lights')).toBeInTheDocument()
    const cards = within(main()).getAllByRole('article')
    expect(cards.map((card) => card.getAttribute('aria-label'))).toEqual([
      'Office desk — Twin comets',
      'Living room — Fireflies',
      'Whole home — Home sunset',
    ])
    expect(cards[1]).toHaveTextContent('Rope offline · Candle 2 switched off elsewhere')
    expect(within(cards[2]).getByText('since 18:04')).toBeInTheDocument()
    expect(within(main()).getByRole('link', { name: 'Put a look on' })).toHaveAttribute('href', '/next/live/put')
    await userEvent.click(within(cards[1]).getAllByRole('link')[0])
    expect(router.state.location.pathname).toBe('/next/live/zones/living')
  })

  // The desktop card's controls (use-zone-controls.ts), at the touch size; Review Focus 1.
  it("turns a zone off from its card, and says why when it can't", async () => {
    openPhone()
    const off = vi.spyOn(api, 'off').mockRejectedValue(new ApiError(409, 'The zone is restoring.', '/api/zones/office/off'))
    const card = screen.getByRole('article', { name: 'Office desk — Twin comets' })
    expect(within(card).getByRole('slider', { name: 'Brightness for Office desk' })).toBeInTheDocument()
    await userEvent.click(within(card).getByRole('button', { name: 'Turn off Office desk' }))
    expect(off).toHaveBeenCalledOnce()
    expect(await screen.findByText("Couldn't turn off Office desk. The zone is restoring.")).toBeInTheDocument()
  })

  // Phone-State-Preview-Only.
  it('puts the preview-only banner in the place of "Running"', () => {
    openPhone('preview-only')
    expect(within(main()).queryByRole('heading', { name: 'Running' })).toBeNull()
    expect(within(main()).getByRole('button', { name: 'Turn off preview only' })).toBeInTheDocument()
  })

  // Phone-State-Reconnecting.
  it('says the link is lost under the stage, holds the cards, and hides Put a look on', () => {
    openPhone()
    act(() => liveStore.setState({ connection: { status: 'reconnecting', attempt: 3 }, lastHeard: HERO_NOW.getTime() }))
    expect(within(main()).getByRole('region', { name: 'Lost the live link' })).toBeInTheDocument()
    expect(screen.getByRole('article', { name: 'Whole home — Home sunset' }).closest('[inert]')).not.toBeNull()
    expect(within(main()).queryByRole('heading', { name: 'Running' })).toBeNull()
    expect(within(main()).queryByRole('link', { name: 'Put a look on' })).toBeNull()
  })

  // Phone-State-Nothing-Running.
  it('says nothing is running, in one sentence, with Start again', () => {
    openPhone('nothing-running')
    expect(within(main()).queryByRole('heading', { name: 'Running' })).toBeNull()
    expect(within(main()).getByRole('heading', { name: 'Nothing running' })).toBeInTheDocument()
    expect(within(main()).getByText('Your lights are as they were: 9 on, 10 off.')).toBeInTheDocument()
    expect(within(main()).getByRole('button', { name: 'Start Home sunset on Whole home again' })).toBeInTheDocument()
  })

  // §9.4 First run, under the phone's stage.
  it("shows the empty home's card under the stage", () => {
    vi.spyOn(api, 'config').mockResolvedValue({})
    openPhone('first-run')
    expect(within(main()).getByRole('region', { name: 'No lights yet' })).toBeInTheDocument()
  })
})
