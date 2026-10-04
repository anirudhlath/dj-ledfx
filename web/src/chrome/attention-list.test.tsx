import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { liveStore } from '@/api/live-store'
import { api, ApiError } from '@/api/rest'
import { renderApp } from '@/test/app'
import { seedLive } from '@/test/live'
import { setViewportWidth } from '@/test/viewport'

/** Live's chrome on the problems scenario, on a page with nothing else on it. */
async function openList() {
  seedLive('problems')
  const router = renderApp('/next/devices')
  await userEvent.click(within(screen.getByRole('banner')).getByRole('button', { name: '5 need attention' }))
  return { router, list: await screen.findByRole('dialog', { name: 'Needs attention' }) }
}

const rows = (list: HTMLElement) => within(list).getAllByRole('listitem')
/** Each row's actions, by their words. */
const actionsOf = (row: HTMLElement) => [...row.querySelectorAll('a, button')].map((action) => action.textContent)
const crashed = () => liveStore.getState().running!.zones.find((zone) => zone.zoneId === 'kitchen')!

describe('the attention list', () => {
  // §6.2, State-Problems: the popover under the button, its count at the title row's end; the server's
  // order and words (§9.5, F3 decision 15); up to two actions, the first secondary, the second ghost.
  it("lists the server's items in its order, each with its icon, words and actions, on desktop", async () => {
    const { list } = await openList()
    expect(list.style.width).toBe('430px')
    expect(within(list).getByText('5')).toHaveClass('text-signal')
    expect(rows(list).map((row) => row.querySelector('span')!.textContent)).toEqual([
      'Lava crashed',
      'Music Assistant went quiet',
      'Living room is running slow',
      'Home Assistant is disconnected',
      'Rope offline',
    ])
    const [lava, music, , homeAssistant, rope] = rows(list)
    expect(within(lava).getByText('The Kitchen lights are holding the last frame. Plasma: raised an error')).toBeInTheDocument()
    expect(lava.querySelector('svg')).toHaveClass('text-signal')
    expect(music.querySelector('svg')).toHaveClass('text-text-3')
    expect(within(lava).getByRole('button', { name: 'Restart' })).toHaveClass('bg-control')
    expect(within(lava).getByRole('link', { name: 'Details' })).toHaveClass('bg-transparent')
    expect(within(lava).getByRole('link', { name: 'Details' })).toHaveAttribute('href', '/next/looks/lava')
    // F3 decision 14: Home Assistant's Retry waits for an engine that serves one.
    expect(within(homeAssistant).queryByRole('button', { name: /Retry/ })).toBeNull()
    expect(within(homeAssistant).getByRole('link', { name: 'Open Inputs' })).toHaveAttribute('href', '/next/inputs')
    expect(within(rope).getByRole('link', { name: 'Details' })).toHaveAttribute('href', '/next/devices/rope')
  })

  it('restarts a crashed look, and says why when the engine refuses', async () => {
    const { list } = await openList()
    const restart = vi
      .spyOn(api, 'restart')
      .mockRejectedValueOnce(new ApiError(500, 'The engine is restarting.', '/api/zones/kitchen/restart'))
      .mockResolvedValueOnce({ ...crashed(), state: 'running', error: null })
    const lava = rows(list)[0]
    await userEvent.click(within(lava).getByRole('button', { name: 'Restart' }))
    expect(restart).toHaveBeenCalledWith('kitchen')
    expect(await screen.findByText("Couldn't restart Lava. The engine is restarting.")).toBeInTheDocument()
    // The button is back, and a second try goes through: the zone the server answers is in the store.
    await userEvent.click(within(lava).getByRole('button', { name: 'Restart' }))
    await waitFor(() => expect(crashed().state).toBe('running'))
  })

  it('closes, and goes there, when an action is a link', async () => {
    const { list, router } = await openList()
    await userEvent.click(within(rows(list)[0]).getByRole('link', { name: 'Details' }))
    expect(router.state.location.pathname).toBe('/next/looks/lava')
    expect(screen.queryByRole('dialog', { name: 'Needs attention' })).toBeNull()
  })

  // Phone-State-Problems: a sheet, the count in its heading row, a Close, one action a row.
  it('opens a sheet on the phone, with a Close and one action a row', async () => {
    setViewportWidth(390)
    const { list } = await openList()
    expect(within(list).getByText('5')).toHaveClass('text-signal')
    expect(rows(list).map(actionsOf)).toEqual([
      ['Restart'],
      ['Open Inputs'],
      ['Details'],
      ['Open Inputs'],
      ['Details'],
    ])
    await userEvent.click(within(list).getByRole('button', { name: 'Close' }))
    expect(screen.queryByRole('dialog', { name: 'Needs attention' })).toBeNull()
  })

  // The list follows the server while it's open: an item the server drops goes.
  it('drops an item the server no longer sends', async () => {
    const { list } = await openList()
    act(() => liveStore.setState({ attention: liveStore.getState().attention!.slice(1) }))
    expect(rows(list)).toHaveLength(4)
  })
})
