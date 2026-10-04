import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { liveStore } from '@/api/live-store'
import type { ScenarioName } from '@/api/mocks/scenarios'
import { api, ApiError } from '@/api/rest'
import { renderApp } from '@/test/app'
import { seedLive } from '@/test/live'
import { seedRest } from '@/test/rest'
import { setViewportWidth } from '@/test/viewport'

function openTempo(name: ScenarioName = 'dj-playing') {
  setViewportWidth(390)
  seedRest(name)
  seedLive(name)
  return renderApp('/next/inputs')
}

const main = () => screen.getByRole('main')
const decks = () => within(within(main()).getByRole('region', { name: 'Decks' })).getAllByRole('listitem')

describe("the phone's Tempo (§8.10)", () => {
  // Phone-Tempo.png.
  it("shows the DJ's tempo, TAP and what it does, the decks with the master marked, and the music's note", () => {
    openTempo()
    expect(within(screen.getByRole('banner')).getByRole('heading', { level: 1, name: 'Tempo' })).toBeInTheDocument()
    expect(within(main()).getByText('Pro DJ Link · Deck 2')).toBeInTheDocument()
    expect(within(main()).getByText('125.5')).toBeInTheDocument()
    // The bar and the beat after it are the pip writer's, on the beat clock.
    expect(within(main()).getByText(/^124\.00 \+1\.2%/)).toBeInTheDocument()
    expect(within(main()).getByRole('button', { name: 'Tap' })).toBeEnabled()
    expect(within(main()).getByText('The DJ has the tempo. Tapping takes over with Internal.')).toBeInTheDocument()
    expect(decks().map((deck) => deck.textContent)).toEqual([
      '1Player 1Cued · 126.00 · +0.0%',
      '2Player 2Playing · 124.00 · +1.2%Master',
      '3Deck 3Empty',
      '4Deck 4Empty',
    ])
    expect(within(main()).getByText('Music Assistant: nothing playing. Audio looks wait for music.')).toBeInTheDocument()
    // Phone-Tempo.html sizes them content-box: the drawn row is 54 high, the number's circle 32 across.
    expect(decks()[0]).toHaveClass('min-h-13.5')
    expect(within(decks()[0]).getByText('1')).toHaveClass('size-8')
  })

  // F3 decisions 26 and 40: no DJ heard, and the music playing.
  it("follows the music's beat with four empty decks, and no note while music plays", () => {
    openTempo('hero')
    expect(within(main()).getByText('The music has the tempo. Tapping takes over with Internal.')).toBeInTheDocument()
    expect(decks().map((deck) => deck.textContent)).toEqual(['1Deck 1Empty', '2Deck 2Empty', '3Deck 3Empty', '4Deck 4Empty'])
    expect(within(main()).queryByText(/^Music Assistant:/)).toBeNull()
  })

  // Review Focus 1.
  it('taps the tempo, and says why when the server refuses', async () => {
    openTempo()
    const tap = vi.spyOn(api, 'tap').mockRejectedValue(new ApiError(409, 'The tempo is locked.', '/api/inputs/tempo/tap'))
    await userEvent.click(within(main()).getByRole('button', { name: 'Tap' }))
    expect(tap).toHaveBeenCalledOnce()
    expect(await screen.findByText("Couldn't tap the tempo. The tempo is locked.")).toBeInTheDocument()
  })

  // F3 decision 6: the hold is said in words, with the way back.
  it('says when Internal holds the tempo, and gives it back to Auto', async () => {
    openTempo()
    act(() =>
      liveStore.setState(({ inputs, beat }) => ({
        inputs: { ...inputs!, tempo: { ...inputs!.tempo, source: 'internal', held: true } },
        beat: { ...beat!, source: 'internal' },
      })),
    )
    const setTempo = vi.spyOn(api, 'setTempo').mockResolvedValue({ ...liveStore.getState().inputs!.tempo, source: 'prodjlink', held: false })
    expect(within(main()).getByText('Internal · held')).toBeInTheDocument()
    expect(within(main()).getByText('Internal holds the tempo until a DJ starts again.')).toBeInTheDocument()
    await userEvent.click(within(main()).getByRole('button', { name: 'Back to Auto' }))
    expect(setTempo).toHaveBeenCalledWith({ lock: 'auto' })
  })

  // F3 decision 5: the engine refuses a tap under these locks.
  it('turns TAP off under a Pro DJ Link lock, and says why', () => {
    openTempo()
    act(() => liveStore.setState(({ inputs }) => ({ inputs: { ...inputs!, tempo: { ...inputs!.tempo, lock: 'prodjlink' } } })))
    expect(within(main()).getByRole('button', { name: 'Tap' })).toBeDisabled()
    expect(within(main()).getByText('Locked to Pro DJ Link, so tapping is off.')).toBeInTheDocument()
    expect(within(main()).getByRole('button', { name: 'Back to Auto' })).toBeInTheDocument()
  })

  // F3 decision 40: Back to Auto shows under any lock. Under Internal's a tap still sets the tempo (decision 5).
  it('offers Back to Auto under an Internal lock, and leaves TAP on', async () => {
    openTempo()
    act(() =>
      liveStore.setState(({ inputs, beat }) => ({
        inputs: { ...inputs!, tempo: { ...inputs!.tempo, lock: 'internal', source: 'internal' } },
        beat: { ...beat!, source: 'internal' },
      })),
    )
    const setTempo = vi.spyOn(api, 'setTempo').mockResolvedValue({ ...liveStore.getState().inputs!.tempo, lock: 'auto', source: 'prodjlink' })
    expect(within(main()).getByRole('button', { name: 'Tap' })).toBeEnabled()
    expect(within(main()).getByText('Locked to Internal. Tap along to set the tempo.')).toBeInTheDocument()
    await userEvent.click(within(main()).getByRole('button', { name: 'Back to Auto' }))
    expect(setTempo).toHaveBeenCalledWith({ lock: 'auto' })
  })
})
