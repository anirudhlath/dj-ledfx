import { act, fireEvent, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Id, Room } from '@/api/contract'
import { frames, previewSession } from '@/api/live'
import { lookName } from '@/api/mocks/fixtures'
import type { MockServer, MockServerOptions } from '@/api/mocks/mock-server'
import { api, ApiError } from '@/api/rest'
import { LIVE_SPEC } from '@/design/live-numbers'
import { renderApp } from '@/test/app'
import { HERO_NOW, pushFrame, restOn, startMockDataLayer } from '@/test/live'
import { resizeObserved } from '@/test/resize'
import { drawn, heroPose, loadedStage, MAIN_STAGE } from '@/test/stage'
import { setViewportWidth } from '@/test/viewport'
import { projectPoint } from '@/stage/camera'
import { lastZone, rememberZone } from './last-zone'
import { ROW_HEIGHT } from './look-row'

// jsdom has no WebGL: src/test/stage.ts's stand-in takes the canvas's place, and the rest of the stage is real.
vi.mock('@/stage/webgl', () => import('@/test/stage').then((stage) => stage.webglMock()))
vi.mock('@/stage/stage-canvas', (importOriginal) => import('@/test/stage').then((stage) => stage.canvasMock(importOriginal)))

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(HERO_NOW)
  // The last zone used is this browser's (F4 ruling 9): each test starts without one.
  localStorage.clear()
})

/** Time for the in-memory socket and the stubbed fetch, which answer in microtasks between the timers. */
const settle = (ms = 1000) => act(() => vi.advanceTimersByTimeAsync(ms))

/**
 * From here the REST reads of `paths` wait for the test to let them go (restOn's stub answers every one at once): the data
 * comes in a different order from the one the app is written for. Returns what lets one go.
 */
function holdReads(paths: readonly string[]) {
  const answer = globalThis.fetch
  const waiting = new Map(
    paths.map((path) => {
      let release = () => {}
      const promise = new Promise<void>((resolve) => (release = resolve))
      return [path, { promise, release }] as const
    }),
  )
  if (waiting.size > 0) {
    vi.stubGlobal('fetch', async (input: URL | string, init?: RequestInit) => {
      await waiting.get(new URL(input).pathname)?.promise
      return answer(input, init)
    })
  }
  return (path: string) => waiting.get(path)!.release()
}

/** The app at `path` on the hero's mock server (or another scenario), REST and socket alike, settled; `held` are REST reads it waits on. */
async function openApp(path: string, options: MockServerOptions = {}, held: readonly string[] = []) {
  const server = startMockDataLayer(options)
  restOn(server)
  const release = holdReads(held)
  const router = renderApp(path)
  await settle()
  return { server, router, release }
}

const composer = () => screen.getByRole('complementary', { name: 'Put a look on' })
const title = () => within(composer()).getByRole('heading', { level: 2 })
const tile = (id: Id) => composer().querySelector<HTMLElement>(`[data-look="${id}"]`)!
const tilesShown = () => [...composer().querySelectorAll<HTMLElement>('[data-look]')].map((each) => each.dataset.look)
const consequenceLine = () => composer().querySelector('[data-consequence]')!
const startButton = (look?: Id) => within(composer()).getByRole('button', { name: look === undefined ? 'Start' : `Start ${lookName(look)}` })
const zoneName = (server: MockServer, id: Id) => server.state.zones.find((zone) => zone.id === id)!.name
/** A mouse press as a browser sends one: Base UI's list picks an option as the button comes up. */
function press(element: HTMLElement) {
  fireEvent.pointerDown(element, { pointerType: 'mouse', button: 0 })
  fireEvent.mouseDown(element, { button: 0 })
  fireEvent.pointerUp(element, { pointerType: 'mouse', button: 0 })
  fireEvent.mouseUp(element, { button: 0 })
  fireEvent.click(element, { button: 0 })
}
const previewCard = () => document.querySelector('[data-preview-card]')
/** A click on a room's label on the stage, where the pointer picks the room. */
function clickRoom(room: Room) {
  const [x, y] = projectPoint(heroPose(), [...room.labelAt, 0])
  fireEvent.click(screen.getByTestId('stage-canvas').parentElement!, { clientX: x, clientY: y })
}
/** From here each preview request waits for the test to let it go: the choices come faster than the answers. */
function holdPreviews() {
  const real = api.startPreview.bind(api)
  const waiting: (() => void)[] = []
  vi.spyOn(api, 'startPreview').mockImplementation(
    (body) => new Promise((resolve, reject) => waiting.push(() => void real(body).then(resolve, reject))),
  )
  return waiting
}
/** What the stage draws a light as, in its first glow: the entries and the frame store written into the canvas's arrays, as the light layer does. */
function glowOf(lightId: Id): number[] {
  const { entries, writer } = drawn.props!
  writer.setEntries(entries)
  writer.write(frames)
  let glow = 0
  for (const entry of entries) {
    if (entry.body.lightId === lightId) return [...writer.glowColours.slice(glow * 3, glow * 3 + 3)].map((value) => +value.toFixed(3))
    glow += entry.body.samples.length
  }
  throw new Error(`The stage draws no ${lightId}`)
}
/** The stream the stage draws a light from. */
const streamOf = (lightId: Id) => drawn.props!.entries.find((entry) => entry.body.lightId === lightId)!.stream
/** From here a Start waits for the test to answer it, and the composer can be left before it is: returns what answers it. */
function holdStart() {
  const real = api.start.bind(api)
  let answer = () => {}
  vi.spyOn(api, 'start').mockImplementation(
    (...request) => new Promise((resolve, reject) => (answer = () => void real(...request).then(resolve, reject))),
  )
  return () => answer()
}
/**
 * From here a step back (navigate(-1)) waits for the test to let it land, as a browser's does: the memory router steps at once, and the
 * page goes on in between. Returns how many have been asked, and what lets them land, in the order they were asked.
 */
function holdStepsBack(router: ReturnType<typeof renderApp>) {
  const navigate = router.navigate.bind(router)
  const waiting: (() => Promise<void>)[] = []
  let holding = true
  vi.spyOn(router, 'navigate').mockImplementation((to, options) => {
    if (!holding || !Object.is(to, -1)) return navigate(to, options)
    waiting.push(() => navigate(-1))
    return Promise.resolve()
  })
  return {
    asked: () => waiting.length,
    land: async () => {
      holding = false
      for (const step of waiting) await step()
    },
  }
}
/**
 * What the consequence line says in the commit that chooses another look or zone: the effect that asks for its preview comes after it,
 * so the preview state is still the last choice's, and the line must say nothing of that. One entry for each preview asked for.
 */
function lineAtEachChoice() {
  const show = previewSession.show.bind(previewSession)
  const seen: (string | null)[] = []
  vi.spyOn(previewSession, 'show').mockImplementation((zoneId, lookId) => {
    seen.push(consequenceLine().textContent)
    show(zoneId, lookId)
  })
  return seen
}
/** A zone's chip in Where, by the zone's name (a chip's name runs on into its note). */
const chip = (name: string) =>
  within(screen.getByRole('group', { name: 'Where' }))
    .getAllByRole('button')
    .find((button) => button.firstChild?.textContent === name)!
const category = (name: string) => within(screen.getByRole('group', { name: 'Categories' })).getByRole('button', { name })
/** §8.2's four ways out of the composer, each as the click or the key that makes it. */
const EXITS = [
  ['Cancel', () => fireEvent.click(within(composer()).getByRole('button', { name: 'Cancel' }))],
  ['Close', () => fireEvent.click(within(composer()).getByRole('button', { name: 'Close' }))],
  ['Esc', () => expect(fireEvent.keyDown(document.body, { key: 'Escape' })).toBe(false)],
  ['Start', () => fireEvent.click(within(composer()).getByRole('button', { name: /^Start / }))],
] as const

describe('Put a look on (§8.2)', () => {
  // §13.1 F4's exit check: "Start a look in ≤ 3 clicks from Live; lights unchanged until Start (mock asserts)".
  it('starts a look in three clicks from Live, and leaves the lights alone until Start', async () => {
    const { server, router } = await openApp('/next/live')
    const running = structuredClone(server.state.running)
    const lights = structuredClone(server.state.lights)
    const home = server.state.zones.find((zone) => zone.kind === 'home')!
    // The whole home runs a home look, so the composer opens on the home looks (F4 ruling 10).
    const look = server.state.looks.find((each) => each.category === 'home' && each.id !== 'homesunset')!

    fireEvent.click(screen.getByRole('link', { name: 'Put a look on' }))
    await settle()
    expect(router.state.location.pathname).toBe('/next/live/put')
    expect(screen.queryByRole('complementary', { name: 'Running' })).not.toBeInTheDocument()
    expect(title()).toHaveTextContent(`Put a look on ${home.name}`)

    fireEvent.click(tile(look.id))
    await settle()
    expect(previewSession.snapshot()).toMatchObject({ status: 'on', zoneId: home.id, lookId: look.id })
    expect(server.state.running).toEqual(running)
    expect(server.state.lights).toEqual(lights)

    fireEvent.click(startButton(look.id))
    await settle()
    expect(server.state.running.find((zone) => zone.zoneId === home.id)?.lookId).toBe(look.id)
    expect(router.state.location.pathname).toBe('/next/live')
    expect(screen.getByRole('status')).toHaveTextContent(`Started ${look.name} on ${home.name}.`)
    expect(previewSession.snapshot().status).toBe('idle')
  })

  // §4.3: the zone and the look are the URL's, changed in place, so Back leaves the composer whole.
  it('keeps the zone and the look in its URL, previews the look on the stage, and says what Start would do', async () => {
    const { server, router } = await openApp('/next/live/put?zone=living')
    await loadedStage()
    act(() => resizeObserved(MAIN_STAGE.width, MAIN_STAGE.height))
    const living = zoneName(server, 'living')
    expect(title()).toHaveTextContent(`Put a look on ${living}`)
    expect(document.querySelector('[data-outline]')).toHaveAttribute('data-outline', 'living')

    fireEvent.click(tile('embers'))
    await settle()
    expect(router.state.location.search).toBe('?zone=living&look=embers')
    expect(router.state.historyAction).toBe('REPLACE')
    expect(tile('embers')).toHaveAttribute('aria-pressed', 'true')
    expect(document.querySelector('[data-preview-card]')).toHaveTextContent(`${lookName('embers')} on ${living}.`)
    expect(consequenceLine()).toHaveTextContent(new RegExp(`^Takes over the ${living} from ${lookName('fireflies')}\\. `))
    expect(startButton('embers')).toBeEnabled()

    // A room's chip chooses its zone, keeping the look.
    const kitchen = zoneName(server, 'kitchen')
    fireEvent.click(chip(kitchen))
    await settle()
    expect(router.state.location.search).toBe('?zone=kitchen&look=embers')
    expect(router.state.historyAction).toBe('REPLACE')
    expect(title()).toHaveTextContent(`Put a look on ${kitchen}`)
    expect(consequenceLine()).toHaveTextContent(new RegExp(`^Takes over the ${kitchen} from ${lookName('homesunset')}\\.`))

    // Start remembers the zone: the composer opens on it next time.
    fireEvent.click(startButton('embers'))
    await settle()
    expect(router.state.location.pathname).toBe('/next/live')
    fireEvent.click(screen.getByRole('link', { name: 'Put a look on' }))
    await settle()
    expect(title()).toHaveTextContent(`Put a look on ${kitchen}`)
    // Live's own hook, which the stage reads, outlived the first session: it must choose the new last zone too.
    expect(document.querySelector('[data-outline]')).toHaveAttribute('data-outline', 'kitchen')
  })

  // ZonePicker calls onSelect for the chip already chosen: that's no choice, so nothing is asked for and the URL stays.
  it('ignores a click on the zone already chosen', async () => {
    const ask = vi.spyOn(api, 'startPreview')
    const { server, router } = await openApp('/next/live/put?look=embers')
    const home = server.state.zones.find((zone) => zone.kind === 'home')!
    expect(title()).toHaveTextContent(`Put a look on ${home.name}`)
    expect(router.state.historyAction).toBe('POP')
    const asked = ask.mock.calls.length

    fireEvent.click(chip(home.name))
    await settle()
    expect(router.state.historyAction).toBe('POP')
    expect(router.state.location.search).toBe('?look=embers')
    expect(ask).toHaveBeenCalledTimes(asked)
  })

  it('holds Start until a look is chosen, and on a zone with no lights', async () => {
    const ask = vi.spyOn(api, 'startPreview')
    const { server, router } = await openApp('/next/live/put?zone=living')
    expect(consequenceLine()).toHaveTextContent('Choose a look to see it on the stage first.')
    expect(startButton()).toBeDisabled()

    await act(() => router.navigate('/live/put?zone=counter&look=embers', { replace: true }))
    await settle()
    expect(consequenceLine()).toHaveTextContent(`The ${zoneName(server, 'counter')} has no lights.`)
    expect(startButton('embers')).toBeDisabled()
    expect(ask).not.toHaveBeenCalled()
  })

  // A link can name a zone or a look the server hasn't got (one deleted since). The zone falls back as a missing ?zone= does, the last one
  // started on, else the whole home; and a choice made in place doesn't carry the stale id on.
  it('falls back to the whole home for a zone the server has not got, and a pick writes a URL without it', async () => {
    const { server, router } = await openApp('/next/live/put?zone=gone&look=embers')
    const home = server.state.zones.find((zone) => zone.kind === 'home')!
    expect(title()).toHaveTextContent(`Put a look on ${home.name}`)
    expect(chip(home.name)).toHaveAttribute('aria-pressed', 'true')
    expect(previewSession.snapshot()).toMatchObject({ zoneId: home.id, lookId: 'embers' })
    fireEvent.click(tile('rain'))
    await settle()
    expect(router.state.location.search).toBe('?look=rain')
  })

  it('falls back to the last zone started on for a zone the server has not got', async () => {
    rememberZone('kitchen')
    const { server } = await openApp('/next/live/put?zone=gone&look=embers')
    expect(title()).toHaveTextContent(`Put a look on ${zoneName(server, 'kitchen')}`)
    expect(previewSession.snapshot()).toMatchObject({ zoneId: 'kitchen', lookId: 'embers' })
  })

  it('draws no preview for a look the server has not got and holds Start, and a choice writes a URL without it', async () => {
    const ask = vi.spyOn(api, 'startPreview')
    const start = vi.spyOn(api, 'start')
    const { server, router } = await openApp('/next/live/put?zone=living&look=gone')
    expect(title()).toHaveTextContent(`Put a look on ${zoneName(server, 'living')}`)
    expect(ask).not.toHaveBeenCalled()
    expect(previewSession.snapshot().status).toBe('idle')
    expect(consequenceLine()).toHaveTextContent('Choose a look to see it on the stage first.')
    expect(startButton()).toBeDisabled()
    expect(tilesShown().filter((id) => tile(id as Id).getAttribute('aria-pressed') === 'true')).toEqual([])
    // Enter on a look that isn't chosen only chooses it.
    fireEvent.keyDown(tile('rain'), { key: 'Enter' })
    expect(start).not.toHaveBeenCalled()

    fireEvent.click(chip(zoneName(server, 'kitchen')))
    await settle()
    expect(router.state.location.search).toBe('?zone=kitchen')
    // The kitchen runs a home look, so the grid opens on the home looks.
    fireEvent.click(category('Ambient'))
    fireEvent.click(tile('rain'))
    await settle()
    expect(router.state.location.search).toBe('?zone=kitchen&look=rain')
    expect(ask).toHaveBeenCalledTimes(1)
    expect(startButton('rain')).toBeEnabled()
  })

  // §8.2: "Home looks (whole-home scope) lock the zone to Whole home."
  it('locks the zone to the whole home for a home look', async () => {
    const { server } = await openApp('/next/live/put?zone=living&look=goodnight')
    const home = server.state.zones.find((zone) => zone.kind === 'home')!
    expect(title()).toHaveTextContent(`Put a look on ${home.name}`)
    expect(chip(home.name)).toBeEnabled()
    expect(chip(zoneName(server, 'living'))).toBeDisabled()
    expect(previewSession.snapshot()).toMatchObject({ zoneId: home.id, lookId: 'goodnight' })
  })

  // F4 ruling 10: a search spans every category; a category's chip clears it.
  it('searches every category, and a category clears the search', async () => {
    const { server } = await openApp('/next/live/put?zone=living&look=embers')
    const categories = screen.getByRole('group', { name: 'Categories' })
    expect(within(categories).getByRole('button', { name: 'Ambient' })).toHaveAttribute('aria-pressed', 'true')
    const search = within(composer()).getByRole('searchbox', { name: 'Search looks' })
    expect(search).toHaveAttribute('placeholder', `Search ${server.state.looks.length} looks`)

    fireEvent.change(search, { target: { value: lookName('comets') } })
    expect(tilesShown()).toEqual(['comets'])
    expect(within(categories).queryByRole('button', { pressed: true })).not.toBeInTheDocument()
    fireEvent.change(search, { target: { value: 'zzzz' } })
    expect(composer()).toHaveTextContent('No looks match “zzzz”.')
    // Esc clears a search first, and the composer stays.
    fireEvent.keyDown(search, { key: 'Escape' })
    expect(search).toHaveValue('')
    expect(composer()).toBeInTheDocument()

    fireEvent.change(search, { target: { value: 'zzzz' } })
    fireEvent.click(within(categories).getByRole('button', { name: 'Tempo' }))
    expect(search).toHaveValue('')
    expect(tilesShown()).toEqual(server.state.looks.filter((each) => each.category === 'tempo').map((each) => each.id))
    fireEvent.click(within(categories).getByRole('button', { name: 'Starred' }))
    expect(composer()).toHaveTextContent('No starred looks yet.')
  })

  // The box is 38 px of icon and padding round the input, and a pointer lands on any of it: the whole face is the input's label, and a
  // browser focuses a label's control on a click. (jsdom forwards the click to the control, and leaves the focus to the browser.)
  it('makes the whole face of the search box its label, so a click on the icon reaches the input', async () => {
    await openApp('/next/live/put?zone=living&look=embers')
    const search = within(composer()).getByRole<HTMLInputElement>('searchbox', { name: 'Search looks' })
    expect(search.labels).toHaveLength(1)
    const face = search.labels![0]!
    const icon = face.querySelector('svg')!
    const clicked = vi.fn()
    search.addEventListener('click', clicked)
    fireEvent.click(icon)
    fireEvent.click(face)
    expect(clicked).toHaveBeenCalledTimes(2)
  })

  // The row clips (as drawn), so the browser's scroll to a focused chip, which no wheel or touch can undo, would leave the first
  // chip cut: it goes back to its start once focus has left the row, and stays put while focus moves between its chips.
  it('puts the categories row back at its start once focus leaves it', async () => {
    await openApp('/next/live/put?zone=living&look=embers')
    const categories = screen.getByRole('group', { name: 'Categories' })
    const chips = within(categories).getAllByRole('button')
    const last = chips[chips.length - 1]!
    last.focus()
    categories.scrollLeft = 36
    fireEvent.blur(last, { relatedTarget: chips[0] })
    expect(categories.scrollLeft).toBe(36)
    fireEvent.blur(last, { relatedTarget: tile('embers') })
    expect(categories.scrollLeft).toBe(0)
    categories.scrollLeft = 12
    fireEvent.blur(chips[0]!, { relatedTarget: null })
    expect(categories.scrollLeft).toBe(0)
  })

  // F4 ruling 12.
  it('opens on L, chooses on the arrows, starts on Enter and closes on Esc', async () => {
    const { server, router } = await openApp('/next/live')
    // Not while typing, and not with a modifier: Ctrl+L is the browser's.
    const typing = document.body.appendChild(document.createElement('input'))
    fireEvent.keyDown(typing, { key: 'l' })
    fireEvent.keyDown(document.body, { key: 'l', ctrlKey: true })
    typing.remove()
    expect(router.state.location.pathname).toBe('/next/live')

    fireEvent.keyDown(document.body, { key: 'l' })
    await settle()
    expect(router.state.location.pathname).toBe('/next/live/put')
    // The focus is on the first look; the grid has two looks a row.
    const shown = tilesShown()
    expect(document.activeElement).toBe(tile(shown[0]!))
    fireEvent.keyDown(document.activeElement!, { key: 'ArrowRight' })
    expect(router.state.location.search).toBe(`?look=${shown[1]}`)
    expect(document.activeElement).toBe(tile(shown[1]!))
    fireEvent.keyDown(document.activeElement!, { key: 'ArrowDown' })
    expect(document.activeElement).toBe(tile(shown[3]!))
    fireEvent.keyDown(document.activeElement!, { key: 'ArrowUp' })
    expect(router.state.location.search).toBe(`?look=${shown[1]}`)
    await settle()

    fireEvent.keyDown(document.activeElement!, { key: 'Enter' })
    await settle()
    expect(router.state.location.pathname).toBe('/next/live')
    const home = server.state.zones.find((zone) => zone.kind === 'home')!
    expect(server.state.running.find((zone) => zone.zoneId === home.id)?.lookId).toBe(shown[1])

    // Esc closes it from anywhere on the page: Where's chips sit on the stage, outside the panel.
    fireEvent.keyDown(document.body, { key: 'l' })
    await settle()
    fireEvent.keyDown(chip(home.name), { key: 'Escape' })
    await settle()
    expect(router.state.location.pathname).toBe('/next/live')
  })

  it('says why Start failed, and stays open', async () => {
    vi.spyOn(api, 'start').mockRejectedValue(new ApiError(503, 'The engine is busy', '/api/zones/living/start'))
    const { router } = await openApp('/next/live/put?zone=living&look=embers')
    fireEvent.click(startButton('embers'))
    await settle()
    expect(screen.getByRole('status')).toHaveTextContent(`Couldn't start ${lookName('embers')}. The engine is busy`)
    expect(router.state.location.pathname).toBe('/next/live/put')
    expect(startButton('embers')).toBeEnabled()
  })

  // F4 ruling 3: the engine refuses a whole-home look until M6 (the mock plays one, so a refusal stands in).
  it('says why the preview was refused, and leaves Start to try', async () => {
    vi.spyOn(api, 'startPreview').mockRejectedValue(new ApiError(400, 'Home looks (whole-home scope) arrive in M6', '/api/preview'))
    await openApp('/next/live/put?look=goodnight')
    expect(consequenceLine()).toHaveTextContent(`Couldn't preview ${lookName('goodnight')}. Home looks (whole-home scope) arrive in M6`)
    expect(startButton('goodnight')).toBeEnabled()
  })

  // F4 ruling 11: the look's own transition unless another is chosen, and it's sent with Start.
  it('starts with the transition chosen', async () => {
    const start = vi.spyOn(api, 'start')
    await openApp('/next/live/put?zone=living&look=embers')
    const transition = within(composer()).getByRole('combobox', { name: 'Transition' })
    expect(transition).toHaveTextContent('Cut')
    fireEvent.click(transition)
    await settle(100)
    press(screen.getByRole('option', { name: 'Fade · 3 s' }))
    await settle(100)
    expect(transition).toHaveTextContent('Fade · 3 s')
    fireEvent.click(startButton('embers'))
    await settle()
    expect(start).toHaveBeenCalledWith('living', { lookId: 'embers', transition: { kind: 'fade', durationS: 3 } })
  })

  // Review focus 1: choices outrun the server. The stage and the consequence line follow the look chosen last, and
  // never an answer that came late: a look's answer lands after the next look was chosen, and says nothing.
  it('follows the look chosen last, and never an answer that came late', async () => {
    const { server } = await openApp('/next/live/put?zone=living&look=embers')
    await loadedStage()
    act(() => resizeObserved(MAIN_STAGE.width, MAIN_STAGE.height))
    const living = zoneName(server, 'living')
    const card = previewCard
    const waiting = holdPreviews()

    // A firmware look, which says what its lights will run once its answer lands, then a look that says nothing of the kind.
    fireEvent.click(category('Firmware'))
    fireEvent.click(tile('firmware'))
    await settle(100)
    fireEvent.click(category('Ambient'))
    fireEvent.click(tile('rain'))
    await settle(100)
    expect(waiting).toHaveLength(1)
    expect(card()).toHaveTextContent(`${lookName('rain')} on ${living}.`)

    // The first look's answer comes late: the server plays it now, and the stage still follows the look chosen last.
    waiting.shift()!()
    await settle(100)
    expect(waiting).toHaveLength(1)
    expect(card()).toHaveTextContent(`${lookName('rain')} on ${living}.`)
    expect(card()).not.toHaveTextContent(lookName('firmware'))
    expect(consequenceLine()).not.toHaveTextContent(/will (run|get)/)

    waiting.shift()!()
    await settle(100)
    expect(previewSession.snapshot()).toMatchObject({ status: 'on', zoneId: 'living', lookId: 'rain' })
    expect(card()).toHaveTextContent(`${lookName('rain')} on ${living}.`)
    expect(consequenceLine()).not.toHaveTextContent(/will (run|get)/)
  })

  // RF1: choices outrun the server too, and it plays the look of an answer that comes late, its frames on the preview stream for a round trip and
  // sometimes ahead of the answer. The zone keeps the last frame it drew until the look chosen last is answered, then draws that look.
  it("holds the last frame a zone drew while a look chosen over is answered, and draws the look chosen last once it is", async () => {
    const { server } = await openApp('/next/live/put?zone=living&look=embers')
    await loadedStage()
    act(() => resizeObserved(MAIN_STAGE.width, MAIN_STAGE.height))
    const living = server.state.zones.find((zone) => zone.id === 'living')!
    const light = drawn.props!.entries.find((entry) => living.lights.includes(entry.body.lightId))!.body.lightId
    const stored = () => frames.get(light, 'preview')!.seq
    const waiting = holdPreviews()

    // Two looks chosen before the server has answered the first.
    fireEvent.click(tile('rain'))
    fireEvent.click(tile('snow'))
    await settle(100)
    expect(waiting).toHaveLength(1)
    const held = { seq: stored(), glow: glowOf(light) }
    expect(streamOf(light)).toBe('preview')

    // The first look's frames come ahead of its answer, and then its answer comes: the server plays it, and the stage keeps the frame it had.
    pushFrame(light, 9_000_000, [255, 0, 0], { stream: 'preview' })
    expect(glowOf(light)).toEqual(held.glow)
    waiting.shift()!()
    await settle(200)
    expect(waiting).toHaveLength(1)
    expect(stored()).toBe(held.seq)
    expect(glowOf(light)).toEqual(held.glow)
    expect(streamOf(light)).toBe('preview')
    expect(previewSession.snapshot()).toMatchObject({ status: 'starting', lookId: 'snow', showing: 'living' })

    // The look chosen last is answered, and its frames are drawn.
    waiting.shift()!()
    await settle(200)
    expect(previewSession.snapshot()).toMatchObject({ status: 'on', lookId: 'snow', showing: 'living' })
    expect(stored()).toBeGreaterThan(held.seq)
    pushFrame(light, 9_000_001, [0, 0, 255], { stream: 'preview' })
    expect(glowOf(light)).toEqual([0, 0, 1])
  })

  it('draws nothing of a look chosen over on a zone that was not previewed yet', async () => {
    const { server } = await openApp('/next/live/put?zone=living')
    await loadedStage()
    act(() => resizeObserved(MAIN_STAGE.width, MAIN_STAGE.height))
    const living = server.state.zones.find((zone) => zone.id === 'living')!
    const light = drawn.props!.entries.find((entry) => living.lights.includes(entry.body.lightId))!.body.lightId
    const waiting = holdPreviews()

    fireEvent.click(tile('rain'))
    fireEvent.click(tile('snow'))
    await settle(100)
    // Nothing is previewed on the zone yet, so it is drawn from the live stream, and the preview stream has none of its own.
    expect(streamOf(light)).toBe('live')
    pushFrame(light, 9_000_000, [255, 0, 0], { stream: 'preview' })
    waiting.shift()!()
    await settle(200)
    expect(waiting).toHaveLength(1)
    expect(frames.get(light, 'preview')).toBeUndefined()
    expect(streamOf(light)).toBe('live')

    waiting.shift()!()
    await settle(200)
    expect(previewSession.snapshot()).toMatchObject({ status: 'on', lookId: 'snow', showing: 'living' })
    expect(streamOf(light)).toBe('preview')
    pushFrame(light, 9_000_001, [0, 0, 255], { stream: 'preview' })
    expect(glowOf(light)).toEqual([0, 0, 1])
  })

  // Review focus 3: Back leaves the composer as Cancel does, and the preview ends with it.
  it('ends the preview when Back leaves', async () => {
    const stop = vi.spyOn(api, 'stopPreview')
    const { router } = await openApp('/next/live')
    await act(() => router.navigate('/live/put?zone=living&look=embers'))
    await settle()
    expect(previewSession.snapshot()).toMatchObject({ status: 'on', zoneId: 'living', lookId: 'embers' })
    await act(() => router.navigate(-1))
    await settle()
    expect(router.state.location.pathname).toBe('/next/live')
    expect(stop).toHaveBeenCalledTimes(1)
    expect(previewSession.snapshot().status).toBe('idle')
  })

  // Review focus 5: the transition's list opens outside the panel; an Esc there closes the list alone.
  it('closes only the transition list on an Esc in it', async () => {
    const { router } = await openApp('/next/live/put?zone=living&look=embers')
    const transition = within(composer()).getByRole('combobox', { name: 'Transition' })
    fireEvent.click(transition)
    await settle(100)
    expect(screen.getByRole('listbox')).toContainElement(document.activeElement as HTMLElement)
    fireEvent.keyDown(document.activeElement!, { key: 'Escape' })
    await settle(100)
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/next/live/put')

    fireEvent.keyDown(transition, { key: 'Escape' })
    await settle()
    expect(router.state.location.pathname).toBe('/next/live')
  })

  // CLAUDE.md: a control drawn under --touch-min keeps its face and grows its hit area (touch-target). The categories' row clips, so
  // it pads on its left, top and bottom, and is pulled back by as much, to leave room for a chip's focus ring and that area. jsdom has
  // no layout, so this checks the classes; that the area reaches 44 px and the ring stays whole is for a browser to see (Task 10's e2e).
  it('marks each control drawn under the touch minimum with the touch-target class, and pads the categories row for it', async () => {
    await openApp('/next/live/put?zone=living&look=embers')
    const panel = within(composer())
    const categories = panel.getByRole('group', { name: 'Categories' })
    const chips = within(categories).getAllByRole('button')
    expect(chips.length).toBeGreaterThan(1)
    const face = panel.getByRole<HTMLInputElement>('searchbox', { name: 'Search looks' }).labels![0]!
    for (const each of [...chips, face, panel.getByRole('button', { name: 'Close' }), panel.getByRole('combobox', { name: 'Transition' })]) {
      expect(each).toHaveClass('touch-target')
    }
    expect(categories).toHaveClass('overflow-hidden', '-ml-1', '-my-2', 'pl-1', 'py-2', 'scroll-px-1')
    expect(categories).not.toHaveClass('-mx-1', 'px-1')
  })
})

// What the brief's tests above leave to the wiring: the stage's mode, the keys' edges, the grid's edges, the inputs, and the narrow layout.
describe('Put a look on: its stage, keys, grid and layout', () => {
  // F4 ruling 16: the stage is Live's own until the composer asks for it, and Live's again once it closes; the page is Live to the shell.
  it("draws Live's own stage until the composer opens and after it closes, and is Live to the shell", async () => {
    const { router } = await openApp('/next/live')
    await loadedStage()
    act(() => resizeObserved(MAIN_STAGE.width, MAIN_STAGE.height))
    expect(document.querySelector('[data-outline]')).toBeNull()
    expect(previewCard()).toBeNull()

    await act(() => router.navigate('/live/put?zone=living&look=embers'))
    await settle()
    expect(document.querySelector('[data-outline]')).toHaveAttribute('data-outline', 'living')
    expect(document.title).toBe('Live · dj-ledfx')
    expect(screen.getByRole('banner')).toHaveTextContent('Wed 23 Sep · 19:14')

    fireEvent.click(within(composer()).getByRole('button', { name: 'Cancel' }))
    await settle()
    expect(document.querySelector('[data-outline]')).toBeNull()
    expect(previewCard()).toBeNull()
  })

  // A card the pointer is over goes with the Running panel when the composer takes its place: no pointer-leave comes, and the stage
  // must not outline that zone once Live is back.
  it('outlines no zone for a card the pointer was over when the composer opened', async () => {
    const { server } = await openApp('/next/live')
    await loadedStage()
    act(() => resizeObserved(MAIN_STAGE.width, MAIN_STAGE.height))
    fireEvent.pointerOver(screen.getByRole('article', { name: new RegExp(`^${zoneName(server, 'living')}`) }))
    expect(document.querySelector('[data-outline]')).toHaveAttribute('data-outline', 'living')
    fireEvent.keyDown(document.body, { key: 'l' })
    await settle()
    fireEvent.keyDown(document.body, { key: 'Escape' })
    await settle()
    expect(document.querySelector('[data-outline]')).toBeNull()
  })

  // §6.3: "Clicking a room on the stage selects the same zone": the composer's look goes with the click.
  it("chooses a room's zone from the stage, keeping the look the composer has", async () => {
    const { server, router } = await openApp('/next/live/put?zone=living&look=embers')
    await loadedStage()
    act(() => resizeObserved(MAIN_STAGE.width, MAIN_STAGE.height))
    const room = server.state.home.rooms.find((each) => each.hasLights && each.id !== 'living')!
    clickRoom(room)
    await settle()
    expect(router.state.location.search).toBe(`?zone=${room.id}&look=embers`)
    expect(router.state.historyAction).toBe('REPLACE')
  })

  // The chips choose a zone through the one choice, and so does the stage: a home look has locked the zone to the whole home, where the
  // chips are disabled, so a room clicked changes nothing; and the zone already chosen is no choice.
  it.each([
    ['leaves the zone alone under a home look, which locks it to the whole home', '?zone=living&look=goodnight', 'kitchen'],
    ['ignores a click on the room of the zone already chosen', '?zone=living&look=embers', 'living'],
  ])('%s, when a room is clicked on the stage', async (_, search, roomId) => {
    const { server, router } = await openApp(`/next/live/put${search}`)
    await loadedStage()
    act(() => resizeObserved(MAIN_STAGE.width, MAIN_STAGE.height))
    clickRoom(server.state.home.rooms.find((each) => each.id === roomId)!)
    await settle()
    expect(router.state.location.search).toBe(search)
    expect(router.state.historyAction).toBe('POP')
  })

  // The panel waits for the looks, so a click on a room can come before the composer knows the look: the URL's look goes with it all the same.
  it('keeps the look in the URL when a room is clicked on the stage while the looks are still on their way', async () => {
    const { server, router, release } = await openApp('/next/live/put?zone=living&look=embers', {}, ['/api/looks'])
    await loadedStage()
    act(() => resizeObserved(MAIN_STAGE.width, MAIN_STAGE.height))
    const room = server.state.home.rooms.find((each) => each.hasLights && each.id !== 'living')!
    clickRoom(room)
    await settle()
    expect(router.state.location.search).toBe(`?zone=${room.id}&look=embers`)
    release('/api/looks')
    await settle()
    expect(title()).toHaveTextContent(`Put a look on ${zoneName(server, room.id)}`)
  })

  // The stage draws a zone from the preview stream only once the server has answered for that zone: until then nothing is said to be
  // previewed there, rather than a look that isn't on the screen.
  it('says nothing is previewed on a zone until the server has answered for it', async () => {
    const { server } = await openApp('/next/live/put?zone=living&look=embers')
    await loadedStage()
    act(() => resizeObserved(MAIN_STAGE.width, MAIN_STAGE.height))
    expect(previewCard()).toHaveTextContent(`${lookName('embers')} on ${zoneName(server, 'living')}.`)
    const waiting = holdPreviews()
    fireEvent.click(chip(zoneName(server, 'kitchen')))
    await settle(100)
    expect(waiting).toHaveLength(1)
    expect(previewCard()).toBeNull()
    waiting.shift()!()
    await settle(100)
    expect(previewCard()).toHaveTextContent(`${lookName('embers')} on ${zoneName(server, 'kitchen')}.`)
  })

  // The firmware look's answer says which lights run what; the commit that chooses another look, or another zone, still holds that answer.
  it("says nothing of the last look's firmware plan as the next look is chosen", async () => {
    await openApp('/next/live/put?zone=living&look=firmware')
    expect(consequenceLine()).toHaveTextContent(/will (run|get)/)
    fireEvent.click(within(screen.getByRole('group', { name: 'Categories' })).getByRole('button', { name: 'Ambient' }))
    const seen = lineAtEachChoice()
    fireEvent.click(tile('rain'))
    expect(seen).toHaveLength(1)
    expect(seen[0]).not.toMatch(/will (run|get)/)
  })

  it("says nothing of the last zone's firmware plan as the next zone is chosen", async () => {
    const { server } = await openApp('/next/live/put?zone=living&look=firmware')
    expect(consequenceLine()).toHaveTextContent(/will (run|get)/)
    const seen = lineAtEachChoice()
    fireEvent.click(chip(zoneName(server, 'kitchen')))
    expect(seen).toHaveLength(1)
    expect(seen[0]).not.toMatch(/will (run|get)/)
  })

  it("says nothing of the last choice's refusal as the zone is chosen", async () => {
    vi.spyOn(api, 'startPreview').mockRejectedValue(new ApiError(400, 'No preview today', '/api/preview'))
    const { server } = await openApp('/next/live/put?zone=living&look=embers')
    expect(consequenceLine()).toHaveTextContent(`Couldn't preview ${lookName('embers')}. No preview today`)
    const seen = lineAtEachChoice()
    fireEvent.click(chip(zoneName(server, 'kitchen')))
    expect(seen).toHaveLength(1)
    expect(seen[0]).not.toContain("Couldn't preview")
  })

  // F4 ruling 4: what runs on each zone is its chip's note, and the look running on the zone chosen is marked on its tile.
  it('shows what runs on each zone, and which look runs on the zone chosen', async () => {
    const { server } = await openApp('/next/live/put?zone=living&look=embers')
    expect(chip(zoneName(server, 'living'))).toHaveTextContent(lookName('fireflies'))
    expect(tile('fireflies')).toHaveAccessibleName(/running here/)
    expect(consequenceLine()).toHaveTextContent(`from ${lookName('fireflies')}`)
  })

  // A class check, for what the render draws: Live-PutLookOn sets a look's name in serif. Task 10's e2e looks at the pixels.
  it("sets the look's name in the consequence line with the serif class", async () => {
    await openApp('/next/live/put?zone=living&look=embers')
    expect([...consequenceLine().querySelectorAll('.font-serif')].map((each) => each.textContent)).toContain(lookName('fireflies'))
  })

  // §8.2 and F4 ruling 8: the lights a firmware look will run it on are named once its preview has answered.
  it('names the lights that will run a firmware look, once its preview has answered', async () => {
    const { server } = await openApp('/next/live/put?zone=living&look=firmware')
    const living = server.state.zones.find((zone) => zone.id === 'living')!
    const names = server.state.lights.filter((light) => living.lights.includes(light.id)).map((light) => light.name)
    expect(consequenceLine()).toHaveTextContent(/will (run|get)/)
    expect(names.some((name) => consequenceLine().textContent!.includes(name))).toBe(true)
  })

  // F4 ruling 8: a look that waits for an input says so on its tile and in the consequence line, as the inputs the server sends say it.
  it('says what a look waits for, as the server\'s inputs say it, and leaves Start to try', async () => {
    await openApp('/next/live/put?look=goodnight', { scenario: 'inputs-down' })
    expect(tile('goodnight')).toHaveAccessibleName(/Needs Home Assistant/)
    expect(consequenceLine()).toHaveTextContent('Waiting for Home Assistant')
    expect(startButton('goodnight')).toBeEnabled()
  })

  // F4 ruling 11: a transition is chosen for the look it was chosen for.
  it("doesn't carry a transition chosen for one look over to the next", async () => {
    await openApp('/next/live/put?zone=living&look=embers')
    const transition = within(composer()).getByRole('combobox', { name: 'Transition' })
    fireEvent.click(transition)
    await settle(100)
    press(screen.getByRole('option', { name: 'Fade · 3 s' }))
    await settle(100)
    expect(transition).toHaveTextContent('Fade · 3 s')
    fireEvent.click(tile('rain'))
    await settle()
    expect(transition).not.toHaveTextContent('Fade · 3 s')
  })

  // The last zone is the one a look was started on, not the one a start was tried on.
  it('remembers a zone only once a look has been started on it', async () => {
    vi.spyOn(api, 'start').mockRejectedValue(new ApiError(503, 'The engine is busy', '/api/zones/living/start'))
    await openApp('/next/live/put?zone=living&look=embers')
    fireEvent.click(startButton('embers'))
    await settle()
    expect(lastZone()).toBeNull()
  })

  // §8.2: Cancel, Close, Esc and Start all end the composer the same way. One that was stepped into (pushed from Live, its entry marked, as
  // the choices made in place keep it) is stepped back out of, so Back from Live goes where it went before the composer: replacing the
  // entry with Live left Live in the history twice.
  it.each(EXITS)('steps back out of the composer on %s, so Back from Live leaves it', async (_, exit) => {
    const { server, router } = await openApp('/next/settings')
    await act(() => router.navigate('/live'))
    await settle()
    expect(fireEvent.keyDown(document.body, { key: 'L' })).toBe(false)
    await settle()
    expect(router.state.location.pathname).toBe('/next/live/put')
    expect(router.state.historyAction).toBe('PUSH')
    // Choices made in place, a zone's chip and a look's tile, keep the entry the composer was stepped into.
    fireEvent.click(chip(zoneName(server, 'kitchen')))
    fireEvent.click(category('Ambient'))
    fireEvent.click(tile('embers'))
    await settle()
    expect(router.state.location.search).toBe('?zone=kitchen&look=embers')
    expect(router.state.historyAction).toBe('REPLACE')
    exit()
    await settle()
    expect(router.state.location.pathname).toBe('/next/live')
    expect(router.state.historyAction).toBe('POP')
    await act(() => router.navigate(-1))
    expect(router.state.location.pathname).toBe('/next/settings')
  })

  // A second exit asked for before the first has left (a double click on Cancel or Close, Esc and then Cancel) is the same exit: another
  // step back would leave Live too. A browser's step back comes later, so the two are asked of the composer still on the page; here
  // they go in one act, before React has drawn the memory router's step.
  const ASKED_TWICE = EXITS.filter(([name]) => name !== 'Start').flatMap(([first, one]) =>
    EXITS.filter(([name]) => name !== 'Start').map(([second, two]) => [first, second, one, two] as const),
  )
  it.each(ASKED_TWICE)('steps out of the composer once when %s is followed by %s before it has left', async (_first, _second, one, two) => {
    const { router } = await openApp('/next/settings')
    await act(() => router.navigate('/live'))
    await settle()
    fireEvent.keyDown(document.body, { key: 'l' })
    await settle()
    expect(router.state.location.pathname).toBe('/next/live/put')
    act(() => {
      one()
      two()
    })
    await settle()
    expect(router.state.location.pathname).toBe('/next/live')
    expect(router.state.historyAction).toBe('POP')
    await act(() => router.navigate(-1))
    expect(router.state.location.pathname).toBe('/next/settings')
  })

  // A look chosen in between replaces the entry: a new key on the same route, and the exit is still on its way. Not in one act, as the pairs
  // are: the memory router steps back at once, so the choice would find Live and replace that. The step back is held until the choice and
  // Cancel have been made, as a browser's lands after them.
  it('steps out of the composer once when a look is chosen between Esc and Cancel, before it has left', async () => {
    const { router } = await openApp('/next/settings')
    await act(() => router.navigate('/live'))
    await settle()
    fireEvent.keyDown(document.body, { key: 'l' })
    await settle()
    fireEvent.click(category('Ambient'))
    const { asked, land } = holdStepsBack(router)
    fireEvent.keyDown(document.body, { key: 'Escape' })
    fireEvent.click(tile('embers'))
    await settle()
    expect(router.state.location.pathname).toBe('/next/live/put')
    expect(router.state.location.search).toContain('look=embers')
    expect(router.state.historyAction).toBe('REPLACE')
    fireEvent.click(within(composer()).getByRole('button', { name: 'Cancel' }))
    await settle()
    expect(asked()).toBe(1)
    await act(() => land())
    expect(router.state.location.pathname).toBe('/next/live')
    expect(router.state.historyAction).toBe('POP')
    await act(() => router.navigate(-1))
    expect(router.state.location.pathname).toBe('/next/settings')
  })

  // What holds a second exit back lasts until the composer has been left: stepping forward into the same entry, it can be left again.
  it('can be left again once stepped forward into the entry it was left from', async () => {
    const { router } = await openApp('/next/settings')
    await act(() => router.navigate('/live'))
    await settle()
    fireEvent.keyDown(document.body, { key: 'l' })
    await settle()
    fireEvent.click(within(composer()).getByRole('button', { name: 'Cancel' }))
    await settle()
    expect(router.state.location.pathname).toBe('/next/live')
    await act(() => router.navigate(1))
    await settle()
    expect(router.state.location.pathname).toBe('/next/live/put')
    expect(router.state.historyAction).toBe('POP')
    fireEvent.click(within(composer()).getByRole('button', { name: 'Cancel' }))
    await settle()
    expect(router.state.location.pathname).toBe('/next/live')
  })

  // A composer with no step into it (a deep link, or a reload of one) has nothing to step back to: Live replaces it.
  it.each(EXITS)('replaces a composer opened by a link with Live on %s', async (_, exit) => {
    const { router } = await openApp('/next/live/put?zone=living&look=embers')
    exit()
    await settle()
    expect(router.state.location.pathname).toBe('/next/live')
    expect(router.state.historyAction).toBe('REPLACE')
  })

  // Every way in is a step into the composer, from the page it was opened from, which Cancel goes back to: L, the Running panel's
  // link, a room on the stage (clicked, or by its link, which a keyboard reaches) and a zone card's menu.
  it.each([
    ['L', async () => fireEvent.keyDown(document.body, { key: 'l' })],
    ["the Running panel's link", async () => fireEvent.click(screen.getByRole('link', { name: 'Put a look on' }))],
    [
      'a room on the stage',
      async (server: MockServer) => {
        await loadedStage()
        act(() => resizeObserved(MAIN_STAGE.width, MAIN_STAGE.height))
        clickRoom(server.state.home.rooms.find((each) => each.hasLights)!)
      },
    ],
    [
      "a room's link on the stage",
      async (server: MockServer) => {
        await loadedStage()
        const room = server.state.home.rooms.find((each) => each.hasLights)!
        fireEvent.click(within(screen.getByRole('navigation', { name: 'Rooms' })).getByRole('link', { name: `Put a look on ${room.name}` }))
      },
    ],
    [
      "a zone card's menu",
      async (server: MockServer) => {
        press(screen.getByRole('button', { name: `More for ${zoneName(server, 'living')}` }))
        await settle(100)
        fireEvent.click(screen.getByRole('menuitem', { name: 'Change look' }))
      },
    ],
  ])('opens on %s as a step that Cancel steps back out of', async (_, open) => {
    const { server, router } = await openApp('/next/settings')
    await act(() => router.navigate('/live'))
    await settle()
    await open(server)
    await settle()
    expect(router.state.location.pathname).toBe('/next/live/put')
    expect(router.state.historyAction).toBe('PUSH')
    fireEvent.click(within(composer()).getByRole('button', { name: 'Cancel' }))
    await settle()
    expect(router.state.location.pathname).toBe('/next/live')
    expect(router.state.historyAction).toBe('POP')
    await act(() => router.navigate(-1))
    expect(router.state.location.pathname).toBe('/next/settings')
  })

  // The focus was inside the composer, which goes: the Running panel that comes back takes it on its link to the composer, where it
  // would otherwise fall to the page.
  it.each(EXITS)('puts the focus on the Running panel\'s Put a look on after %s', async (_, exit) => {
    await openApp('/next/live')
    fireEvent.keyDown(document.body, { key: 'l' })
    await settle()
    fireEvent.click(tile(tilesShown()[0]!))
    await settle()
    expect(composer()).toContainElement(document.activeElement as HTMLElement)
    exit()
    await settle()
    expect(screen.getByRole('link', { name: 'Put a look on' })).toHaveFocus()
  })

  // The focus goes back to that link as the composer closes, and not otherwise.
  it('leaves the focus alone as Live opens', async () => {
    await openApp('/next/live')
    expect(screen.getByRole('link', { name: 'Put a look on' })).not.toHaveFocus()
  })

  // The page's L is no one's while a dialog is open: Stop all?'s keys are its own.
  it('takes no L while a dialog is open on Live', async () => {
    const { router } = await openApp('/next/live')
    fireEvent.click(screen.getByRole('button', { name: 'Stop all' }))
    await settle(100)
    const dialog = screen.getByRole('alertdialog', { name: 'Stop all?' })
    expect(dialog).toContainElement(document.activeElement as HTMLElement)
    expect(fireEvent.keyDown(document.activeElement!, { key: 'l' })).toBe(true)
    await settle()
    expect(router.state.location.pathname).toBe('/next/live')

    // With the dialog closed, an L opens the composer as it does anywhere on Live.
    fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    await settle(100)
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    fireEvent.keyDown(document.body, { key: 'l' })
    await settle()
    expect(router.state.location.pathname).toBe('/next/live/put')
  })

  // §8.2 "L opens the composer from Live": on Live alone, in either case, and not while typing, or with the modifiers that are the browser's.
  // Esc and L are the page's, but mean nothing where they aren't asked for.
  it('opens on L from Live alone, and takes no L or Esc where they mean nothing', async () => {
    const { router } = await openApp('/next/live/zones/kitchen')
    const where = () => router.state.location.pathname
    fireEvent.keyDown(document.body, { key: 'Escape' })
    await settle()
    expect(where()).toBe('/next/live/zones/kitchen')
    const fields = ['input', 'textarea', 'select', 'div'].map((tag) => document.body.appendChild(document.createElement(tag)))
    // jsdom has no isContentEditable.
    Object.defineProperty(fields[3]!, 'isContentEditable', { value: true })
    for (const field of fields) fireEvent.keyDown(field, { key: 'l' })
    fields.forEach((field) => field.remove())
    for (const modifier of ['ctrlKey', 'altKey', 'metaKey']) fireEvent.keyDown(document.body, { key: 'l', [modifier]: true })
    expect(where()).toBe('/next/live/zones/kitchen')

    fireEvent.keyDown(document.body, { key: 'l' })
    await settle()
    expect(where()).toBe('/next/live/put')
    // Open, an L is no one's: the choice stays.
    fireEvent.click(tile(tilesShown()[1]!))
    await settle()
    const chosen = router.state.location.search
    expect(chosen).toMatch(/^\?look=/)
    fireEvent.keyDown(tile(tilesShown()[1]!), { key: 'l' })
    await settle()
    expect(router.state.location.search).toBe(chosen)
  })

  // Ruling 12: the grid has two looks a row, so Left and Right move by one and Up and Down by a row, and the keys are the grid's alone: the
  // page doesn't scroll under them. Up and Down that would leave the grid stay where they are, but for a Down into a last row that is one
  // look short, which lands on its look. Enter on a look that isn't the one chosen starts nothing.
  it('moves over the grid by the arrows, stops at its edges, and starts only on the look chosen', async () => {
    const start = vi.spyOn(api, 'start')
    const { router } = await openApp('/next/live/put?zone=living&look=embers')
    const shown = tilesShown() as Id[]
    const last = shown.length - 1
    const chosen = () => new URLSearchParams(router.state.location.search).get('look')
    const arrow = (from: Id, key: string) => fireEvent.keyDown(tile(from), { key })

    expect(shown.indexOf('embers')).toBe(2)
    expect(arrow('embers', 'ArrowLeft')).toBe(false)
    expect(chosen()).toBe(shown[1])
    // Up on the top row's right look stays there, and is still the grid's key.
    expect(arrow(shown[1]!, 'ArrowUp')).toBe(false)
    expect(chosen()).toBe(shown[1])
    arrow(shown[1]!, 'ArrowLeft')
    expect(chosen()).toBe(shown[0])
    arrow(shown[0]!, 'ArrowLeft')
    arrow(shown[0]!, 'ArrowUp')
    expect(chosen()).toBe(shown[0])
    expect(last % 2).toBe(0)
    arrow(shown[last - 1]!, 'ArrowDown')
    expect(chosen()).toBe(shown[last])
    arrow(shown[last]!, 'ArrowRight')
    arrow(shown[last]!, 'ArrowDown')
    expect(chosen()).toBe(shown[last])

    expect(fireEvent.keyDown(tile(shown[0]!), { key: 'Enter' })).toBe(true)
    expect(start).not.toHaveBeenCalled()
    expect(fireEvent.keyDown(tile(shown[last]!), { key: 'Enter' })).toBe(false)
    expect(start).toHaveBeenCalledTimes(1)
  })

  // Ruling 12, "by a row": where the last row is full there is no row below it, and a Down on its left look stays there rather than step to its right.
  it('keeps an Up or Down that would leave a grid whose rows are all full where it is', async () => {
    const { router } = await openApp('/next/live/put?zone=living&look=embers')
    fireEvent.click(category('Audio'))
    const shown = tilesShown() as Id[]
    expect(shown).toHaveLength(4)
    const chosen = () => new URLSearchParams(router.state.location.search).get('look')
    const arrow = (from: Id, key: string) => fireEvent.keyDown(tile(from), { key })
    fireEvent.click(tile(shown[2]!))
    await settle()
    arrow(shown[2]!, 'ArrowDown')
    expect(chosen()).toBe(shown[2])
    fireEvent.click(tile(shown[1]!))
    await settle()
    arrow(shown[1]!, 'ArrowUp')
    expect(chosen()).toBe(shown[1])
    arrow(shown[1]!, 'ArrowDown')
    expect(chosen()).toBe(shown[3])
    arrow(shown[3]!, 'ArrowUp')
    expect(chosen()).toBe(shown[1])
  })

  it('starts once, however often Start is asked for while it is on its way', async () => {
    const start = vi.spyOn(api, 'start').mockImplementation(() => new Promise<never>(() => {}))
    await openApp('/next/live/put?zone=living&look=embers')
    fireEvent.keyDown(tile('embers'), { key: 'Enter' })
    fireEvent.keyDown(tile('embers'), { key: 'Enter' })
    expect(start).toHaveBeenCalledTimes(1)
    expect(startButton('embers')).toBeDisabled()
  })

  // A Start's answer can come after the composer was left (the rail, Back): the look started, wherever the user is by now, and that is said
  // and remembered. The composer that asked is gone, and closing it then would take the user back from the page they went to.
  it.each([
    ['the rail', (router: Awaited<ReturnType<typeof openApp>>['router']) => act(() => router.navigate('/inputs')), '/next/inputs'],
    ['Back', (router: Awaited<ReturnType<typeof openApp>>['router']) => act(() => router.navigate(-1)), '/next/live'],
  ])('says a Start answered after the composer was left by %s, and goes nowhere', async (_, leave, where) => {
    const { server, router } = await openApp('/next/settings')
    await act(() => router.navigate('/live'))
    await settle()
    fireEvent.keyDown(document.body, { key: 'l' })
    await settle()
    fireEvent.click(category('Ambient'))
    fireEvent.click(tile('embers'))
    await settle()
    const answer = holdStart()
    fireEvent.click(startButton('embers'))
    await leave(router)
    await settle()
    expect(router.state.location.pathname).toBe(where)
    answer()
    await settle()
    expect(router.state.location.pathname).toBe(where)
    const home = server.state.zones.find((zone) => zone.kind === 'home')!
    expect(screen.getByRole('status')).toHaveTextContent(`Started ${lookName('embers')} on ${home.name}.`)
    expect(server.state.running.find((zone) => zone.zoneId === home.id)?.lookId).toBe('embers')
    expect(lastZone()).toBe(home.id)
  })

  // Esc and L make another composer, of its own, before the answer comes: it's that one's session, and the answer to the first's Start leaves it open.
  it("doesn't close a composer opened after the one that asked for a Start", async () => {
    const { router } = await openApp('/next/live')
    fireEvent.keyDown(document.body, { key: 'l' })
    await settle()
    fireEvent.click(category('Ambient'))
    fireEvent.click(tile('embers'))
    await settle()
    const answer = holdStart()
    fireEvent.click(startButton('embers'))
    fireEvent.keyDown(document.body, { key: 'Escape' })
    await settle()
    fireEvent.keyDown(document.body, { key: 'l' })
    await settle()
    expect(router.state.location.pathname).toBe('/next/live/put')
    answer()
    await settle()
    expect(router.state.location.pathname).toBe('/next/live/put')
    expect(composer()).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent(`Started ${lookName('embers')}`)
  })

  it('starts nothing on Enter where Start is held', async () => {
    const start = vi.spyOn(api, 'start')
    await openApp('/next/live/put?zone=counter&look=embers')
    expect(startButton('embers')).toBeDisabled()
    fireEvent.keyDown(tile('embers'), { key: 'Enter' })
    await settle()
    expect(start).not.toHaveBeenCalled()
  })

  // The focus is on the look chosen as the composer opens, which is the grid's one tab stop, and typing in the search keeps it there.
  it('puts the focus on the look chosen as it opens, and keeps it in the search while that is typed in', async () => {
    await openApp('/next/live/put?zone=living&look=embers')
    expect(document.activeElement).toBe(tile('embers'))
    expect([...composer().querySelectorAll<HTMLElement>('[data-look]')].filter((each) => each.tabIndex === 0)).toEqual([tile('embers')])
    const search = within(composer()).getByRole('searchbox', { name: 'Search looks' })
    search.focus()
    fireEvent.change(search, { target: { value: lookName('comets') } })
    expect(tilesShown()).toEqual(['comets'])
    expect(document.activeElement).toBe(search)
  })

  // The grid is drawn once both the zones and the looks have come, in either order: the focus is for the look chosen whenever that is.
  it('puts the focus on the look chosen when the looks come before the zones', async () => {
    const { release } = await openApp('/next/live/put?look=embers', {}, ['/api/zones'])
    expect(composer().querySelector('[data-look]')).toBeNull()
    release('/api/zones')
    await settle()
    expect(document.activeElement).toBe(tile('embers'))
  })

  // Review focus 5: an Esc in a search with nothing in it is the page's, and a search of spaces is no search.
  it('closes on an Esc in a search with nothing in it, and counts spaces as no search', async () => {
    const { router } = await openApp('/next/live/put?zone=living&look=embers')
    const search = within(composer()).getByRole('searchbox', { name: 'Search looks' })
    fireEvent.change(search, { target: { value: '   ' } })
    expect(within(screen.getByRole('group', { name: 'Categories' })).getByRole('button', { name: 'Ambient' })).toHaveAttribute('aria-pressed', 'true')
    fireEvent.change(search, { target: { value: '' } })
    fireEvent.keyDown(search, { key: 'Escape' })
    await settle()
    expect(router.state.location.pathname).toBe('/next/live')
  })

  // A tile's hidden description is `sr-only`, which is absolutely positioned: with no positioned ancestor inside the grid's scroller it
  // escapes the scroller's clip and stretches <main>'s scroll area (measured: 83 px at 1440 x 900), so each tile holds its own with `relative`.
  it("holds every hidden description in a positioned tile, so nothing in the grid reaches out to <main>'s scroll area", async () => {
    await openApp('/next/live/put?zone=living&look=embers')
    const hidden = composer().querySelectorAll('[data-look] .sr-only')
    expect(hidden).toHaveLength(tilesShown().length)
    for (const each of hidden) expect(each.closest('.relative')).toBe(each.closest('[data-look]'))
  })

  // §4.4: between 768 and 1199 px the panel lies over the stage's right side, and the composer lies there in its place, with Where
  // stopping short of it; the button that brings a hidden Running panel back isn't drawn beside the composer. jsdom has no layout, so
  // the position is the classes (Task 10's e2e measures it).
  it("between 768 and 1199 px, sets the classes that lay the composer over the stage and stop the Where chips short of it", async () => {
    setViewportWidth(1000)
    await openApp('/next/live')
    expect(screen.getByRole('complementary', { name: 'Running' })).toBeInTheDocument()
    fireEvent.keyDown(document.body, { key: 'l' })
    await settle()
    expect(composer()).toHaveClass('absolute')
    expect(screen.queryByRole('complementary', { name: 'Running' })).not.toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Where' }).parentElement).toHaveClass('right-[calc(var(--live-panel-w)+--spacing(5))]')

    fireEvent.keyDown(document.body, { key: 'Escape' })
    await settle()
    // The panel that comes back over the stage takes the focus on its link, as the wide layout's does.
    expect(screen.getByRole('link', { name: 'Put a look on' })).toHaveFocus()
    fireEvent.click(screen.getByRole('button', { name: 'Hide Running' }))
    await settle(100)
    expect(screen.getByRole('button', { name: 'Running' })).toBeInTheDocument()
    fireEvent.keyDown(document.body, { key: 'l' })
    await settle()
    expect(screen.queryByRole('button', { name: 'Running' })).not.toBeInTheDocument()
    fireEvent.keyDown(document.body, { key: 'Escape' })
    await settle()
    expect(screen.getByRole('button', { name: 'Running' })).toBeInTheDocument()
  })
})

describe('Put a look on, on the phone (§8.10)', () => {
  beforeEach(() => {
    setViewportWidth(390)
  })

  const sheet = () => screen.getByRole('region', { name: 'Put a look on' })
  const row = (id: Id) => sheet().querySelector<HTMLElement>(`[data-look="${id}"]`)!
  const rowsShown = () => [...sheet().querySelectorAll<HTMLElement>('[data-look]')].map((each) => each.dataset.look)

  // Phone-PutLookOn: a sheet under the stage, with no header or tab bar; Start names the look and the zone.
  it('puts the composer in a sheet under the stage, and starts the look there', async () => {
    const { server, router } = await openApp('/next/live/put?zone=living&look=embers')
    const living = zoneName(server, 'living')
    expect(screen.queryByRole('banner')).not.toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Main' })).not.toBeInTheDocument()
    expect(within(sheet()).getByRole('heading', { level: 1 })).toHaveTextContent('Put a look on')
    expect(within(sheet()).getByRole('group', { name: 'Where' })).toBeInTheDocument()
    expect(rowsShown()).toEqual(server.state.looks.filter((each) => each.category === 'ambient').map((each) => each.id))
    expect(row('embers')).toHaveAttribute('aria-pressed', 'true')
    expect(sheet().querySelector('[data-consequence]')).toHaveTextContent(`Takes over from ${lookName('fireflies')}`)

    fireEvent.click(within(sheet()).getByRole('button', { name: `Start ${lookName('embers')} on ${living}` }))
    await settle()
    expect(router.state.location.pathname).toBe('/next/live')
    expect(server.state.running.find((zone) => zone.zoneId === 'living')?.lookId).toBe('embers')
    expect(screen.getByRole('banner')).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument()
  })

  // F4 ruling 12: one look a row, so Up and Down move by one.
  it('moves through the looks a row at a time, and closes', async () => {
    const { router } = await openApp('/next/live/put?zone=living&look=embers')
    const shown = rowsShown()
    const next = shown[shown.indexOf('embers') + 1]!
    expect(document.activeElement).toBe(row('embers'))
    fireEvent.keyDown(document.activeElement!, { key: 'ArrowDown' })
    expect(router.state.location.search).toBe(`?zone=living&look=${next}`)
    expect(document.activeElement).toBe(row(next))
    fireEvent.keyDown(document.activeElement!, { key: 'ArrowUp' })
    expect(router.state.location.search).toBe('?zone=living&look=embers')

    fireEvent.click(within(sheet()).getByRole('button', { name: 'Close' }))
    await settle()
    expect(router.state.location.pathname).toBe('/next/live')
  })

  // Phone-PutLookOn has no header, tab bar or search: the sheet's title is the screen's one h1, and the route's own ("Live") is drawn nowhere.
  it('draws no other title, header, tab or search than the sheet\'s', async () => {
    await openApp('/next/live/put?zone=living&look=embers')
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(screen.queryByText('Live')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Live' })).not.toBeInTheDocument()
    expect(within(sheet()).queryByRole('searchbox')).not.toBeInTheDocument()
    expect(sheet().closest('main')).toBe(screen.getByRole('main'))
  })

  // The short consequence beside the transition, as F4 ruling 14 words it: "Takes over from <look>", the look's name in serif.
  it("says the short consequence, not the desktop's sentences", async () => {
    await openApp('/next/live/put?zone=living&look=firmware')
    expect(sheet().querySelector('[data-consequence]')).toHaveTextContent(new RegExp(`^Takes over from ${lookName('fireflies')}$`))
    expect(sheet().querySelector('[data-consequence] .font-serif')).toHaveTextContent(lookName('fireflies'))
  })

  // Review focus 2, on the phone: the consequence line is the one place a refusal can be said, so it says the server's words whole, however
  // long they are, and Start stays to try (and to say its own failure).
  it('says why the preview was refused, whole however long it is, and leaves Start to try', async () => {
    const detail = 'The engine cannot take another preview just now, because the one before it has not finished and the lights have not settled, so ask again in a moment'
    vi.spyOn(api, 'startPreview').mockRejectedValue(new ApiError(400, detail, '/api/preview'))
    await openApp('/next/live/put?look=goodnight')
    expect(sheet().querySelector('[data-consequence]')?.textContent).toBe(`Couldn't preview ${lookName('goodnight')}. ${detail}`)
    expect(within(sheet()).getByRole('button', { name: new RegExp(`^Start ${lookName('goodnight')}`) })).toBeEnabled()
  })

  it.each([
    ['no look chosen', '?zone=living', 'Start', 'Choose a look to see it on the stage first.'],
    ['a zone with no lights', '?zone=counter&look=embers', `Start ${lookName('embers')} on `, ' has no lights.'],
  ])('holds Start for %s, and says why', async (_, search, start, says) => {
    await openApp(`/next/live/put${search}`)
    expect(within(sheet()).getByRole('button', { name: new RegExp(`^${start}`) })).toBeDisabled()
    expect(sheet().querySelector('[data-consequence]')).toHaveTextContent(says)
  })

  // §8.2: "Home looks (whole-home scope) lock the zone to Whole home."
  it('locks the zone to the whole home under a home look', async () => {
    const { server } = await openApp('/next/live/put?zone=living&look=goodnight')
    const home = server.state.zones.find((zone) => zone.kind === 'home')!
    expect(chip(home.name)).toHaveAttribute('aria-pressed', 'true')
    expect(within(screen.getByRole('group', { name: 'Where' })).getAllByRole('button').filter((button) => button.hasAttribute('disabled'))).toHaveLength(
      server.state.zones.length - 1,
    )
    expect(within(sheet()).getByRole('button', { name: `Start ${lookName('goodnight')} on ${home.name}` })).toBeEnabled()
  })

  // The sheet previews through the same hook the panel does: the look chosen, on the zone chosen, as the sheet opens and on each arrow.
  it('previews the look chosen on the zone chosen, and each look the arrows reach', async () => {
    await openApp('/next/live/put?zone=living&look=embers')
    expect(previewSession.snapshot()).toMatchObject({ status: 'on', zoneId: 'living', lookId: 'embers' })
    const shown = rowsShown()
    fireEvent.keyDown(document.activeElement!, { key: 'ArrowDown' })
    await settle()
    expect(previewSession.snapshot()).toMatchObject({ status: 'on', zoneId: 'living', lookId: shown[shown.indexOf('embers') + 1] })
  })

  // §6.3: a chip and a category are choices made in place, so Back from the sheet still leaves it whole.
  it('chooses a zone and a category in place, and Start names the zone', async () => {
    const { server, router } = await openApp('/next/live/put?zone=living&look=embers')
    const kitchen = zoneName(server, 'kitchen')
    fireEvent.click(chip(kitchen))
    await settle()
    expect(router.state.location.search).toBe('?zone=kitchen&look=embers')
    expect(router.state.historyAction).toBe('REPLACE')
    expect(within(sheet()).getByRole('button', { name: `Start ${lookName('embers')} on ${kitchen}` })).toBeEnabled()

    fireEvent.click(category('Tempo'))
    expect(category('Tempo')).toHaveAttribute('aria-pressed', 'true')
    expect(rowsShown()).toEqual(server.state.looks.filter((each) => each.category === 'tempo').map((each) => each.id))
  })

  // F4 ruling 15: "A room click chooses its zone and keeps the look", on the phone's stage as on the desktop's, in place.
  it("chooses a room's zone from a tap on the stage above the sheet, keeping the look", async () => {
    const { server, router } = await openApp('/next/live/put?zone=living&look=embers')
    await loadedStage()
    act(() => resizeObserved(LIVE_SPEC.phoneStage.width, LIVE_SPEC.phoneStage.height))
    const room = server.state.home.rooms.find((each) => each.hasLights && each.id !== 'living')!
    const [x, y] = projectPoint(drawn.props!.pose, [...room.labelAt, 0])
    fireEvent.click(screen.getByTestId('stage-canvas').parentElement!, { clientX: x, clientY: y })
    await settle()
    expect(router.state.location.search).toBe(`?zone=${room.id}&look=embers`)
    expect(router.state.historyAction).toBe('REPLACE')
    expect(chip(zoneName(server, room.id))).toHaveAttribute('aria-pressed', 'true')
  })

  // The sheet has no dialog's focus trap or backdrop: it is part of the page, so the stage above it stays Live's own, and mounted.
  it('keeps the stage that Live drew, and leaves the page unlocked behind a sheet that is no dialog', async () => {
    await openApp('/next/live')
    await loadedStage()
    act(() => resizeObserved(LIVE_SPEC.phoneStage.width, LIVE_SPEC.phoneStage.height))
    const stage = screen.getByTestId('stage-canvas')
    fireEvent.click(screen.getByRole('link', { name: 'Put a look on' }))
    await settle()
    expect(sheet()).toBeInTheDocument()
    expect(screen.getByTestId('stage-canvas')).toBe(stage)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(sheet().closest('[aria-hidden="true"], [inert]')).toBeNull()
  })

  /** A click as a browser sends it: the control takes the focus, then is clicked. */
  const tap = (element: HTMLElement) => {
    element.focus()
    fireEvent.click(element)
  }

  /** The ways out of the sheet; the phone has no Cancel. Each needs a look chosen, so Start can go. */
  const EXITS_FROM_THE_SHEET = [
    ['Close', () => fireEvent.click(within(sheet()).getByRole('button', { name: 'Close' }))],
    ['Esc', () => expect(fireEvent.keyDown(document.body, { key: 'Escape' })).toBe(false)],
    ['Start', () => fireEvent.click(within(sheet()).getByRole('button', { name: /^Start / }))],
  ] as const

  // The focus was in the sheet, which goes with it: the page the exit lands on takes it on its own link to the composer, as the desktop's
  // Running panel does, where it would otherwise fall to <body>. Live's is the sticky Put a look on, and Zone detail's is Change, or Put a
  // look on where the zone has no look of its own (once a Start has put one there, the page is drawn with Change).
  describe.each([
    ['Live', '/next/live', 'Put a look on', 'Put a look on'],
    ["a running zone's detail", '/next/live/zones/living', 'Change', 'Change'],
    ["a zone's detail where nothing runs", '/next/live/zones/kitchen', 'Put a look on', 'Change'],
  ])('from %s', (_, path, link, afterStart) => {
    it.each(EXITS_FROM_THE_SHEET)("puts the focus on the page's link to the composer after %s", async (exitName, exit) => {
      const { router } = await openApp(path)
      fireEvent.click(screen.getByRole('link', { name: link }))
      await settle()
      expect(router.state.location.pathname).toBe('/next/live/put')
      // An ambient look: the composer opens on what runs there, which may be a home look, and that would lock the zone to the whole home.
      // A click in a browser gives the control the focus (fireEvent's doesn't), and the row the focus began on goes with its category.
      tap(category('Ambient'))
      tap(row(rowsShown()[0]!))
      await settle()
      expect(sheet()).toContainElement(document.activeElement as HTMLElement)
      exit()
      await settle()
      expect(router.state.location.pathname).toBe(path)
      expect(screen.getByRole('link', { name: exitName === 'Start' ? afterStart : link })).toHaveFocus()
    })
  })

  // A deep link or a reload has no page to step back to: the exit replaces it with Live, which takes the focus on its link all the same.
  it("puts the focus on Live's Put a look on after an exit from a composer that was opened directly", async () => {
    const { router } = await openApp('/next/live/put?zone=living&look=embers')
    fireEvent.click(within(sheet()).getByRole('button', { name: 'Close' }))
    await settle()
    expect(router.state.location.pathname).toBe('/next/live')
    expect(router.state.historyAction).toBe('REPLACE')
    expect(screen.getByRole('link', { name: 'Put a look on' })).toHaveFocus()
  })

  it('leaves the focus alone as the phone\'s Live and Zone detail open', async () => {
    const { router } = await openApp('/next/live')
    expect(screen.getByRole('link', { name: 'Put a look on' })).not.toHaveFocus()
    await act(() => router.navigate('/live/zones/living'))
    await settle()
    expect(screen.getByRole('link', { name: 'Change' })).not.toHaveFocus()
  })

  // jsdom has no layout, so these check the classes; Chromium measured the rest (<main> never scrolls, from 844 px down to 480, and the
  // chips' and rows' rings are whole), and Task 10's e2e pins it. An absolutely positioned span (a row's hidden description, `sr-only`)
  // with no positioned ancestor inside the list escapes the list's clip, and stretched <main>'s scroll area by the last row's place.
  it('holds every hidden description in a positioned row, so nothing in the list reaches out to <main>\'s scroll area', async () => {
    await openApp('/next/live/put?zone=living&look=embers')
    const list = within(sheet()).getByRole('group', { name: 'Looks' })
    const hidden = list.querySelectorAll('.sr-only')
    expect(hidden).toHaveLength(rowsShown().length)
    for (const each of hidden) {
      const holder = each.closest('.relative')
      expect(holder).not.toBeNull()
      expect(list).toContainElement(holder as HTMLElement)
    }
  })

  it('marks the chips and the transition select, which are drawn under the touch minimum, with touch-target, and pads the chips for their rings', async () => {
    await openApp('/next/live/put?zone=living&look=embers')
    const categories = within(sheet()).getByRole('group', { name: 'Categories' })
    const chips = within(categories).getAllByRole('button')
    expect(chips.length).toBeGreaterThan(1)
    for (const each of [...chips, within(sheet()).getByRole('combobox', { name: 'Transition' })]) expect(each).toHaveClass('touch-target')
    expect(categories).toHaveClass('overflow-x-auto', '-m-1', 'p-1', 'scroll-px-1')
  })

  // Phone-PutLookOn: the stage keeps Phone-Live's box and the sheet fills the screen under it, over the stage's foot (F4 ruling 16). The
  // page is <main>'s own height, so that only the list scrolls; where the screen is too short for the rest of the sheet and a row of the
  // list, the sheet does.
  it("fills the screen under the stage: the page is <main>'s height, and only the list, then the sheet, scrolls", async () => {
    await openApp('/next/live/put?zone=living&look=embers')
    expect(sheet().parentElement).toHaveClass('h-full')
    expect(sheet().parentElement).not.toHaveClass('min-h-full')
    expect(sheet()).toHaveClass('-mt-9', 'min-h-0', 'flex-1', 'overflow-y-auto')
    expect(within(sheet()).getByRole('group', { name: 'Looks' })).toHaveClass('grow', 'overflow-y-auto')
  })

  // Task 9's review: the list takes what the rest of the sheet leaves, but never less than one whole row (and its own padding, on top: the
  // list is `box-content`). The brief's `min-h-0` let it fall away on a short screen (375 x 667 in Safari showed no look at all); below the
  // floor the sheet scrolls instead, so every look and Start can be reached. jsdom has no layout, so this pins the style, the box, the render's
  // 72 px row and the padding and border it is computed from; Chromium's heights are in the report.
  it('keeps the look list at least one whole row high, so a short screen scrolls the sheet rather than squeezing the list away', async () => {
    await openApp('/next/live/put?zone=living&look=embers')
    const list = within(sheet()).getByRole('group', { name: 'Looks' })
    expect(ROW_HEIGHT).toBe(72)
    expect(list.style.minHeight).toBe(`${ROW_HEIGHT}px`)
    expect(list).toHaveClass('box-content')
    expect(list).not.toHaveClass('min-h-0')
    expect(row('embers')).toHaveClass('p-2', 'border')
  })

  it("names the sheet from its heading, the screen's one title", async () => {
    await openApp('/next/live/put?zone=living&look=embers')
    const heading = within(sheet()).getByRole('heading', { level: 1 })
    expect(heading.id).not.toBe('')
    expect(sheet()).toHaveAttribute('aria-labelledby', heading.id)
    expect(sheet()).not.toHaveAttribute('aria-label')
  })

  it("lets Live's page grow past <main> again once the sheet has gone", async () => {
    await openApp('/next/live/put?zone=living&look=embers')
    const page = sheet().parentElement!
    expect(page).toHaveClass('h-full')
    fireEvent.click(within(sheet()).getByRole('button', { name: 'Close' }))
    await settle()
    expect(screen.queryByRole('region', { name: 'Put a look on' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Put a look on' }).closest('.min-h-full')).toBe(page)
    expect(page).not.toHaveClass('h-full')
  })
})
