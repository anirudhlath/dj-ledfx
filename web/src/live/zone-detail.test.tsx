import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { api } from '@/api/rest'
import { renderApp } from '@/test/app'
import { pushFrame, seedLive } from '@/test/live'
import { seedRest } from '@/test/rest'
import { setViewportWidth } from '@/test/viewport'

function openZone(zoneId: string) {
  setViewportWidth(390)
  seedRest('hero')
  seedLive('hero')
  return renderApp(`/next/live/zones/${zoneId}`)
}

const main = () => screen.getByRole('main')
const lights = () => within(main()).getByRole('region', { name: 'Lights · live' })
const row = (name: string) => within(lights()).getByText(name).closest('li')!

describe("the phone's Zone detail (§8.10)", () => {
  // Phone-Zone.png.
  it("shows the zone's look, brightness, Change, Tweak and Off, and its lights, under a header that goes back to Live", () => {
    openZone('living')
    const header = screen.getByRole('banner')
    expect(within(header).getByRole('heading', { level: 1, name: 'Living room' })).toBeInTheDocument()
    expect(within(header).getByRole('link', { name: 'Back' })).toHaveAttribute('href', '/next/live')
    expect(within(main()).getByRole('heading', { name: 'Fireflies' })).toBeInTheDocument()
    expect(within(main()).getByText('Ambient · no input · since 19:05 · 11 lights')).toBeInTheDocument()
    expect(within(main()).getByRole('slider', { name: 'Brightness for Living room' })).toHaveValue('70')
    expect(within(main()).getByRole('link', { name: 'Change' })).toHaveAttribute('href', '/next/live/put?zone=living')
    expect(within(main()).getByRole('link', { name: 'Tweak' })).toHaveAttribute('href', '/next/looks/fireflies')
    expect(within(lights()).getAllByRole('listitem')).toHaveLength(11)
    expect(row('Rope')).toHaveTextContent('Offline since 17:02')
    expect(row('Candle 2')).toHaveTextContent('Switched off elsewhere · rejoins')
  })

  // F3 decision 24.
  it('says whether each streaming light is glowing or waiting, from its frames', () => {
    vi.useFakeTimers()
    openZone('living')
    expect(row('Right Corner Lamp')).toHaveTextContent('waiting')
    pushFrame('rcl', 1, [255, 120, 0])
    act(() => vi.advanceTimersToNextFrame())
    expect(row('Right Corner Lamp')).toHaveTextContent('glowing')
  })

  it('turns the zone off', async () => {
    openZone('living')
    const off = vi.spyOn(api, 'off').mockResolvedValue()
    // Zone detail's Off, not the list's card's (Live's list has one too).
    expect(within(main()).getByRole('heading', { name: 'Fireflies' })).toBeInTheDocument()
    await userEvent.click(within(main()).getByRole('button', { name: 'Turn off Living room' }))
    expect(off).toHaveBeenCalledWith('living')
  })

  // F3 decision 39.
  it('says when the zone has no look of its own, and puts one on there', () => {
    openZone('kitchen')
    expect(within(screen.getByRole('banner')).getByRole('heading', { level: 1, name: 'Kitchen' })).toBeInTheDocument()
    expect(within(main()).getByRole('heading', { name: 'Nothing running' })).toBeInTheDocument()
    expect(within(main()).getByText('Kitchen has no look of its own.')).toBeInTheDocument()
    expect(within(main()).getByRole('link', { name: 'Put a look on' })).toHaveAttribute('href', '/next/live/put?zone=kitchen')
  })
})
