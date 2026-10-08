import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { lookFixtures, lookName } from '@/api/mocks/fixtures'
import { queryClient } from '@/api/queries'
import { LIVE_SPEC } from '@/design/live-numbers'
import { seedRest } from '@/test/rest'
import { LookRow } from './look-row'
import { LookTile, type LookTileProps } from './look-tile'

const inQuery = (ui: ReactNode) => render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)

/** A tile's props for a look: not chosen, not running, waiting for nothing. */
function props(id: string, overrides: Partial<LookTileProps> = {}): LookTileProps {
  const look = lookFixtures.find((each) => each.id === id)!
  return { look, selected: false, here: false, missing: [], tabbable: false, onSelect: () => {}, ...overrides }
}

// The thumbs read the looks from REST's cache.
beforeEach(() => {
  seedRest('hero')
})

describe('LookTile (§6.4)', () => {
  // Live-PutLookOn's chosen tile.
  it('says PREVIEWING on the look the stage previews, framed in text', () => {
    inQuery(<LookTile {...props('embers', { selected: true, tabbable: true })} />)
    const tile = screen.getByRole('button', { name: lookName('embers') })
    expect(tile).toHaveAttribute('aria-pressed', 'true')
    expect(tile).toHaveAttribute('tabindex', '0')
    expect(tile).toHaveAttribute('data-look', 'embers')
    const tag = within(tile).getByText('Previewing')
    expect(tag).toHaveClass('bg-text')
    expect(tag.querySelector('svg')).not.toBeNull()
    expect(tile.querySelector('[data-thumb]')).toHaveClass('border-text')
    expect(within(tile).getByText(lookName('embers'))).toHaveStyle({ fontSize: `${LIVE_SPEC.lookTile.namePx}px` })
  })

  // Live-PutLookOn's tile for the look the room runs.
  it('says RUNNING HERE on the look the zone runs', () => {
    inQuery(<LookTile {...props('fireflies', { here: true })} />)
    const tile = screen.getByRole('button', { name: `${lookName('fireflies')}, running here` })
    expect(tile).toHaveAttribute('aria-pressed', 'false')
    expect(tile).toHaveAttribute('tabindex', '-1')
    expect(within(tile).getByText('Running here')).toHaveClass('border-line', 'text-text-2')
    expect(tile.querySelector('[data-thumb]')).toHaveClass('border-line')
  })

  // §8.2: "A look whose input is missing stays selectable; its tile says 'Waits for music' … in signal".
  it('says the input a look would wait for in signal, and still selects', async () => {
    const onSelect = vi.fn()
    inQuery(<LookTile {...props('spectrum', { missing: ['music'], onSelect })} />)
    const tile = screen.getByRole('button', { name: `${lookName('spectrum')}, Waits for music` })
    expect(within(tile).getByText('Waits for music')).toHaveClass('text-signal')
    await userEvent.click(tile)
    expect(onSelect).toHaveBeenCalledOnce()
  })

  // missingInputs() lists them in §6.3's chip order, and a tile says the first.
  it('says only the first of several inputs it would wait for', () => {
    inQuery(<LookTile {...props('goodnight', { missing: ['music', 'home-assistant'] })} />)
    const tile = screen.getByRole('button', { name: `${lookName('goodnight')}, Waits for music` })
    expect(within(tile).getByText('Waits for music')).toHaveClass('text-signal')
    expect(within(tile).queryByText('Needs Home Assistant')).not.toBeInTheDocument()
  })

  // Live-PutLookOn draws the inputs' icons at the right of the name; §8.2's signal is the one it waits for.
  it('draws an icon for each input the look uses, and the one it would wait for in signal', () => {
    inQuery(
      <>
        <LookTile {...props('drop')} />
        <LookTile {...props('drop', { missing: ['music'] })} />
      </>,
    )
    const [tempo, music, ...others] = screen.getByRole('button', { name: lookName('drop') }).querySelectorAll('svg')
    expect(others).toHaveLength(0)
    expect(tempo).toHaveClass('text-text-3')
    expect(music).toHaveClass('text-text-3')
    const waiting = screen.getByRole('button', { name: `${lookName('drop')}, Waits for music` })
    const [tempoStill, musicWaiting, ...rest] = waiting.querySelectorAll('svg')
    expect(rest).toHaveLength(0)
    expect(tempoStill).toHaveClass('text-text-3')
    expect(musicWaiting).toHaveClass('text-signal')
  })

  // The previewed look can also be the one the zone runs: the tag's one place says PREVIEWING.
  it('says PREVIEWING, not RUNNING HERE, on a look that is both, and still tells a screen reader', () => {
    inQuery(<LookTile {...props('fireflies', { selected: true, here: true })} />)
    const tile = screen.getByRole('button', { name: `${lookName('fireflies')}, running here`, pressed: true })
    expect(within(tile).getByText('Previewing')).toBeInTheDocument()
    expect(within(tile).queryByText('Running here')).not.toBeInTheDocument()
  })
})

describe('LookRow (§8.10)', () => {
  // Phone-PutLookOn's first three rows.
  it('frames the chosen row with a check, and says what each row is', () => {
    inQuery(
      <>
        <LookRow {...props('embers', { selected: true })} />
        <LookRow {...props('fireflies', { here: true })} />
        <LookRow {...props('aurora')} />
      </>,
    )
    const chosen = screen.getByRole('button', { name: lookName('embers') })
    expect(chosen).toHaveClass('border-text', 'bg-control')
    expect(chosen.querySelector('[data-thumb]')).toHaveStyle({
      width: `${LIVE_SPEC.phoneComposer.thumb.width}px`,
      height: `${LIVE_SPEC.phoneComposer.thumb.height}px`,
    })
    // F4 ruling 19: on the chosen row's control fill the line is text-2, for §14's contrast.
    expect(within(chosen).getByText('Previewing on screen')).toHaveClass('text-text-2')
    expect(chosen.querySelectorAll('svg')).toHaveLength(1)
    const here = screen.getByRole('button', { name: `${lookName('fireflies')}, running here` })
    expect(within(here).getByText('Running here now')).toBeInTheDocument()
    expect(here).toHaveClass('border-transparent')
    expect(here.querySelectorAll('svg')).toHaveLength(0)
    const plain = screen.getByRole('button', { name: lookName('aurora') })
    expect(within(plain).getByText('Ambient · no input')).toHaveClass('text-text-3')
  })

  // §8.2's signal line on a row, chosen or not; only the list's one tab stop is tabbable (F4 ruling 12).
  it('says the input it would wait for in signal, and still selects', async () => {
    const onSelect = vi.fn()
    inQuery(
      <>
        <LookRow {...props('spectrum', { missing: ['music'], onSelect })} />
        <LookRow {...props('goodnight', { selected: true, missing: ['home-assistant'], tabbable: true })} />
      </>,
    )
    const waiting = screen.getByRole('button', { name: `${lookName('spectrum')}, Waits for music`, pressed: false })
    expect(waiting).toHaveAttribute('tabindex', '-1')
    expect(waiting).toHaveAttribute('data-look', 'spectrum')
    expect(within(waiting).getByText('Waits for music')).toHaveClass('text-signal')
    await userEvent.click(waiting)
    expect(onSelect).toHaveBeenCalledOnce()
    const chosen = screen.getByRole('button', { name: `${lookName('goodnight')}, Needs Home Assistant`, pressed: true })
    expect(chosen).toHaveAttribute('tabindex', '0')
    expect(within(chosen).getByText('Needs Home Assistant')).toHaveClass('text-signal')
    expect(within(chosen).getByText('Needs Home Assistant')).not.toHaveClass('text-text-2')
  })
})
