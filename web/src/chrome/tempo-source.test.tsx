import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { liveStore } from '@/api/live-store'
import { api, ApiError } from '@/api/rest'
import { Announcer } from '@/design/announcer'
import { seedLive } from '@/test/live'
import { TempoSourcePopover } from './tempo-source'

async function openPopover() {
  render(
    <Announcer news="">
      <TempoSourcePopover trigger={<button type="button">Source</button>} />
    </Announcer>,
  )
  await userEvent.click(screen.getByRole('button', { name: 'Source' }))
  return screen.findByRole('dialog', { name: 'Tempo source' })
}

describe('the tempo source popover', () => {
  // F3 decision 7: §6.7's chain with each source's status, §8.8's sentence, and §11.5's lock.
  it('says where the tempo comes from, and locks a source', async () => {
    seedLive()
    vi.spyOn(api, 'setTempo').mockResolvedValue({ ...liveStore.getState().inputs!.tempo, lock: 'internal' })
    const popover = await openPopover()
    const chain = within(popover).getByRole('group', { name: 'Where the tempo comes from' })
    expect(chain).toHaveTextContent('Pro DJ LinkNo DJ on the network')
    expect(chain).toHaveTextContent('MusicBeat of “Rain”')
    expect(chain).toHaveTextContent('Internal118.0 · tapped 19:10')
    expect(within(chain).getByText('Music').closest('[aria-current]')).toHaveAttribute('aria-current', 'true')
    expect(popover).toHaveTextContent("The first source that's available drives the clock.")
    expect(within(popover).queryByRole('button', { name: 'Back to Auto' })).toBeNull()
    await userEvent.click(within(popover).getByRole('button', { name: 'Internal' }))
    expect(api.setTempo).toHaveBeenCalledWith({ lock: 'internal' })
  })

  // F3 decision 6, and Review Focus 1.
  it('offers Back to Auto while Internal holds, and says why when the server refuses', async () => {
    seedLive('dj-playing')
    liveStore.setState(({ inputs }) => ({ inputs: { ...inputs!, tempo: { ...inputs!.tempo, source: 'internal', held: true } } }))
    vi.spyOn(api, 'setTempo').mockRejectedValue(new ApiError(500, 'The tempo clock is busy', '/api/inputs/tempo'))
    const popover = await openPopover()
    expect(popover).toHaveTextContent('Internal holds the tempo until a DJ starts again.')
    await userEvent.click(within(popover).getByRole('button', { name: 'Back to Auto' }))
    expect(api.setTempo).toHaveBeenCalledWith({ lock: 'auto' })
    expect(await screen.findByRole('status')).toHaveTextContent("Couldn't give the tempo back. The tempo clock is busy")
  })
})
