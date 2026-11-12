import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Look } from '@/api/contract'
import { liveStore } from '@/api/live-store'
import { lookName } from '@/api/mocks/fixtures'
import { buildScenario } from '@/api/mocks/scenarios'
import { queries, queryClient } from '@/api/queries'
import { api, ApiError } from '@/api/rest'
import { missingInputs } from '@/compose/model'
import { LIVE_SPEC } from '@/design/live-numbers'
import { librarySections, looksContext, type LibraryFilter } from '@/looks/library-model'
import { LIBRARY, LOOK_CATEGORIES } from '@/looks/looks-render'
import { renderApp } from '@/test/app'
import { HERO_NOW, restOn, seedLive, startMockServer } from '@/test/live'
import { seedRest } from '@/test/rest'
import { setViewportWidth } from '@/test/viewport'

// The page as Looks.png draws it: the `library` scenario, with the hero's zones running.
const { looks, running } = buildScenario('library', HERO_NOW)
const ALL: LibraryFilter = { tab: 'all', query: '', readyOnly: false, inputs: null }

beforeEach(() => {
  seedRest('library')
  seedLive('library')
})

/** The card of a look, as the grid draws it. */
function card(lookId: string): HTMLElement {
  const found = document.querySelector<HTMLElement>(`[data-look="${lookId}"]`)
  if (found === null) throw new Error(`no card for ${lookId}`)
  return found
}
const shown = () => [...document.querySelectorAll<HTMLElement>('[data-look]')].map((each) => each.dataset.look)
/** The section a heading is the name of. */
const sectionOf = (heading: HTMLElement) => heading.closest('section')!
/** A section's grid of cards, its last child. */
const gridOf = (section: HTMLElement) => section.lastElementChild as HTMLElement

describe('the Looks page (§8.4)', () => {
  it('says how many looks there are and how many zones run', async () => {
    renderApp('/next/looks')
    const line = looksContext(looks, running)
    expect(await within(screen.getByRole('banner')).findByText(line)).toBeInTheDocument()
    expect(line).toBe(`${LIBRARY.counts.All} looks · ${running.length} running`)
  })

  it("draws nothing in the header until the zones that run have been heard of", async () => {
    liveStore.setState({ running: null })
    renderApp('/next/looks')
    await screen.findAllByRole('heading', { level: 2 })
    expect(screen.getByRole('banner')).not.toHaveTextContent(/looks ·/)
    act(() => seedLive('library'))
    expect(await within(screen.getByRole('banner')).findByText(looksContext(looks, running))).toBeInTheDocument()
  })

  it("draws a section per category with its name at §8.4's size, its count and its blurb, then Firmware and Mine", async () => {
    renderApp('/next/looks')
    const headings = await screen.findAllByRole('heading', { level: 2 })
    expect(headings.map((h) => h.textContent)).toEqual(librarySections(looks, ALL).map((s) => s.name))
    expect(headings.map((h) => h.textContent)).toEqual([...LOOK_CATEGORIES.map((category) => category.name), 'Mine'])
    expect(headings[0]).toHaveStyle({ fontSize: `${LIVE_SPEC.looksPage.sectionNamePx}px` })
    expect(headings[0]).toHaveClass('font-serif')
    expect(screen.getByText(LOOK_CATEGORIES[0].blurb)).toBeInTheDocument()
    expect(screen.getByText(LIBRARY.mineBlurb)).toBeInTheDocument()
    // The name, its count and its blurb, on one baseline; Firmware and Mine, the last row's, say no count.
    const [ambient, , , , firmware, mine] = headings
    expect(ambient.parentElement).toHaveClass('flex', 'items-baseline', 'gap-3')
    expect(within(ambient.parentElement!).getByText(String(LIBRARY.counts.Ambient))).toHaveClass('font-mono', 'text-meta', 'text-text-3')
    expect(ambient.parentElement!.children).toHaveLength(3)
    expect(firmware.parentElement!.children).toHaveLength(2)
    expect(mine.parentElement!.children).toHaveLength(2)
  })

  it("lays the cards on §8.4's gaps", async () => {
    renderApp('/next/looks')
    const [ambient] = await screen.findAllByRole('heading', { level: 2 })
    const grid = gridOf(sectionOf(ambient))
    expect(grid).toHaveClass('grid', 'gap-x-4', 'gap-y-7')
    // Tailwind's spacing step is 4 px: gap-y-7 and gap-x-4 are the spec's 28 and 16.
    expect(LIVE_SPEC.looksPage.rowGapPx).toBe(4 * 7)
    expect(LIVE_SPEC.looksPage.columnGapPx).toBe(4 * 4)
    // The columns fill the content width from the card's own width, six at the design's 1288 px (F5 ruling 20), two on the phone.
    expect(grid).toHaveClass('grid-cols-2', 'md:grid-cols-[repeat(auto-fill,minmax(var(--card-min),1fr))]')
    expect(grid.style.getPropertyValue('--card-min')).toBe(`${LIVE_SPEC.lookCard.px}px`)
    expect(LIVE_SPEC.looksPage.columns).toBe(LIVE_SPEC.lookCard.columns)
  })

  it('puts Firmware and Mine side by side in the last row, with fixed-width cards', async () => {
    renderApp('/next/looks')
    const headings = await screen.findAllByRole('heading', { level: 2 })
    const [tempo, firmware, mine] = [headings[1], headings[4], headings[5]].map(sectionOf)
    expect(firmware.parentElement).toBe(mine.parentElement)
    expect(tempo.parentElement).not.toBe(firmware.parentElement)
    expect(firmware.parentElement).toHaveClass('flex', 'md:flex-row', 'md:flex-wrap', 'md:gap-12')
    expect(firmware.parentElement!.children).toHaveLength(2)
    const grid = gridOf(mine)
    expect(grid).toHaveClass('grid', 'grid-cols-2', 'md:flex', 'md:flex-wrap', 'gap-x-4', 'gap-y-7')
    expect(grid.style.getPropertyValue('--card-min')).toBe(`${LIVE_SPEC.lookCard.px}px`)
    for (const wrapper of [...grid.children, ...gridOf(firmware).children]) expect(wrapper).toHaveClass('md:w-(--card-min)')
    // The grid sections' cards are not fixed: they fill their columns.
    for (const wrapper of gridOf(tempo).children) expect(wrapper).not.toHaveClass('md:w-(--card-min)')
  })

  it("keeps the tab and the search in the URL, and replaces a cat it doesn't know (F5 plan, Review Focus 1)", async () => {
    const user = userEvent.setup()
    const router = renderApp('/next/looks?cat=calm&q=fire')
    expect(await screen.findByRole('button', { name: /^All/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('searchbox', { name: 'Search looks' })).toHaveValue('fire')
    await user.click(screen.getByRole('button', { name: /^Tempo/ }))
    expect(router.state.location.search).toBe('?cat=tempo&q=fire')
    expect(screen.getByRole('button', { name: /^Tempo/ })).toHaveAttribute('aria-pressed', 'true')
    // A tab is a step in the history, and All is no cat at all.
    expect(router.state.historyAction).toBe('PUSH')
    await user.click(screen.getByRole('button', { name: /^All/ }))
    expect(router.state.location.search).toBe('?q=fire')
    await user.click(screen.getByRole('button', { name: /^Starred/ }))
    expect(router.state.location.search).toBe('?cat=starred&q=fire')
  })

  it('writes the search as it is typed, replacing the entry and clearing it when it is empty', async () => {
    const user = userEvent.setup()
    const router = renderApp('/next/looks?cat=tempo')
    const search = await screen.findByRole('searchbox', { name: 'Search looks' })
    await user.type(search, 'beat')
    expect(search).toHaveValue('beat')
    expect(router.state.location.search).toBe('?cat=tempo&q=beat')
    expect(router.state.historyAction).toBe('REPLACE')
    expect(router.state.location.search).not.toContain('q=b&')
    await user.clear(search)
    expect(router.state.location.search).toBe('?cat=tempo')
    // The tab's looks hold only Tempo ones, and the search is within it: a Tempo look is found, an Ambient one isn't.
    await user.type(search, 'fire')
    expect(shown()).toEqual([])
    await user.clear(search)
    await user.type(search, 'bursts')
    expect(shown()).toEqual(['bursts'])
  })

  it("takes the search the URL names when it changes under the box, as Back does, and not when the box's own writes come round", async () => {
    const user = userEvent.setup()
    const router = renderApp('/next/looks?q=fire')
    const search = await screen.findByRole('searchbox', { name: 'Search looks' })
    await user.click(screen.getByRole('button', { name: /^Tempo/ }))
    await user.clear(search)
    await user.type(search, 'bursts')
    expect(search).toHaveValue('bursts')
    await act(() => router.navigate(-1))
    expect(router.state.location.search).toBe('?q=fire')
    expect(search).toHaveValue('fire')
    await act(() => router.navigate('/looks'))
    expect(search).toHaveValue('')
  })

  // The router's updates are transitions, so the URL can answer a key after the next one has been typed: that echo must not put the box back.
  // Here the navigations are held and let go after the typing, so the first key's write comes round with the box already at "bu".
  it("doesn't put the box back to the text of its own write that comes round late", async () => {
    const user = userEvent.setup()
    const router = renderApp('/next/looks')
    const search = await screen.findByRole('searchbox', { name: 'Search looks' })
    const navigate = router.navigate as (to: unknown, options?: unknown) => Promise<void>
    const held: Array<() => Promise<void>> = []
    vi.spyOn(router, 'navigate').mockImplementation(((to: unknown, options?: unknown) => {
      held.push(() => navigate(to, options))
      return Promise.resolve()
    }) as typeof router.navigate)
    await user.type(search, 'bu')
    expect(held).toHaveLength(2)
    expect(router.state.location.search).toBe('')
    const bu = librarySections(looks, { ...ALL, query: 'bu' }).flatMap((section) => section.looks.map((look) => look.id))
    await act(() => held[0]!())
    expect(router.state.location.search).toBe('?q=b')
    expect(search).toHaveValue('bu')
    expect(shown()).toEqual(bu)
    await act(() => held[1]!())
    expect(router.state.location.search).toBe('?q=bu')
    expect(search).toHaveValue('bu')
  })

  it("takes a replace that isn't the box's, as it takes any other change of the URL", async () => {
    const router = renderApp('/next/looks?q=fire')
    const search = await screen.findByRole('searchbox', { name: 'Search looks' })
    expect(search).toHaveValue('fire')
    await act(() => router.navigate('/looks?q=bursts', { replace: true }))
    expect(router.state.location.search).toBe('?q=bursts')
    expect(search).toHaveValue('bursts')
    expect(shown()).toEqual(librarySections(looks, { ...ALL, query: 'bursts' }).flatMap((section) => section.looks.map((look) => look.id)))
  })

  it('filters the cards by the search and the tab, as the sections the model draws', async () => {
    renderApp('/next/looks?q=fire')
    await screen.findAllByRole('heading', { level: 2 })
    const ids = (filter: Partial<LibraryFilter>) => librarySections(looks, { ...ALL, ...filter }).flatMap((section) => section.looks.map((look) => look.id))
    expect(ids({ query: 'fire' })).toContain('fireflies')
    expect(shown()).toEqual(ids({ query: 'fire' }))
    expect(shown()).not.toEqual(ids({}))
    expect(screen.getByRole('button', { name: /^Tempo/ })).toHaveAttribute('aria-pressed', 'false')
  })

  it('shows only the looks ready now with the switch on: inputs-down hides those waiting for music or Home Assistant', async () => {
    const user = userEvent.setup()
    seedLive('inputs-down')
    // Stale music holds its last value (§9.3); a source with nothing playing is what a look that needs music waits for.
    const heard = liveStore.getState().inputs!
    liveStore.setState({ inputs: { ...heard, music: { ...heard.music!, state: 'idle', track: null } } })
    const { inputs } = liveStore.getState()
    renderApp('/next/looks')
    await screen.findAllByRole('heading', { level: 2 })
    const waiting = looks.filter((look) => missingInputs(look, inputs).length > 0)
    const ready = looks.filter((look) => missingInputs(look, inputs).length === 0)
    expect(waiting.some((look) => look.needs?.includes('music'))).toBe(true)
    expect(waiting.some((look) => look.needs?.includes('home-assistant'))).toBe(true)
    expect(shown()).toEqual(looks.map((look) => look.id))
    const only = screen.getByRole('switch', { name: 'Only ready now' })
    expect(only).not.toBeChecked()
    await user.click(only)
    expect(only).toBeChecked()
    expect(shown()).toEqual(ready.map((look) => look.id))
    // The switch is the page's, not the URL's (§4.3 names only cat and q).
    await user.click(only)
    expect(shown()).toEqual(looks.map((look) => look.id))
  })

  it('says why there is nothing to show', async () => {
    const user = userEvent.setup()
    const router = renderApp('/next/looks?q=zzzz')
    expect(await screen.findByText('No looks match “zzzz”.')).toBeInTheDocument()
    expect(screen.queryAllByRole('heading', { level: 2 })).toEqual([])
    // The bar stays, so the search can be changed.
    expect(screen.getByRole('searchbox', { name: 'Search looks' })).toHaveValue('zzzz')
    await user.clear(screen.getByRole('searchbox', { name: 'Search looks' }))
    expect(screen.queryByText(/No looks match/)).toBeNull()
    expect(shown()).toHaveLength(looks.length)
    // The hero has no stars and no saved looks.
    act(() => {
      seedRest('hero')
    })
    await act(() => router.navigate('/looks?cat=starred'))
    expect(await screen.findByText('No starred looks yet.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /^Mine/ }))
    expect(await screen.findByText('No saved looks yet.')).toBeInTheDocument()
  })

  // F5 final review, issue 1: the switch's line is only for a switch that hid looks.
  it('blames "Only ready now" only where it hid the looks: an empty tab with the switch on says its own line', async () => {
    const user = userEvent.setup()
    seedLive('inputs-down')
    const heard = liveStore.getState().inputs!
    liveStore.setState({ inputs: { ...heard, music: { ...heard.music!, state: 'idle', track: null } } })
    const { inputs } = liveStore.getState()
    // Built-in and unstarred, so that Starred and Mine hold nothing.
    const waiting = looks.filter((look) => look.builtIn && missingInputs(look, inputs).length > 0).map((look) => ({ ...look, starred: false }))
    expect(waiting.length).toBeGreaterThan(0)
    // The tab's looks all wait for an input: with the switch on, the switch hid them.
    queryClient.setQueryData(queries.looks().queryKey, waiting)
    const router = renderApp('/next/looks')
    await screen.findAllByRole('heading', { level: 2 })
    await user.click(screen.getByRole('switch', { name: 'Only ready now' }))
    expect(await screen.findByText('No looks are ready now.')).toBeInTheDocument()
    expect(shown()).toEqual([])
    // Starred holds no look at all, so the switch hid nothing there, and neither does Mine's.
    await act(() => router.navigate('/looks?cat=starred'))
    expect(await screen.findByText('No starred looks yet.')).toBeInTheDocument()
    expect(screen.queryByText('No looks are ready now.')).toBeNull()
    await user.click(screen.getByRole('button', { name: /^Mine/ }))
    expect(await screen.findByText('No saved looks yet.')).toBeInTheDocument()
    expect(screen.getByRole('switch', { name: 'Only ready now' })).toBeChecked()
    // The search comes first.
    await user.type(screen.getByRole('searchbox', { name: 'Search looks' }), 'zz')
    expect(await screen.findByText('No looks match “zz”.')).toBeInTheDocument()
  })

  it("says when the looks didn't load, and tries again", async () => {
    vi.useFakeTimers()
    // Everything but the looks is seeded, so the page really asks for them.
    queryClient.removeQueries({ queryKey: queries.looks().queryKey, exact: true })
    const failing = vi.spyOn(api, 'looks').mockRejectedValue(new ApiError(500, 'Internal Server Error', '/api/looks'))
    renderApp('/next/looks')
    // One retry, a second on.
    await act(() => vi.advanceTimersByTimeAsync(1500))
    expect(failing).toHaveBeenCalledTimes(2)
    expect(screen.getByText("Couldn't load the looks. Internal Server Error")).toBeInTheDocument()
    expect(screen.queryByRole('searchbox')).toBeNull()
    expect(within(screen.getByRole('banner')).queryByText(/looks ·/)).toBeNull()

    failing.mockResolvedValue(looks)
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    await act(() => vi.advanceTimersByTimeAsync(100))
    expect(failing).toHaveBeenCalledTimes(3)
    expect(screen.queryByText(/Couldn't load the looks/)).toBeNull()
    expect(shown()).toHaveLength(looks.length)
  })

  it('keeps the looks it has when a fetch fails after them, and says nothing is wrong', async () => {
    vi.useFakeTimers()
    const failing = vi.spyOn(api, 'looks').mockRejectedValue(new ApiError(500, 'Internal Server Error', '/api/looks'))
    renderApp('/next/looks')
    expect(screen.getAllByRole('heading', { level: 2 })).not.toHaveLength(0)
    void queryClient.invalidateQueries({ queryKey: queries.looks().queryKey })
    await act(() => vi.advanceTimersByTimeAsync(1500))
    expect(failing).toHaveBeenCalledTimes(2)
    expect(screen.queryByText(/Couldn't load the looks/)).toBeNull()
    expect(shown()).toHaveLength(looks.length)
  })

  it('puts the running zones and the parents on the cards', async () => {
    renderApp('/next/looks')
    await screen.findAllByRole('heading', { level: 2 })
    for (const [lookId, zone] of Object.entries(LIBRARY.running)) {
      expect(within(card(lookId)).getByText(zone)).toBeInTheDocument()
    }
    for (const mine of LIBRARY.mine) {
      expect(within(screen.getByRole('article', { name: mine.name })).getByText(`From ${lookName(mine.from)}`)).toBeInTheDocument()
    }
    // A look that runs nowhere has no pill.
    expect(within(card('sunset')).queryByText(/Running on/)).toBeNull()
  })

  it('names the inputs a card lists, and the one it waits for in signal', async () => {
    seedLive('inputs-down')
    renderApp('/next/looks')
    await screen.findAllByRole('heading', { level: 2 })
    const goodnight = looks.find((look) => look.needs?.includes('home-assistant'))!
    expect(within(card(goodnight.id)).getByText('HA')).toHaveClass('text-signal')
  })

  it('stars a look on the page, asks the server and keeps the look it answers with', async () => {
    const user = userEvent.setup()
    const server = startMockServer({ scenario: 'library' })
    restOn(server)
    // The request goes to the mock server through fetch; its answer is given a mark, so that the cache can show it is the server's look.
    const ask = api.setStarred
    const asked = vi.spyOn(api, 'setStarred').mockImplementation(async (id, starred) => ({ ...(await ask(id, starred)), description: 'as the server has it' }))
    renderApp('/next/looks')
    await screen.findAllByRole('heading', { level: 2 })
    const star = within(card('sunset')).getByRole('button', { name: 'Star Sunset' })
    expect(star).toHaveAttribute('aria-pressed', 'false')
    await user.click(star)
    // The card shows the choice before the server has answered, and the count follows, as the tab says Starred.
    expect(within(card('sunset')).getByRole('button', { name: 'Unstar Sunset' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /^Starred/ })).toHaveTextContent(String(LIBRARY.counts.Starred + 1))
    // The request reached the server, which kept it, and the cache holds the look it answered with.
    expect(asked).toHaveBeenCalledExactlyOnceWith('sunset', true)
    const served = (await asked.mock.results[0]!.value) as Look
    expect(served).toMatchObject({ id: 'sunset', starred: true, description: 'as the server has it' })
    expect((server.handle('GET', '/api/looks').body as Look[]).find((look) => look.id === 'sunset')?.starred).toBe(true)
    const cachedSunset = () => queryClient.getQueryData(queries.looks().queryKey)!.find((look: Look) => look.id === 'sunset')
    await waitFor(() => expect(cachedSunset()).toEqual(served))
  })

  it('says aloud that a star was not saved, and puts it back', async () => {
    const user = userEvent.setup()
    vi.spyOn(api, 'setStarred').mockRejectedValue(new ApiError(500, 'Internal Server Error', '/api/looks/sunset/starred'))
    renderApp('/next/looks')
    await screen.findAllByRole('heading', { level: 2 })
    await user.click(within(card('sunset')).getByRole('button', { name: 'Star Sunset' }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent("Couldn't star Sunset. Internal Server Error"))
    expect(within(card('sunset')).getByRole('button', { name: 'Star Sunset' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('draws the editor under the same title without the library\'s count (M10)', async () => {
    renderApp('/next/looks/fireflies')
    await screen.findByText('Look editor')
    const banner = screen.getByRole('banner')
    expect(within(banner).getByText('Looks')).toBeInTheDocument()
    expect(banner).not.toHaveTextContent(/looks ·/)
  })

  // jsdom measures no layout, so the frame is pinned by its classes: Looks.html's main is the content width between gutters (the phone's
  // are the other phone pages'), with space above and below. <main> also holds Live's full-bleed stage, so it is the page that frames itself.
  it('frames itself: gutters round a content column capped at the content width, centred', async () => {
    renderApp('/next/looks')
    const [ambient] = await screen.findAllByRole('heading', { level: 2 })
    const column = sectionOf(ambient).parentElement!
    expect(column).toHaveClass('mx-auto', 'w-full', 'max-w-(--content-max-w)')
    const gutters = column.parentElement!
    expect(gutters).toHaveClass('px-4', 'md:px-10', 'pt-6', 'pb-10')
    expect(gutters.parentElement).toBe(screen.getByRole('main'))
  })

  it('reflows to two columns on the phone, with no header context', async () => {
    setViewportWidth(390)
    renderApp('/next/looks')
    const [ambient] = await screen.findAllByRole('heading', { level: 2 })
    expect(gridOf(sectionOf(ambient))).toHaveClass('grid-cols-2')
    expect(screen.getByRole('banner')).not.toHaveTextContent(/looks ·/)
  })

  it('adds no live region of its own: the Announcer is the only one', async () => {
    renderApp('/next/looks')
    await screen.findAllByRole('heading', { level: 2 })
    expect(screen.getAllByRole('status')).toHaveLength(1)
  })
})
