import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { buildScenario } from '@/api/mocks/scenarios'
import { api, ApiError } from '@/api/rest'
import { renderApp } from '@/test/app'
import { HERO_NOW, seedLive } from '@/test/live'
import { seedRest } from '@/test/rest'

describe('the empty home', () => {
  // State-No-Lights-Placed's card, on Live (F3 decision 21).
  it('asks for the lights to be placed, places them roughly, and goes once they are', async () => {
    const { lights } = seedRest('no-lights')
    seedLive('no-lights')
    const guess = vi.spyOn(api, 'guessPlacements').mockResolvedValue({})
    vi.spyOn(api, 'lights').mockResolvedValue(buildScenario('hero', HERO_NOW).lights)
    renderApp('/next/live')
    const card = screen.getByRole('region', { name: `Place your ${lights.length} lights` })
    expect(within(card).getByRole('link', { name: 'Open the map' })).toHaveAttribute('href', '/next/map')
    await userEvent.click(within(card).getByRole('button', { name: 'Place them roughly for me' }))
    expect(guess).toHaveBeenCalledOnce()
    await waitFor(() => expect(screen.queryByRole('region', { name: /^Place your/ })).toBeNull())
    expect(screen.getByText('Placed the lights at guessed spots. Confirm them on the map.')).toBeInTheDocument()
  })

  // Review Focus 1.
  it("says why the lights couldn't be placed, and keeps the card", async () => {
    seedRest('no-lights')
    seedLive('no-lights')
    vi.spyOn(api, 'guessPlacements').mockRejectedValue(new ApiError(409, 'A backup is being restored.', '/api/lights/placement/guess'))
    renderApp('/next/live')
    const card = screen.getByRole('region', { name: /^Place your/ })
    await userEvent.click(within(card).getByRole('button', { name: 'Place them roughly for me' }))
    expect(await screen.findByText("Couldn't place the lights. A backup is being restored.")).toBeInTheDocument()
    expect(within(card).getByRole('button', { name: 'Place them roughly for me' })).toBeEnabled()
  })

  // §9.4 "First run, no lights found": "No lights yet" + Find new lights + which integrations are on.
  it('looks for lights on first run, and says which integrations look', async () => {
    seedRest('first-run')
    seedLive('first-run')
    vi.spyOn(api, 'config').mockResolvedValue({ devices: { openrgb: { enabled: false } } })
    const scan = vi.spyOn(api, 'scanDevices').mockResolvedValue({ discovered: 0 })
    // Find new lights loads the lights again once the scan is done: still none.
    vi.spyOn(api, 'lights').mockResolvedValue([])
    renderApp('/next/live')
    const card = screen.getByRole('region', { name: 'No lights yet' })
    expect(await within(card).findByText('Find new lights looks for LIFX and Govee lights on your network.')).toBeInTheDocument()
    await userEvent.click(within(card).getByRole('button', { name: 'Find new lights' }))
    expect(scan).toHaveBeenCalledOnce()
    expect(await screen.findByText('Found no new lights.')).toBeInTheDocument()
  })
})
