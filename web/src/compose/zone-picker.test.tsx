import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, onTestFinished, vi } from 'vitest'
import type { Id } from '@/api/contract'
import { lookName } from '@/api/mocks/fixtures'
import { buildScenario } from '@/api/mocks/scenarios'
import { ICONS } from '@/design/icons'
import { LIVE_RENDER, LIVE_SPEC } from '@/design/live-numbers'
import { HERO_NOW } from '@/test/live'
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

/** Element.scrollIntoView, which jsdom has none of, recorded: the element and the options of each call. */
function watchScrolling() {
  const scrolled: [Element, ScrollIntoViewOptions | boolean | undefined][] = []
  const original = Element.prototype.scrollIntoView
  Element.prototype.scrollIntoView = function (this: Element, options?: ScrollIntoViewOptions | boolean) {
    scrolled.push([this, options])
  }
  onTestFinished(() => void (Element.prototype.scrollIntoView = original))
  return scrolled
}

/** What an icon draws, as the markup a browser serialises. */
function payload(icon: keyof typeof ICONS): string {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
  svg.innerHTML = ICONS[icon]
  return svg.innerHTML
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

  // Phone-PutLookOn's Where: tall buttons in a row that scrolls. The chosen one leads the row as the
  // composer opens, as drawn; a later choice scrolls only as far as it must.
  it("draws the phone's buttons at LIVE_SPEC.phoneComposer.zonePx and keeps the chosen one in view", () => {
    const scrolled: [Element, ScrollIntoViewOptions | boolean | undefined][] = []
    const original = Element.prototype.scrollIntoView
    Element.prototype.scrollIntoView = function (this: Element, options?: ScrollIntoViewOptions | boolean) {
      scrolled.push([this, options])
    }
    onTestFinished(() => void (Element.prototype.scrollIntoView = original))
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

  // A home look leaves the others unavailable, and they say so by fading as well as by being disabled.
  it('fades the zones a home look leaves out, and does not choose them', async () => {
    const { onSelect, chip } = pick({ selected: 'home', locked: true })
    expect(chip('kitchen')).toHaveClass('disabled:opacity-45')
    await userEvent.click(chip('kitchen'))
    expect(onSelect).not.toHaveBeenCalled()
  })

  // F4 ruling 6: the chip comes last in the group, with its plus; on the phone it's as tall as the zones' buttons.
  it.each(['desktop', 'phone'] as const)('ends the group with Pick lights… and its plus on the %s', (variant) => {
    const { group } = pick({ variant })
    const pickLights = within(group).getAllByRole('button').at(-1)!
    expect(pickLights).toHaveAccessibleName('Pick lights…')
    expect(pickLights.querySelector('svg')!.innerHTML).toBe(payload('plus'))
  })

  it("draws the phone's Pick lights… as tall as its zone buttons", () => {
    const { group } = pick({ variant: 'phone' })
    expect(within(group).getByRole('button', { name: 'Pick lights…' })).toHaveStyle({ height: `${LIVE_SPEC.phoneComposer.zonePx}px` })
  })

  // §8.2 Where: "zone chips across the top of the stage", wrapping; they're under --touch-min, so their hit
  // areas grow to it (CLAUDE.md: touch-target) and the faces stay as drawn.
  it("wraps the desktop chips, and grows each one's hit area to the touch minimum", () => {
    const { group } = pick()
    expect(group).toHaveClass('flex-wrap')
    const buttons = within(group).getAllByRole('button')
    expect(buttons).toHaveLength(hero.zones.length + 1)
    for (const button of buttons) expect(button).toHaveClass('touch-target')
  })

  // The brief: the row snaps, so it stops where it should whenever the fonts and the notes land. Each button
  // keeps its width, so the row overflows and scrolls. The row pads, and is pulled back by as much, so it
  // doesn't clip the buttons' focus rings (a scrolling row clips on both axes). jsdom has no layout, so the
  // classes are what a test can pin.
  it("snaps the phone's row, lets its buttons overflow it, and leaves room for their focus rings", () => {
    const { group } = pick({ variant: 'phone' })
    expect(group).toHaveClass('overflow-x-auto', 'snap-x', 'snap-proximity')
    expect(group).toHaveClass('p-1', '-m-1', 'scroll-px-1')
    const buttons = within(group).getAllByRole('button')
    expect(buttons).toHaveLength(hero.zones.length + 1)
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
})
