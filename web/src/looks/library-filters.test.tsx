import { fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { buildScenario } from '@/api/mocks/scenarios'
import { HERO_NOW } from '@/test/live'
import { renderAt } from '@/test/router'
import { LibraryFilters } from './library-filters'
import { LIBRARY_TABS, tabCounts, type LibraryTab } from './library-model'

// The counts Looks.png draws, worked out from the `library` scenario as the page works them out.
const counts = tabCounts(buildScenario('library', HERO_NOW).looks)

/**
 * The bar as the page holds it: its three choices in state, so a typed search is the whole word and a tab, once pressed, is the pressed
 * one. The spies see each call the bar makes.
 */
function renderBar(start: { tab?: LibraryTab; query?: string; readyOnly?: boolean } = {}) {
  const onTab = vi.fn<(tab: LibraryTab) => void>()
  const onQuery = vi.fn<(query: string) => void>()
  const onReadyOnly = vi.fn<(on: boolean) => void>()
  function Bar() {
    const [tab, setTab] = useState(start.tab ?? 'all')
    const [query, setQuery] = useState(start.query ?? '')
    const [readyOnly, setReadyOnly] = useState(start.readyOnly ?? false)
    return (
      <LibraryFilters
        tab={tab}
        counts={counts}
        query={query}
        readyOnly={readyOnly}
        onTab={(next) => {
          onTab(next)
          setTab(next)
        }}
        onQuery={(next) => {
          onQuery(next)
          setQuery(next)
        }}
        onReadyOnly={(next) => {
          onReadyOnly(next)
          setReadyOnly(next)
        }}
      />
    )
  }
  renderAt('/looks', <Bar />)
  return { onTab, onQuery, onReadyOnly }
}

// §8.4's filter bar: "search (looks, layers, inputs), category tabs with counts, "Only ready now" switch, "New look"".
describe('LibraryFilters (§8.4)', () => {
  it('searches looks, layers and inputs, and Esc clears it', async () => {
    const user = userEvent.setup()
    const { onQuery } = renderBar()
    const box = screen.getByRole('searchbox', { name: 'Search looks' })
    expect(box).toHaveAttribute('placeholder', 'Search looks, layers, inputs')
    await user.type(box, 'fi')
    expect(onQuery).toHaveBeenLastCalledWith('fi')
    expect(box).toHaveValue('fi')
    await user.keyboard('{Escape}')
    expect(onQuery).toHaveBeenLastCalledWith('')
    expect(box).toHaveValue('')
  })

  // The composer's search clears first and leaves the page's Esc alone otherwise: a key it handled is marked (`defaultPrevented`).
  it("handles Esc only while there is something to clear, so a page's own Esc still gets it", () => {
    const { onQuery } = renderBar()
    const box = screen.getByRole('searchbox', { name: 'Search looks' })
    expect(fireEvent.keyDown(box, { key: 'Escape' })).toBe(true)
    expect(onQuery).not.toHaveBeenCalled()

    fireEvent.change(box, { target: { value: 'fi' } })
    expect(fireEvent.keyDown(box, { key: 'Escape' })).toBe(false)
    expect(onQuery).toHaveBeenLastCalledWith('')
  })

  it('shows the search it is given', () => {
    renderBar({ query: 'drop' })
    expect(screen.getByRole('searchbox', { name: 'Search looks' })).toHaveValue('drop')
  })

  it('draws a tab for All, Starred, each category and Mine, each with its count, the chosen one pressed', () => {
    renderBar()
    const group = screen.getByRole('group', { name: 'Categories' })
    const tabs = within(group).getAllByRole('button')
    expect(tabs.map((tab) => tab.textContent)).toEqual(LIBRARY_TABS.map((tab) => `${tab.label}${counts[tab.id]}`))
    expect(within(group).getByRole('button', { name: /^All/ })).toHaveAttribute('aria-pressed', 'true')
    expect(tabs.filter((tab) => tab.getAttribute('aria-pressed') === 'true')).toHaveLength(1)
  })

  it('presses the tab it is given, and chooses another on a click', async () => {
    const user = userEvent.setup()
    const { onTab } = renderBar({ tab: 'tempo' })
    const group = screen.getByRole('group', { name: 'Categories' })
    expect(within(group).getByRole('button', { name: /^Tempo/ })).toHaveAttribute('aria-pressed', 'true')
    expect(within(group).getByRole('button', { name: /^All/ })).toHaveAttribute('aria-pressed', 'false')

    await user.click(within(group).getByRole('button', { name: /^Mine/ }))
    expect(onTab).toHaveBeenCalledExactlyOnceWith('mine')
    expect(within(group).getByRole('button', { name: /^Mine/ })).toHaveAttribute('aria-pressed', 'true')
    expect(within(group).getByRole('button', { name: /^Tempo/ })).toHaveAttribute('aria-pressed', 'false')
  })

  // Looks.png draws the count in text-3, which is below §14's contrast on the chosen tab's control-hover fill (F4 ruling 19): there it is text-2.
  it("keeps the count legible on the chosen tab's fill", () => {
    renderBar()
    const group = screen.getByRole('group', { name: 'Categories' })
    const count = (name: RegExp) => within(group).getByRole('button', { name }).lastElementChild
    expect(count(/^All/)).toHaveClass('font-mono', 'text-text-2')
    expect(count(/^Starred/)).toHaveClass('font-mono', 'text-text-3')
  })

  it('turns Only ready now on and off', async () => {
    const user = userEvent.setup()
    const { onReadyOnly } = renderBar()
    const only = screen.getByRole('switch', { name: 'Only ready now' })
    expect(only).toHaveAttribute('aria-checked', 'false')
    await user.click(only)
    expect(onReadyOnly).toHaveBeenLastCalledWith(true)
    expect(only).toHaveAttribute('aria-checked', 'true')
    await user.click(only)
    expect(onReadyOnly).toHaveBeenLastCalledWith(false)
    expect(only).toHaveAttribute('aria-checked', 'false')
  })

  it('shows the switch it is given as on', () => {
    renderBar({ readyOnly: true })
    expect(screen.getByRole('switch', { name: 'Only ready now' })).toHaveAttribute('aria-checked', 'true')
  })

  it('offers New look, which goes to the editor', () => {
    renderBar()
    expect(screen.getByRole('link', { name: 'New look' })).toHaveAttribute('href', '/next/looks/new')
  })

  // F5 ruling 1: below the phone breakpoint the bar wraps, and the search takes the whole of its row.
  it('wraps on the phone, the search taking the whole row', () => {
    renderBar()
    const search = screen.getByRole('searchbox', { name: 'Search looks' }).closest('label')!
    const left = search.parentElement!
    const bar = left.parentElement!
    expect(bar).toHaveClass('flex-wrap')
    expect(left).toHaveClass('flex-wrap', 'max-md:w-full')
    expect(search).toHaveClass('max-md:w-full')
  })
})
