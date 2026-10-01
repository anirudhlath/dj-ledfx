import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { decodeFrame, encodeFrame } from '@/api/frames'
import { frames } from '@/api/live'
import { liveStore } from '@/api/live-store'
import { roomName } from '@/api/mocks/fixtures'
import type { ScenarioName } from '@/api/mocks/scenarios'
import { renderApp } from '@/test/app'
import { seedLive } from '@/test/live'
import { resizeObserved } from '@/test/resize'
import { seedRest } from '@/test/rest'
import { setReducedMotion, setViewportWidth } from '@/test/viewport'
import { lightBodies } from './bodies'
import { bearingDeg, FIT_VIEW, fitPose, LIVE_PADDING, projectPoint } from './camera'
import { RENDER, SPEC } from './design-numbers'
import { anchorOf } from './marks'
import type { StageSceneProps } from './scene/stage-scene'
import { sunReadout, sunReadoutRuns, sunScene } from './sun'
import { readStageView } from './view-memory'
import { hasWebGL2 } from './webgl'

// jsdom has no WebGL: the canvas is a stand-in that shows what it was asked to draw. The rest of the
// stage (the SVG layer, the overlays, the pointer) is the real one.
vi.mock('./webgl', () => ({ hasWebGL2: vi.fn(() => true) }))
vi.mock('./stage-canvas', () => ({
  StageCanvas: ({ frozen, cadenceMs, bearing }: StageSceneProps) => (
    <div data-testid="stage-canvas" data-frozen={String(frozen)} data-cadence={String(cadenceMs)} data-bearing={bearing} />
  ),
}))

const STAGE = { width: RENDER.stage.widthPx, height: RENDER.stage.heightPx }

/** The stage, once its code and data have loaded. */
async function loadedStage(): Promise<HTMLElement> {
  // The stage's code is a lazy chunk, and three.js takes a moment to load the first time.
  await waitFor(() => expect(screen.getByRole('region', { name: 'Home, live' })).not.toHaveAttribute('aria-busy'), { timeout: 10_000 })
  return screen.getByRole('region', { name: 'Home, live' })
}

/** Live on a scenario's data, laid out at Main.png's stage size. */
async function openLive(name: ScenarioName = 'hero') {
  const state = seedRest(name)
  seedLive(name)
  const router = renderApp('/next/live')
  await loadedStage()
  act(() => resizeObserved(STAGE.width, STAGE.height))
  const pose = fitPose(state.home.outline, STAGE, LIVE_PADDING, FIT_VIEW)!
  return { state, router, pose }
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
    expect(screen.getByText(sunScene(state.home, sun)!.label)).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Home, live' })).toHaveTextContent(sunReadout(sun)!)
    expect(within(screen.getByRole('list', { name: 'What the lights show' })).getAllByRole('listitem')).toHaveLength(4)
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
    expect(canvas().dataset.bearing).toBe(String(bearingDeg(SPEC.rotate.stepDeg)))
    const zoomIn = screen.getByRole('button', { name: 'Zoom in' })
    while (!(zoomIn as HTMLButtonElement).disabled) await userEvent.click(zoomIn)
    expect(readStageView(window.localStorage, 'live').view).toEqual({ mode: 'plan', rotateDeg: SPEC.rotate.stepDeg, zoom: 2 })
    await userEvent.click(screen.getByRole('button', { name: 'Fit home' }))
    expect(readStageView(window.localStorage, 'live').view).toEqual({ ...FIT_VIEW, mode: 'plan' })
    expect(canvas().dataset.bearing).toBe(String(bearingDeg(0)))
  })

  // Review focus 3: the link drops, and comes back.
  it('freezes on Reconnecting and thaws when the link is back', async () => {
    await openLive()
    const live = liveStore.getState().connection
    expect(canvas().dataset.frozen).toBe('false')
    expect(canvas().dataset.cadence).toBe(String(1000 / SPEC.target.fps))
    act(() => liveStore.setState({ connection: { status: 'reconnecting', attempt: 1 } }))
    expect(canvas().dataset.frozen).toBe('true')
    expect(canvas().dataset.cadence).toBe('null')
    expect(picture().style.filter).toBe(`grayscale(${SPEC.frozen.grayscale}) brightness(${SPEC.frozen.brightness})`)
    expect(screen.queryByRole('navigation', { name: 'Rooms' })).not.toBeInTheDocument()
    // State-Reconnecting.png's stage is the greyed picture alone: "Controls come back when the link does".
    const overlays = () => [
      screen.queryByRole('switch', { name: 'Labels' }),
      screen.queryByRole('button', { name: 'Rotate view' }),
      screen.queryByRole('list', { name: 'What the lights show' }),
      screen.queryByText(sunReadoutRuns(liveStore.getState().inputs!.sun)![1]),
    ]
    expect(overlays()).toEqual([null, null, null, null])
    act(() => liveStore.setState({ connection: live }))
    expect(canvas().dataset.frozen).toBe('false')
    expect(picture().style.filter).toBe('')
    expect(screen.getByRole('navigation', { name: 'Rooms' })).toBeInTheDocument()
    for (const overlay of overlays()) expect(overlay).toBeInTheDocument()
  })

  it("shows a light's tooltip under the mouse: its name, colour now, look and zone, and model", async () => {
    const { state, pose } = await openLive()
    const zone = state.running.find((candidate) => candidate.zoneId !== 'home')!
    const light = state.lights.find((candidate) => zone.lights.includes(candidate.id) && candidate.shape != null)!
    const [x, y] = projectPoint(pose, anchorOf(lightBodies(light)[0]))
    act(() => {
      decodeFrame(encodeFrame(2, light.id, 1, new Uint8Array(light.leds * 3).fill(128)), 2, frames, 0)
    })
    fireEvent.pointerMove(picture(), { clientX: x, clientY: y, pointerType: 'mouse' })
    const tooltip = await screen.findByRole('tooltip')
    expect(tooltip).toHaveTextContent(light.name)
    expect(tooltip).toHaveTextContent('#808080 · 50%')
    expect(tooltip).toHaveTextContent(`${zone.lookName} · ${state.zones.find((candidate) => candidate.id === zone.zoneId)!.name}`)
    expect(tooltip).toHaveTextContent(light.model)
    fireEvent.pointerLeave(picture())
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
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
    act(() => resizeObserved(STAGE.width, STAGE.height))
    const dark = state.home.rooms.find((room) => !room.hasLights)
    if (dark !== undefined) {
      const [dx, dy] = projectPoint(pose, [...dark.labelAt, 0])
      fireEvent.click(picture(), { clientX: dx, clientY: dy })
      expect(router.state.location.pathname).toBe('/next/live')
    }
  })

  it("says so where WebGL is missing, and keeps the rooms' links", async () => {
    vi.mocked(hasWebGL2).mockReturnValueOnce(false)
    seedRest()
    seedLive()
    renderApp('/next/live')
    await loadedStage()
    expect(screen.getByText("The home can't be drawn here")).toBeInTheDocument()
    expect(within(screen.getByRole('navigation', { name: 'Rooms' })).getAllByRole('link').length).toBeGreaterThan(0)
  })

  // §5.4: with reduced motion the stage still updates the lights' colours, but slowly.
  it('redraws at most once every SPEC.reducedMotionMs when the system asks for less motion', async () => {
    await openLive()
    expect(canvas().dataset.cadence).toBe(String(1000 / SPEC.target.fps))
    act(() => setReducedMotion(true))
    expect(canvas().dataset.cadence).toBe(String(SPEC.reducedMotionMs))
  })

  it("draws the phone's stage without labels or overlays", async () => {
    setViewportWidth(SPEC.phoneStage.width)
    const { state } = await openLive()
    expect(screen.queryByText(state.home.rooms[0].name)).not.toBeInTheDocument()
    expect(screen.queryByRole('switch', { name: 'Labels' })).not.toBeInTheDocument()
    expect(screen.queryByRole('list', { name: 'What the lights show' })).not.toBeInTheDocument()
    // §8.10 "(no labels)": Phone-Live.png draws the sun's disc and arc, but not its label.
    expect(screen.queryByText(sunScene(state.home, state.inputs.sun)!.label)).not.toBeInTheDocument()
    expect(canvas().dataset.cadence).toBe(String(1000 / SPEC.phoneFps))
  })

  // Review focus 1: engine M2 sends no inputs, so no sun.
  it('shows no sun and no readout when the server has no sun, or it has set', async () => {
    const { state } = await openLive()
    const inputs = liveStore.getState().inputs!
    const sun = state.inputs.sun
    const sunDrawn = () => screen.queryByText(sunScene(state.home, sun)!.label) ?? screen.queryByText(sunReadoutRuns(sun)![1])
    expect(sunDrawn()).toBeInTheDocument()
    act(() => liveStore.setState({ inputs: null }))
    expect(sunDrawn()).not.toBeInTheDocument()
    act(() => liveStore.setState({ inputs: { ...inputs, sun: { ...sun, elevation: -3 } } }))
    expect(screen.queryByText(/^SUN /)).not.toBeInTheDocument()
    expect(screen.queryByText(/^Sun /)).not.toBeInTheDocument()
  })
})
