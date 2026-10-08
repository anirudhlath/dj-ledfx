import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useEffect } from 'react'
import { describe, expect, it, vi } from 'vitest'
import type { Id } from '@/api/contract'
import { lookName } from '@/api/mocks/fixtures'
import { buildScenario } from '@/api/mocks/scenarios'
import { LIVE_RENDER, LIVE_SPEC } from '@/design/live-numbers'
import { payload } from '@/test/icons'
import { HERO_NOW } from '@/test/live'
import { watchScrolling } from '@/test/scroll'
import { ZonePicker, type ZonePickerProps } from './zone-picker'

const hero = buildScenario('hero', HERO_NOW)
const name = (id: Id) => hero.zones.find((zone) => zone.id === id)!.name

function pick(overrides: Partial<ZonePickerProps> = {}) {
  const onSelect = vi.fn()
  const props: ZonePickerProps = {
    zones: hero.zones,
    running: hero.running,
    selected: 'living',
    locked: false,
    onSelect,
    variant: 'desktop',
    ...overrides,
  }
  const { rerender } = render(<ZonePicker {...props} />)
  const group = screen.getByRole('group', { name: 'Where' })
  // A chip's name is the zone's and the note's: it starts with the zone's name.
  const chip = (id: Id) => within(group).getAllByRole('button').find((button) => button.firstChild?.textContent === name(id))!
  /** The zone chosen changes, as the composer's URL changes it. */
  const choose = (selected: Id) => rerender(<ZonePicker {...props} selected={selected} />)
  /** Any props change, as a push from the server changes what runs. */
  const update = (next: Partial<ZonePickerProps>) => rerender(<ZonePicker {...props} {...next} />)
  return { onSelect, group, chip, choose, update }
}

describe('ZonePicker (§6.3)', () => {
  // Live-PutLookOn's Where: the chosen chip inverted, each chip with what runs there.
  it("has a chip for every zone in the server's order, the chosen one inverted, each saying what runs there", () => {
    const { group, chip } = pick()
    const zones = within(group)
      .getAllByRole('button')
      .filter((button) => button.getAttribute('aria-disabled') !== 'true')
    expect(zones.map((button) => button.getAttribute('aria-pressed'))).toEqual(hero.zones.map((zone) => String(zone.id === 'living')))
    expect(chip('living')).toHaveClass('bg-text')
    expect(within(chip('living')).getByText(lookName('fireflies'))).toHaveStyle({ color: LIVE_RENDER.selectedZoneNote.chip })
    // F4 ruling 19: text-2 on the control fill, where the render's text-3 falls short of §14's contrast.
    expect(within(chip('home')).getByText(lookName('homesunset'))).toHaveClass('text-text-2')
    expect(within(chip('office')).getByText(lookName('comets'))).toBeInTheDocument()
    expect(within(chip('counter')).getByText('no lights')).toBeInTheDocument()
  })

  it('chooses a zone', async () => {
    const { onSelect, chip } = pick()
    await userEvent.click(chip('kitchen'))
    expect(onSelect).toHaveBeenCalledWith('kitchen')
  })

  // §8.2: "Home looks (whole-home scope) lock the zone to Whole home."
  it('leaves only the whole home to choose while a home look is chosen', () => {
    const { chip } = pick({ selected: 'home', locked: true })
    expect(chip('home')).toBeEnabled()
    for (const zone of hero.zones.filter((each) => each.kind !== 'home')) expect(chip(zone.id)).toBeDisabled()
  })

  // F4 ruling 6: picking lights has no milestone yet.
  it('draws Pick lights… dashed, and it does nothing', async () => {
    const { onSelect, group } = pick()
    const pickLights = within(group).getByRole('button', { name: 'Pick lights…' })
    expect(pickLights).toHaveAttribute('aria-disabled', 'true')
    expect(pickLights).toHaveClass('border-dashed')
    await userEvent.click(pickLights)
    expect(onSelect).not.toHaveBeenCalled()
  })

  // app.css gives every button that isn't disabled a pointer, and an aria-disabled one isn't; jsdom loads no CSS,
  // so the class that overrides it is what a test can pin.
  it("overrides app.css's pointer on Pick lights… with aria-disabled:cursor-default, since it's inert", () => {
    const { group } = pick()
    expect(within(group).getByRole('button', { name: 'Pick lights…' })).toHaveClass('aria-disabled:cursor-default')
  })

  // Phone-PutLookOn's Where: tall buttons in a row that scrolls. The chosen one leads the row as the
  // composer opens, as drawn; a later choice scrolls only as far as it must.
  it("draws the phone's buttons at LIVE_SPEC.phoneComposer.zonePx and keeps the chosen one in view", () => {
    const scrolled = watchScrolling()
    const { chip, choose } = pick({ variant: 'phone', selected: 'bedroom' })
    expect(chip('bedroom')).toHaveStyle({ height: `${LIVE_SPEC.phoneComposer.zonePx}px` })
    expect(within(chip('bedroom')).getByText(lookName('homesunset'))).toHaveStyle({ color: LIVE_RENDER.selectedZoneNote.button })
    expect(scrolled).toEqual([[chip('bedroom'), { block: 'nearest', inline: 'start' }]])
    choose('kitchen')
    expect(scrolled.slice(1)).toEqual([[chip('kitchen'), { block: 'nearest', inline: 'nearest' }]])
  })

  // Beyond the brief's five: what a mutation pass over the picker found them letting through.

  // F4 ruling 4: "A room never says a sub-zone's look". A sub-zone's lights sit in its room, so the picker has
  // to hand runningOn() every zone, not only the ones it draws.
  it("says a room's own look, never that of a sub-zone in it", () => {
    const { chip } = pick()
    expect(within(chip('bedroom')).getByText(lookName('homesunset'))).toBeInTheDocument()
    expect(within(chip('bedroom')).queryByText(lookName('comets'))).not.toBeInTheDocument()
  })

  // Phone-PutLookOn's "idle" and "no lights".
  it('says idle where nothing runs, and no lights where there are none', () => {
    const { chip } = pick({ running: [] })
    expect(within(chip('living')).getByText('idle')).toBeInTheDocument()
    expect(within(chip('counter')).getByText('no lights')).toBeInTheDocument()
  })

  // §6.3: "the selected chip is inverted": only that one, on both sizes, and only it has a note of its own colour.
  it.each(['desktop', 'phone'] as const)('inverts only the chosen chip on the %s, the others keeping their notes text-2', (variant) => {
    const { chip } = pick({ variant, selected: 'kitchen' })
    const note = (id: Id, text: string) => within(chip(id)).getByText(text)
    expect(chip('kitchen')).toHaveClass('border-text', 'bg-text', 'text-on-text')
    expect(note('kitchen', lookName('homesunset'))).not.toHaveClass('text-text-2')
    for (const id of ['home', 'living', 'office'] as const) {
      expect(chip(id)).toHaveClass('border-line', 'bg-control', 'text-text')
      expect(chip(id)).not.toHaveClass('bg-text')
    }
    expect(note('living', lookName('fireflies'))).toHaveClass('text-text-2')
    expect(note('living', lookName('fireflies')).style.color).toBe('')
  })

  // A home look leaves the others unavailable: disabled, so a click chooses nothing, and faded by the disabled
  // class, which is what a test sees of it (jsdom loads no CSS).
  it('disables the zones a home look leaves out, with the disabled fade, and a click on one chooses nothing', async () => {
    const { onSelect, chip } = pick({ selected: 'home', locked: true })
    expect(chip('kitchen')).toHaveClass('disabled:opacity-45')
    await userEvent.click(chip('kitchen'))
    expect(onSelect).not.toHaveBeenCalled()
  })

  // F4 ruling 6: the chip comes last in the desktop's group, with its plus.
  it("ends the desktop's group with Pick lights… and its plus", () => {
    const { group } = pick()
    const pickLights = within(group).getAllByRole('button').at(-1)!
    expect(pickLights).toHaveAccessibleName('Pick lights…')
    expect(pickLights.querySelector('svg')!.innerHTML).toBe(payload('plus'))
  })

  // Only Live-PutLookOn draws Pick lights…; Phone-PutLookOn's row is the zones alone, and the renders are the
  // layout's authority.
  it("draws no Pick lights… on the phone, and only a button for each zone in its row", () => {
    const { group } = pick({ variant: 'phone' })
    expect(screen.queryByRole('button', { name: 'Pick lights…' })).not.toBeInTheDocument()
    expect(within(group).getAllByRole('button')).toHaveLength(hero.zones.length)
  })

  // §8.2 Where: "zone chips across the top of the stage", wrapping; they're under --touch-min, so their hit
  // areas grow to it (CLAUDE.md: touch-target) and the faces stay as drawn. jsdom has no layout, so these are the
  // classes; that the chips wrap and the hit areas reach the minimum is for the e2e to see.
  it("has the classes that wrap the desktop chips and grow every chip's hit area, Pick lights… too, to the touch minimum", () => {
    const { group } = pick()
    expect(group).toHaveClass('flex-wrap')
    const buttons = within(group).getAllByRole('button')
    expect(buttons).toHaveLength(hero.zones.length + 1)
    for (const button of buttons) expect(button).toHaveClass('touch-target')
  })

  // The brief: the row snaps, so it stops where it should whenever the fonts and the notes land. Each button
  // keeps its width, so the row overflows and scrolls. The row pads, and is pulled back by as much, so it
  // doesn't clip the buttons' focus rings (a scrolling row clips on both axes). jsdom has no layout, so these
  // are the classes; that the rings stay whole, and that the chosen button is whole after a later choice, is for
  // the e2e to see.
  it("has the classes that scroll and snap the phone's row, pad and pull it back for its focus rings, and keep each button's width", () => {
    const { group } = pick({ variant: 'phone' })
    expect(group).toHaveClass('overflow-x-auto', 'snap-x', 'snap-proximity')
    expect(group).toHaveClass('p-1', '-m-1', 'scroll-px-1')
    const buttons = within(group).getAllByRole('button')
    expect(buttons).toHaveLength(hero.zones.length)
    for (const button of buttons) expect(button).toHaveClass('snap-start', 'shrink-0')
  })

  it('never scrolls the desktop chips', () => {
    const scrolled = watchScrolling()
    const { choose } = pick({ selected: 'bedroom' })
    choose('kitchen')
    expect(scrolled).toEqual([])
  })

  // A push from the server changes the notes every few seconds; the row stays where the owner scrolled it.
  it("scrolls the phone's row only when the choice changes, never as what runs does", () => {
    const scrolled = watchScrolling()
    const { update } = pick({ variant: 'phone', selected: 'bedroom' })
    expect(scrolled).toHaveLength(1)
    update({ running: [] })
    expect(scrolled).toHaveLength(1)
  })

  // The row moves before the paint. A composer opened on a zone that isn't first would otherwise paint the row at
  // its start and jump on the next frame, and a later choice would invert its chip a frame before the row moves.
  // A layout effect runs in the commit, ahead of any effect that waits for the paint: one in an earlier sibling is
  // the witness, and it must find the scroll already made.
  it("scrolls the phone's row in the commit, before the effects that wait for the paint", () => {
    const scrolled = watchScrolling()
    const seen: number[] = []
    function AfterPaint() {
      useEffect(() => {
        seen.push(scrolled.length)
      })
      return null
    }
    const props: ZonePickerProps = { zones: hero.zones, running: hero.running, selected: 'bedroom', locked: false, onSelect: vi.fn(), variant: 'phone' }
    const { rerender } = render(
      <>
        <AfterPaint />
        <ZonePicker {...props} />
      </>,
    )
    rerender(
      <>
        <AfterPaint />
        <ZonePicker {...props} selected="kitchen" />
      </>,
    )
    expect(seen).toEqual([1, 2])
  })
})
