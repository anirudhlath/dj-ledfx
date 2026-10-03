import { act, fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { applyMessage, liveStore } from '@/api/live-store'
import { roomName } from '@/api/mocks/fixtures'
import type { ScenarioName } from '@/api/mocks/scenarios'
import { LIVE_SPEC } from '@/design/live-numbers'
import { renderApp } from '@/test/app'
import { renders, resetRenders } from '@/test/count-renders'
import { pushFrame } from '@/test/live'
import { resizeObserved } from '@/test/resize'
import { drawn, heroPose, loadedStage, MAIN_STAGE, seedStage } from '@/test/stage'
import { setReducedMotion, setViewportWidth } from '@/test/viewport'
import { lightBodies } from './bodies'
import { FIT_VIEW, projectPoint } from './camera'
import { SPEC } from './design-numbers'
import { anchorOf } from './marks'
import { STAGE_LABEL } from './stage-pending'
import { sunPosition, sunScene } from './sun'
import { readStageView } from './view-memory'
import { hasWebGL2 } from './webgl'

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
    for (const room of state.home.rooms) expect(screen.getByText(room.name)).toBeInTheDocument()
    expect(screen.getByText(roomName('corridor'))).toBeInTheDocument()
    for (const zone of state.running) expect(screen.getAllByText(zone.lookName).length).toBeGreaterThan(0)
    const sun = state.inputs.sun
    expect(screen.getByText(sunScene(state.home, sun)!.label!)).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: STAGE_LABEL })).getByText(sunPosition(sun)!)).toBeInTheDocument()
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
    expect(screen.queryByText(/^SUN /)).not.toBeInTheDocument()
    expect(screen.queryByText(/^Sun /)).not.toBeInTheDocument()
  })
})
