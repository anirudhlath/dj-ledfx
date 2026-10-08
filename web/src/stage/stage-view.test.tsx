import { act, fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useSearchParams } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { applyMessage, liveStore } from '@/api/live-store'
import { lookName, roomName } from '@/api/mocks/fixtures'
import type { ScenarioName } from '@/api/mocks/scenarios'
import { LIVE_SPEC } from '@/design/live-numbers'
import type { ElementSize } from '@/lib/use-element-size'
import { renderApp } from '@/test/app'
import { renders, resetRenders } from '@/test/count-renders'
import { pushFrame } from '@/test/live'
import { resizeObserved } from '@/test/resize'
import { drawn, heroPose, loadedStage, MAIN_STAGE, seedStage, stageWriter } from '@/test/stage'
import { setReducedMotion, setViewportWidth } from '@/test/viewport'
import { lightBodies } from './bodies'
import { FIT_VIEW, fitPose, projectPoint } from './camera'
import { SPEC } from './design-numbers'
import { anchorOf } from './marks'
import { STAGE_LABEL } from './stage-pending'
import { sunPosition, sunScene } from './sun'
import Stage from './stage'
import type { StageVariant } from './stage-view'
import { readStageView } from './view-memory'
import { hasWebGL2 } from './webgl'
import { zonePolygons } from './zone-shape'

// jsdom has no WebGL: the canvas is src/test/stage.ts's stand-in, which keeps the props it was given
// last in `drawn`. The rest of the stage (the SVG layer, the overlays, the pointer) is the real one.
// The view's, the canvas's and the SVG layer's renders are counted.
vi.mock('./webgl', () => import('@/test/stage').then((stage) => stage.webglMock()))
vi.mock('./stage-canvas', (importOriginal) => import('@/test/stage').then((stage) => stage.canvasMock(importOriginal)))
const { countedExport } = await vi.hoisted(() => import('@/test/count-renders'))
vi.mock('./overlays/stage-svg', countedExport('svg', 'StageSvg'))
vi.mock('./stage-view', countedExport('view', 'StageView'))

/** Live on a scenario's data, laid out at Main.png's stage size. */
async function openLive(name: ScenarioName = 'hero') {
  const state = seedStage(name)
  const router = renderApp('/next/live')
  await loadedStage()
  act(() => resizeObserved(MAIN_STAGE.width, MAIN_STAGE.height))
  return { state, router, pose: heroPose() }
}

const canvas = () => screen.getByTestId('stage-canvas')
/** The picture under the overlays: the canvas and the SVG layer, where the pointer picks. */
const picture = () => canvas().parentElement!

beforeEach(() => {
  window.localStorage.clear()
})

describe('the stage on Live (§7, §8.1)', () => {
  it('labels each room with its look, and draws the sun and its readout', async () => {
    const { state } = await openLive()
    // The stage's own labels: the Running panel beside it names the zones too.
    const stage = within(screen.getByRole('region', { name: STAGE_LABEL }))
    for (const room of state.home.rooms) expect(stage.getByText(room.name)).toBeInTheDocument()
    expect(stage.getByText(roomName('corridor'))).toBeInTheDocument()
    for (const zone of state.running) expect(stage.getAllByText(zone.lookName).length).toBeGreaterThan(0)
    const sun = state.inputs.sun
    expect(stage.getByText(sunScene(state.home, sun)!.label!)).toBeInTheDocument()
    expect(stage.getByText(sunPosition(sun)!)).toBeInTheDocument()
    expect(within(screen.getByRole('list', { name: 'What the lights show' })).getAllByRole('listitem')).toHaveLength(4)
  })

  // I1: the engine pushes `lights` every 5 s while a look plays, with the colours it read back. Only a
  // change to what's drawn makes a new writer; the marks follow the lights' status alone.
  it('keeps the light layer and the marks when a push changes only colours', async () => {
    const { state } = await openLive()
    const writer = drawn.props!.writer
    const push = (patch: (light: (typeof state.lights)[number]) => object) =>
      act(() => liveStore.setState({ lights: Object.fromEntries(state.lights.map((light) => [light.id, { ...liveStore.getState().lights![light.id], ...patch(light) }])) }))
    resetRenders()
    push(() => ({ power: true, colour: '#00FF00' }))
    expect(drawn.props!.writer).toBe(writer)
    expect(drawn.props!.entries.some((entry) => entry.resting?.join() === '0,255,0')).toBe(true)
    expect(renders.svg ?? 0).toBe(0)
    const streaming = state.lights.find((light) => light.status === 'streaming')!
    push((light) => (light.id === streaming.id ? { status: 'offline' } : {}))
    expect(drawn.props!.writer).not.toBe(writer)
    expect(renders.svg).toBe(1)
  })

  // E6: hovering re-renders the view, for the tooltip, and nothing it draws.
  it('renders neither the canvas nor the SVG layer again for a hover', async () => {
    const { state, pose } = await openLive()
    const light = state.lights.find((candidate) => candidate.shape != null)!
    const [x, y] = projectPoint(pose, anchorOf(lightBodies(light)[0]))
    resetRenders()
    fireEvent.pointerMove(picture(), { clientX: x, clientY: y, pointerType: 'mouse' })
    expect(await screen.findByRole('tooltip')).toBeInTheDocument()
    expect(renders.canvas ?? 0).toBe(0)
    expect(renders.svg ?? 0).toBe(0)
  })

  // E6: the engine sends `inputs` once a second; one whose sun hasn't changed changes nothing drawn.
  it('renders nothing again for an inputs heartbeat with the same sun', async () => {
    await openLive()
    const inputs = liveStore.getState().inputs!
    const heartbeat = (sun = inputs.sun) => act(() => applyMessage(liveStore, { channel: 'inputs', inputs: structuredClone({ ...inputs, sun }) }, 0))
    resetRenders()
    heartbeat()
    expect(renders).toEqual({})
    heartbeat({ ...inputs.sun!, elevation: inputs.sun!.elevation + 1 })
    expect(renders.view).toBe(1)
    expect(renders.svg).toBe(1)
    expect(renders.canvas ?? 0).toBe(0)
  })

  it('hides the labels with the Labels switch, and remembers that for Live', async () => {
    const { state } = await openLive()
    await userEvent.click(screen.getByRole('switch', { name: 'Labels' }))
    expect(screen.queryByText(state.home.rooms[0].name)).not.toBeInTheDocument()
    expect(readStageView(window.localStorage, 'live').labels).toBe(false)
  })

  it('turns to Plan, orbits a step at a time, zooms in to the last step, and fits again', async () => {
    await openLive()
    await userEvent.click(screen.getByRole('button', { name: 'Plan' }))
    await userEvent.click(screen.getByRole('button', { name: 'Rotate view' }))
    expect(drawn.props!.pose).toEqual(heroPose(MAIN_STAGE, { mode: 'plan', rotateDeg: SPEC.rotate.stepDeg, zoom: 1 }))
    const zoomIn = screen.getByRole('button', { name: 'Zoom in' })
    while (!(zoomIn as HTMLButtonElement).disabled) await userEvent.click(zoomIn)
    expect(readStageView(window.localStorage, 'live').view).toEqual({ mode: 'plan', rotateDeg: SPEC.rotate.stepDeg, zoom: 2 })
    await userEvent.click(screen.getByRole('button', { name: 'Fit home' }))
    expect(readStageView(window.localStorage, 'live').view).toEqual({ ...FIT_VIEW, mode: 'plan' })
    expect(drawn.props!.pose).toEqual(heroPose(MAIN_STAGE, { ...FIT_VIEW, mode: 'plan' }))
  })

  // Review focus 3: the link drops, and comes back.
  it('freezes on Reconnecting and thaws when the link is back', async () => {
    await openLive()
    const live = liveStore.getState().connection
    expect(canvas().dataset.cadence).toBe(String(1000 / SPEC.target.fps))
    act(() => liveStore.setState({ connection: { status: 'reconnecting', attempt: 1 } }))
    // No draws for frames (§7.6 "no animation"), and the picture greyed.
    expect(canvas().dataset.cadence).toBe('null')
    expect(picture().style.filter).toBe(`grayscale(${SPEC.frozen.grayscale}) brightness(${SPEC.frozen.brightness})`)
    expect(screen.queryByRole('navigation', { name: 'Rooms' })).not.toBeInTheDocument()
    // State-Reconnecting.png's stage is the greyed picture alone: "Controls come back when the link does".
    const overlays = () => [
      screen.queryByRole('switch', { name: 'Labels' }),
      screen.queryByRole('button', { name: 'Rotate view' }),
      screen.queryByRole('list', { name: 'What the lights show' }),
      screen.queryByText(sunPosition(liveStore.getState().inputs!.sun)!),
    ]
    expect(overlays()).toEqual([null, null, null, null])
    act(() => liveStore.setState({ connection: live }))
    expect(canvas().dataset.cadence).toBe(String(1000 / SPEC.target.fps))
    expect(picture().style.filter).toBe('')
    expect(screen.getByRole('navigation', { name: 'Rooms' })).toBeInTheDocument()
    for (const overlay of overlays()) expect(overlay).toBeInTheDocument()
  })

  it("shows a light's tooltip under the mouse: its name, colour now, look and zone, and model", async () => {
    const { state, pose } = await openLive()
    const zone = state.running.find((candidate) => candidate.zoneId !== 'home')!
    const light = state.lights.find((candidate) => zone.lights.includes(candidate.id) && candidate.shape != null)!
    const [x, y] = projectPoint(pose, anchorOf(lightBodies(light)[0]))
    act(() => pushFrame(light.id, 1, new Uint8Array(light.leds * 3).fill(128)))
    fireEvent.pointerMove(picture(), { clientX: x, clientY: y, pointerType: 'mouse' })
    const tooltip = await screen.findByRole('tooltip')
    expect(tooltip).toHaveTextContent(light.name)
    expect(tooltip).toHaveTextContent('#808080 · 50%')
    expect(tooltip).toHaveTextContent(`${zone.lookName} · ${state.zones.find((candidate) => candidate.id === zone.zoneId)!.name}`)
    expect(tooltip).toHaveTextContent(light.model)
    fireEvent.pointerLeave(picture())
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })

  // A1: §7.6 lists the hover tooltip under `live` only; a frozen stage has none, like its other controls.
  it('shows no tooltip while frozen, and the pointer picks nothing until the link is back', async () => {
    const { state, pose } = await openLive()
    const light = state.lights.find((candidate) => candidate.status === 'streaming' && candidate.shape != null)!
    const [x, y] = projectPoint(pose, anchorOf(lightBodies(light)[0]))
    const hover = () => fireEvent.pointerMove(picture(), { clientX: x, clientY: y, pointerType: 'mouse' })
    hover()
    expect(await screen.findByRole('tooltip')).toHaveTextContent(light.name)
    const live = liveStore.getState().connection
    act(() => liveStore.setState({ connection: { status: 'reconnecting', attempt: 1 } }))
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    hover()
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    act(() => liveStore.setState({ connection: live }))
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    hover()
    expect(screen.getByRole('tooltip')).toHaveTextContent(light.name)
  })

  it('opens the composer for a room with lights, and not for one without', async () => {
    const { state, pose, router } = await openLive()
    const lit = state.home.rooms.find((room) => room.hasLights)!
    const [x, y] = projectPoint(pose, [...lit.labelAt, 0])
    fireEvent.click(picture(), { clientX: x, clientY: y })
    expect(router.state.location.pathname).toBe('/next/live/put')
    expect(router.state.location.search).toBe(`?zone=${lit.id}`)
    await act(() => router.navigate('/live'))
    await loadedStage()
    act(() => resizeObserved(MAIN_STAGE.width, MAIN_STAGE.height))
    const dark = state.home.rooms.find((room) => !room.hasLights)
    if (dark !== undefined) {
      const [dx, dy] = projectPoint(pose, [...dark.labelAt, 0])
      fireEvent.click(picture(), { clientX: dx, clientY: dy })
      expect(router.state.location.pathname).toBe('/next/live')
    }
  })

  it("says so where WebGL is missing, and keeps the rooms' links", async () => {
    vi.mocked(hasWebGL2).mockReturnValueOnce(false)
    seedStage()
    renderApp('/next/live')
    await loadedStage()
    const title = screen.getByText("The home can't be drawn here")
    // Mi7: what happened, without jargon, true whatever stopped WebGL 2 (the ruling's wording).
    expect(screen.getByText("This browser can't draw the 3D home. Everything else still works.")).toBeInTheDocument()
    // R19: EmptyState pads itself, so nothing around it pads again.
    const padded = []
    for (let element = title.parentElement; element !== null && element.tagName !== 'SECTION'; element = element.parentElement) {
      if (/(^|\s)p-\d/.test(element.className)) padded.push(element)
    }
    expect(padded).toHaveLength(1)
    expect(within(screen.getByRole('navigation', { name: 'Rooms' })).getAllByRole('link').length).toBeGreaterThan(0)
  })

  // §5.4: with reduced motion the stage still updates the lights' colours, but slowly.
  it('redraws at most once every LIVE_SPEC.reducedMotionMs when the system asks for less motion', async () => {
    await openLive()
    expect(canvas().dataset.cadence).toBe(String(1000 / SPEC.target.fps))
    act(() => setReducedMotion(true))
    expect(canvas().dataset.cadence).toBe(String(LIVE_SPEC.reducedMotionMs))
  })

  it("draws the phone's stage without labels or overlays", async () => {
    setViewportWidth(LIVE_SPEC.phoneStage.width)
    const { state } = await openLive()
    expect(screen.queryByText(state.home.rooms[0].name)).not.toBeInTheDocument()
    expect(screen.queryByRole('switch', { name: 'Labels' })).not.toBeInTheDocument()
    expect(screen.queryByRole('list', { name: 'What the lights show' })).not.toBeInTheDocument()
    // §8.10 "(no labels)": Phone-Live.png draws the sun's disc and arc, but not its label.
    expect(screen.queryByText(sunScene(state.home, state.inputs.sun)!.label!)).not.toBeInTheDocument()
    expect(canvas().dataset.cadence).toBe(String(1000 / SPEC.phoneFps))
  })

  // Review focus 1: engine M2 sends no inputs, and M3 (Mi2) only its tempo and Pro DJ Link, so no sun.
  it('shows no sun and no readout when the server has no sun, or it has set', async () => {
    const { state } = await openLive()
    const inputs = liveStore.getState().inputs!
    const sun = state.inputs.sun
    const sunDrawn = () => screen.queryByText(sunScene(state.home, sun)!.label!) ?? screen.queryByText(sunPosition(sun)!)
    expect(sunDrawn()).toBeInTheDocument()
    act(() => applyMessage(liveStore, { channel: 'inputs', inputs: { tempo: inputs.tempo, prodjlink: inputs.prodjlink } }, 0))
    expect(sunDrawn()).not.toBeInTheDocument()
    act(() => liveStore.setState({ inputs }))
    expect(sunDrawn()).toBeInTheDocument()
    act(() => liveStore.setState({ inputs: null }))
    expect(sunDrawn()).not.toBeInTheDocument()
    act(() => liveStore.setState({ inputs: { ...inputs, sun: { ...sun, elevation: -3 } } }))
    // On the stage: on a Sunday the top bar's date line starts "Sun " too.
    const stage = within(screen.getByRole('region', { name: STAGE_LABEL }))
    expect(stage.queryByText(/^SUN /)).not.toBeInTheDocument()
    expect(stage.queryByText(/^Sun /)).not.toBeInTheDocument()
  })

  // §8.1 "Hover a card → its zone outlines on the stage"; F3 decision 23.
  it('outlines the zone of the card under the pointer, and the zone /live/zones/:zoneId names', async () => {
    const { router } = await openLive()
    const panel = screen.getByRole('complementary', { name: 'Running' })
    const outline = () => document.querySelector('[data-outline]')
    expect(outline()).toBeNull()
    fireEvent.pointerOver(within(panel).getByRole('article', { name: 'Living room — Fireflies' }))
    expect(outline()).toHaveAttribute('data-outline', 'living')
    expect(outline()!.querySelectorAll('polygon')).toHaveLength(1)
    fireEvent.pointerLeave(panel)
    expect(outline()).toBeNull()
    await act(() => router.navigate('/live/zones/office'))
    expect(outline()).toHaveAttribute('data-outline', 'office')
  })

  // State-Problems; F3 decision 18: desktop `live` only.
  it('tags a crashed and a slow zone on the stage, until the link drops', async () => {
    await openLive('problems')
    const stage = screen.getByRole('region', { name: STAGE_LABEL })
    expect(within(stage).getByText('Lava stopped · 19:12')).toBeInTheDocument()
    expect(within(stage).getByText('38 fps · target 60')).toBeInTheDocument()
    act(() => liveStore.setState({ connection: { status: 'reconnecting', attempt: 1 } }))
    expect(within(stage).queryByText('Lava stopped · 19:12')).toBeNull()
  })

  // State-Transition; F3 decision 16.
  it('tags a transition with its kind and its percentage', async () => {
    await openLive('transition')
    const stage = screen.getByRole('region', { name: STAGE_LABEL })
    expect(within(stage).getByText(/^Fireflies → Embers · dissolving/)).toHaveTextContent('Fireflies → Embers · dissolving 62%')
  })
})

describe('the stage in focus (§7.6)', () => {
  it("frames the zone at the focus tilt, hides the other zones' lights, and keeps the frame through a drop", async () => {
    const state = seedStage('hero')
    renderApp('/next/focus', { routes: [{ path: '/focus', element: <Stage variant="phone" focus="living" /> }] })
    await loadedStage()
    act(() => resizeObserved(390, 280))
    const zone = state.zones.find((each) => each.id === 'living')!
    const framed = fitPose(zonePolygons(state.home, zone, state.lights).flat(), { width: 390, height: 280 }, FIT_VIEW, SPEC.focus.tiltDeg)
    expect(drawn.props!.pose).toEqual(framed)
    // The canvas draws the zone's lights as it would draw them in the whole home (an offline light is a
    // mark, not a light), and none of the lights round it.
    const lightIds = (entries: readonly { body: { lightId: string } }[]) => entries.map((entry) => entry.body.lightId)
    const inZone = state.lights.filter((light) => zone.lights.includes(light.id))
    const zoneDrawn = lightIds(stageWriter(inZone, { rooms: state.home.rooms }).entries)
    expect(lightIds(drawn.props!.entries)).toEqual(zoneDrawn)
    expect(lightIds(stageWriter(state.lights, { rooms: state.home.rooms }).entries).length).toBeGreaterThan(zoneDrawn.length)
    // The picture alone: no room links, no overlays, and a vignette over it.
    expect(screen.queryByRole('navigation', { name: 'Rooms' })).not.toBeInTheDocument()
    expect(screen.queryByRole('switch', { name: 'Labels' })).not.toBeInTheDocument()
    expect(picture().querySelector('[data-vignette]')).not.toBeNull()

    act(() => liveStore.setState({ connection: { status: 'reconnecting', attempt: 1 } }))
    expect(drawn.props!.pose).toEqual(framed)
    expect(picture().style.filter).toBe(`grayscale(${SPEC.frozen.grayscale}) brightness(${SPEC.frozen.brightness})`)
  })
})

describe('the stage in compose (§7.6)', () => {
  /** The composer's stage on what the URL says, as the composer hands it over: ?zone=, ?look= and the look previewed. */
  function Composing({ variant }: { variant: StageVariant }) {
    const [params] = useSearchParams()
    const compose = { zoneId: params.get('zone')!, lookId: params.get('look'), previewing: params.get('previewing') }
    return <Stage variant={variant} compose={compose} />
  }

  async function openCompose(
    search: string,
    { variant = 'desktop', size = MAIN_STAGE, scenario = 'hero' }: { variant?: StageVariant; size?: ElementSize; scenario?: ScenarioName } = {},
  ) {
    const state = seedStage(scenario)
    const router = renderApp(`/next/live/put${search}`, { routes: [{ path: '/live/put', element: <Composing variant={variant} /> }] })
    await loadedStage()
    act(() => resizeObserved(size.width, size.height))
    return { state, router, pose: heroPose() }
  }
  const previewing = (id: string) => `&previewing=${encodeURIComponent(lookName(id))}`
  /** The streams the canvas draws the zone's lights from, and the rest of the lights. */
  const streams = (lights: readonly string[]) => {
    const ids = new Set(lights)
    const of = (inZone: boolean) => new Set(drawn.props!.entries.filter((entry) => ids.has(entry.body.lightId) === inZone).map((entry) => entry.stream))
    return { zone: of(true), rest: of(false) }
  }

  // Live-PutLookOn: the other rooms dimmed under the zone's outline, the zone's labels bright, and a card.
  it("dims the rooms outside the zone, outlines it, and draws the preview there with a card beside it", async () => {
    const { state, router } = await openCompose(`?zone=living&look=embers${previewing('embers')}`)
    const zone = state.zones.find((each) => each.id === 'living')!
    const stage = within(screen.getByRole('region', { name: STAGE_LABEL }))
    const dims = document.querySelector('[data-dims]')!
    const outline = document.querySelector('[data-outline]')!
    expect(dims.querySelectorAll('polygon')).toHaveLength(state.home.rooms.length - 1)
    expect(outline).toHaveAttribute('data-outline', 'living')
    // Over the labels, as the render layers them: the labels, then the dims, then the outline.
    const label = stage.getByText(zone.name)
    expect(label.compareDocumentPosition(dims) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(dims.compareDocumentPosition(outline) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(label).toHaveClass('fill-text')
    const other = state.home.rooms.find((room) => room.id !== 'living' && room.hasLights)!
    expect(stage.getByText(other.name)).toHaveClass('fill-text-3')
    // The zone's label names the look previewed, and its lights draw the preview stream.
    expect(stage.getByText(lookName('embers'))).toHaveClass('fill-text')
    expect(streams(zone.lights)).toEqual({ zone: new Set(['preview']), rest: new Set(['live']) })
    expect(document.querySelector('[data-preview-card]')).toHaveTextContent(
      `Preview on screen${lookName('embers')} on ${zone.name}. The lights are still running ${lookName('fireflies')}.`,
    )
    // The legend and the sun stay; Live's tools, readout, tags and links don't.
    expect(screen.getByRole('list', { name: 'What the lights show' })).toBeInTheDocument()
    expect(stage.getByText(sunScene(state.home, state.inputs.sun)!.label!)).toBeInTheDocument()
    expect(screen.queryByRole('switch', { name: 'Labels' })).not.toBeInTheDocument()
    expect(screen.queryByText(sunPosition(state.inputs.sun)!)).not.toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Rooms' })).not.toBeInTheDocument()

    // The preview ends: the lights draw the live stream again, and the card goes.
    await act(() => router.navigate('/live/put?zone=living&look=embers', { replace: true }))
    expect(streams(zone.lights)).toEqual({ zone: new Set(['live']), rest: new Set(['live']) })
    expect(stage.getByText(lookName('fireflies'))).toHaveClass('fill-text')
    expect(document.querySelector('[data-preview-card]')).toBeNull()
    expect(document.querySelector('[data-outline]')).toHaveAttribute('data-outline', 'living')
  })

  it('says the lights are as they were where nothing runs', async () => {
    await openCompose(`?zone=kitchen&look=embers${previewing('embers')}`, { scenario: 'nothing-running' })
    expect(document.querySelector('[data-preview-card]')).toHaveTextContent(/\. The lights are as they were\.$/)
  })

  // §6.3 ZonePicker: "Clicking a room on the stage selects the same zone": in place, the look kept, no tooltip.
  it('chooses the zone of a room clicked, keeping the look, and shows no tooltip', async () => {
    const { state, router, pose } = await openCompose('?zone=living&look=embers')
    const room = state.home.rooms.find((candidate) => candidate.hasLights && candidate.id !== 'living')!
    const [x, y] = projectPoint(pose, [...room.labelAt, 0])
    fireEvent.click(picture(), { clientX: x, clientY: y })
    expect(router.state.location.pathname).toBe('/next/live/put')
    expect(router.state.location.search).toBe(`?zone=${room.id}&look=embers`)
    expect(router.state.historyAction).toBe('REPLACE')
    expect(document.querySelector('[data-outline]')).toHaveAttribute('data-outline', room.id)
    const light = state.lights.find((candidate) => candidate.shape != null)!
    const [lx, ly] = projectPoint(pose, anchorOf(lightBodies(light)[0]))
    fireEvent.pointerMove(picture(), { clientX: lx, clientY: ly, pointerType: 'mouse' })
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })

  // Phone-PutLookOn: framed on the zone as focus frames one, the lights round it kept, and a tag.
  it("frames the phone's zone, keeps the lights round it, tags the preview, and keeps the frame through a drop", async () => {
    const size = LIVE_SPEC.phoneStage
    const { state } = await openCompose(`?zone=living&look=embers${previewing('embers')}`, { variant: 'phone', size })
    const zone = state.zones.find((each) => each.id === 'living')!
    const framed = fitPose(zonePolygons(state.home, zone, state.lights).flat(), size, FIT_VIEW, SPEC.focus.tiltDeg)
    expect(drawn.props!.pose).toEqual(framed)
    expect(drawn.props!.entries).toHaveLength(stageWriter(state.lights, { rooms: state.home.rooms }).entries.length)
    expect(picture().querySelector('[data-vignette]')).toBeNull()
    expect(screen.getByText('Preview on screen · lights unchanged')).toBeInTheDocument()
    expect(document.querySelector('[data-preview-card]')).toBeNull()
    expect(screen.queryByRole('list', { name: 'What the lights show' })).not.toBeInTheDocument()
    act(() => liveStore.setState({ connection: { status: 'reconnecting', attempt: 1 } }))
    expect(drawn.props!.pose).toEqual(framed)
    expect(document.querySelector('[data-dims]')).not.toBeNull()
    expect(screen.queryByText('Preview on screen · lights unchanged')).not.toBeInTheDocument()
  })
})
