import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderApp } from '@/test/app'
import { seedLive } from '@/test/live'
import { seedRest } from '@/test/rest'

describe('FirmwareBreakdown', () => {
  // State-Firmware: the card, then its lights by state.
  it("lists the zone's lights under its card by state, the waveform's eleven folded into one line", () => {
    seedRest('firmware')
    seedLive('firmware')
    renderApp('/next/live')
    const panel = screen.getByRole('complementary', { name: 'Running' })
    const breakdown = within(panel).getByRole('region', { name: 'Lights in Whole home' })
    expect(within(breakdown).getAllByRole('heading').map((heading) => heading.textContent)).toEqual([
      'Own effect',
      'Own effect · waveform',
      'Streamed copy',
    ])
    expect(within(breakdown).getByText('Candle 1').closest('li')).toHaveTextContent('LIFX Flame')
    expect(within(breakdown).getByText('Corner Lamp').closest('li')).toHaveTextContent('Streamed copy of Flame')
    expect(within(breakdown).getByText('11 lights · LIFX waveform')).toBeInTheDocument()
    // Every light has its swatch, its state in its name (§6.6).
    expect(within(breakdown).getAllByRole('img')).toHaveLength(19)
    expect(within(breakdown).getByRole('img', { name: 'Candle 1, running its own effect' })).toBeInTheDocument()
    // State-Firmware: the card draws no swatches of its own while the breakdown has every light's, and the
    // footer says nothing under Put a look on.
    expect(within(within(panel).getByRole('article', { name: 'Whole home — Firmware showcase' })).queryAllByRole('img')).toEqual([])
    expect(within(panel).queryByText('or click a room in the home')).toBeNull()
  })

  it('draws nothing for zones whose lights stream', () => {
    seedRest('hero')
    seedLive('hero')
    renderApp('/next/live')
    expect(screen.queryByRole('region', { name: /^Lights in / })).toBeNull()
    expect(within(screen.getByRole('article', { name: 'Living room — Fireflies' })).getAllByRole('img').length).toBeGreaterThan(0)
  })
})
