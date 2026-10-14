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

/** A tile's props for a look: not chosen (and so, if it were, previewed), not running, waiting for nothing. */
function props(id: string, overrides: Partial<LookTileProps> = {}): LookTileProps {
  const look = lookFixtures.find((each) => each.id === id)!
  return { look, selected: false, previewed: true, here: false, missing: [], tabbable: false, onSelect: () => {}, ...overrides }
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

  // WCAG 1.1.1: the icons are aria-hidden and the label replaces what the button holds, so the inputs (and the category,
  // which a search shows no other way) reach a screen reader as the tile's description, in the phone rows' words.
  it('describes its look by its category and inputs, whatever its state', () => {
    inQuery(
      <>
        <LookTile {...props('aurora')} />
        <LookTile {...props('spectrum', { missing: ['music'] })} />
        <LookTile {...props('drop', { selected: true, here: true })} />
      </>,
    )
    const plain = screen.getByRole('button', { name: lookName('aurora') })
    expect(plain).toHaveAccessibleDescription('Ambient · no input')
    // The words are for a screen reader only: the tile draws no such line.
    expect(within(plain).getByText('Ambient · no input')).toHaveClass('sr-only')
    const waiting = screen.getByRole('button', { name: `${lookName('spectrum')}, Waits for music` })
    expect(waiting).toHaveAccessibleDescription('Audio · Music')
    expect(screen.getByRole('button', { name: `${lookName('drop')}, running here` })).toHaveAccessibleDescription('Audio · Tempo · Music')
  })

  // The previewed look can also be the one the zone runs: the tag's one place says PREVIEWING.
  it('says PREVIEWING, not RUNNING HERE, on a look that is both, and still tells a screen reader', () => {
    inQuery(<LookTile {...props('fireflies', { selected: true, here: true })} />)
    const tile = screen.getByRole('button', { name: `${lookName('fireflies')}, running here`, pressed: true })
    expect(within(tile).getByText('Previewing')).toBeInTheDocument()
    expect(within(tile).queryByText('Running here')).not.toBeInTheDocument()
  })
})

// The tag says what the stage shows: a chosen look whose preview is refused (a zone with no lights, any refusal) keeps its frame and its
// aria-pressed, which are the choice, but claims no preview.
describe('a chosen look whose preview is refused', () => {
  it('keeps its frame on a tile and says nothing of previewing', () => {
    inQuery(<LookTile {...props('embers', { selected: true, previewed: false, tabbable: true })} />)
    const tile = screen.getByRole('button', { name: lookName('embers'), pressed: true })
    expect(tile.querySelector('[data-thumb]')).toHaveClass('border-text')
    expect(within(tile).queryByText('Previewing')).not.toBeInTheDocument()
    expect(within(tile).queryByText('Running here')).not.toBeInTheDocument()
  })

  it('shows RUNNING HERE on a tile when it runs on the zone', () => {
    inQuery(<LookTile {...props('fireflies', { selected: true, previewed: false, here: true })} />)
    const tile = screen.getByRole('button', { name: `${lookName('fireflies')}, running here`, pressed: true })
    expect(within(tile).getByText('Running here')).toBeInTheDocument()
    expect(within(tile).queryByText('Previewing')).not.toBeInTheDocument()
  })

  it('keeps its frame and check on a row, with its inputs for the line, or "Running here now"', () => {
    inQuery(
      <>
        <LookRow {...props('embers', { selected: true, previewed: false })} />
        <LookRow {...props('fireflies', { selected: true, previewed: false, here: true })} />
      </>,
    )
    const chosen = screen.getByRole('button', { name: lookName('embers'), pressed: true })
    expect(chosen).toHaveClass('border-text', 'bg-control')
    expect(chosen.querySelectorAll('svg')).toHaveLength(1)
    expect(within(chosen).queryByText('Previewing on screen')).not.toBeInTheDocument()
    expect(within(chosen).getByText('Ambient · no input', { selector: ':not(.sr-only)' })).toHaveClass('text-text-2')
    const running = screen.getByRole('button', { name: `${lookName('fireflies')}, running here`, pressed: true })
    expect(within(running).getByText('Running here now')).toBeInTheDocument()
    expect(within(running).queryByText('Previewing on screen')).not.toBeInTheDocument()
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
    // A row with no state to show has the same words twice: its line, and its description, hidden. The line is the drawn one.
    expect(within(plain).getByText('Ambient · no input', { selector: ':not(.sr-only)' })).toHaveClass('text-text-3')
  })

  // WCAG 1.1.1: the label replaces what the button holds, and it already says a row's state ("running here", the waiting
  // words; aria-pressed says previewed). The line is often that state and would be heard twice, so the description is not
  // the line: it is the look's inputs, the one thing nothing else says (the category shows nowhere else when a search
  // spans every category).
  it("describes each row by its look's category and inputs, whatever its line says", () => {
    inQuery(
      <>
        <LookRow {...props('drop', { selected: true })} />
        <LookRow {...props('spectrum', { here: true })} />
        <LookRow {...props('goodnight', { missing: ['home-assistant'] })} />
        <LookRow {...props('aurora')} />
      </>,
    )
    const previewed = screen.getByRole('button', { name: lookName('drop') })
    expect(within(previewed).getByText('Previewing on screen')).toBeInTheDocument()
    expect(previewed).toHaveAccessibleDescription('Audio · Tempo · Music')
    // The words are for a screen reader only: the line stays as drawn.
    expect(within(previewed).getByText('Audio · Tempo · Music')).toHaveClass('sr-only')
    const running = screen.getByRole('button', { name: `${lookName('spectrum')}, running here` })
    expect(within(running).getByText('Running here now')).toBeInTheDocument()
    expect(running).toHaveAccessibleDescription('Audio · Music')
    const waiting = screen.getByRole('button', { name: `${lookName('goodnight')}, Needs Home Assistant` })
    expect(within(waiting).getByText('Needs Home Assistant')).toBeInTheDocument()
    expect(waiting).toHaveAccessibleDescription('Home · Home Assistant')
    // With no state to show, the line is the inputs, and the description is too.
    expect(screen.getByRole('button', { name: lookName('aurora') })).toHaveAccessibleDescription('Ambient · no input')
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
