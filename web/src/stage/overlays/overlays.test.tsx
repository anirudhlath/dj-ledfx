import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import type { SunInput } from '@/api/contract'
import { decodeFrame, encodeFrame } from '@/api/frames'
import { frames } from '@/api/live'
import { buildScenario } from '@/api/mocks/scenarios'
import { HERO_NOW } from '@/test/live'
import { FIT_VIEW, fitPose, LIVE_PADDING, type CameraPose, type View } from '../camera'
import { RENDER, SPEC } from '../design-numbers'
import type { StageLabel } from '../labels'
import type { Mark } from '../marks'
import { lightState } from '../show'
import { sunReadout, sunScene } from '../sun'
import { tooltipText } from '../tooltip'
import { nextRotation, ZOOM_STEPS } from '../view-memory'
import { Legend } from './legend'
import { LightTooltip } from './light-tooltip'
import { RoomLinks } from './room-links'
import { StageSvg } from './stage-svg'
import { StageTools } from './stage-tools'
import { SunReadout } from './sun-readout'
import { ViewControls } from './view-controls'

const hero = buildScenario('hero', HERO_NOW)
const STAGE = { width: RENDER.stage.widthPx, height: RENDER.stage.heightPx }
const pose: CameraPose = fitPose(hero.home.outline, STAGE, LIVE_PADDING, FIT_VIEW)!
const HERO_SUN: SunInput = hero.inputs.sun

/** One mark of each kind, somewhere on the stage. */
const MARKS: Mark[] = [
  { kind: 'drop', key: 'drop', from: [10, 10], to: [10, 40] },
  { kind: 'switched-off', key: 'off', at: [50, 50] },
  { kind: 'offline', key: 'offline', at: [80, 50] },
  { kind: 'offline-strip', key: 'strip', points: [[100, 100], [140, 100]] },
  { kind: 'own-effect', key: 'own', at: [200, 50] },
  { kind: 'streamed-copy', key: 'copy', at: [250, 50] },
]

const LABELS: StageLabel[] = [
  { key: 'a', name: 'A room', look: 'A look', at: [1, 1, 0] },
  { key: 'b', name: 'Another room', look: null, at: [3, 3, 0] },
]

describe("the stage's SVG layer (§7.3, §7.4, §7.6, §9.1)", () => {
  it('draws a mark for each state, dashed and coloured as SPEC and RENDER say', () => {
    const { container } = render(<StageSvg pose={pose} marks={MARKS} labels={null} sun={null} />)
    const svg = container.querySelector('svg')!
    expect(svg).toHaveAttribute('aria-hidden', 'true')
    expect(svg.children).toHaveLength(MARKS.length)
    const drop = svg.querySelector('line')!
    expect(drop).toHaveAttribute('stroke-dasharray', `${SPEC.dropLine.dashPx} ${SPEC.dropLine.gapPx}`)
    const offline = svg.children[2]
    expect(offline).toHaveAttribute('stroke', 'var(--color-signal)')
    expect(offline).toHaveAttribute('stroke-dasharray', `${RENDER.offlineStrip.dashPx} ${RENDER.offlineStrip.gapPx}`)
    expect(svg.querySelector('polyline')).toHaveAttribute('points', '100,100 140,100')
    expect(svg.children[4]).toHaveAttribute('stroke-dasharray', `${RENDER.ownEffect.dashPx} ${RENDER.ownEffect.gapPx}`)
    // The streamed copy's two wave marks, one row under the other.
    expect(svg.children[5].getAttribute('d')!.match(/M/g)).toHaveLength(2)
  })

  it('labels each room in caps, with its look beneath in serif italic when one runs', () => {
    render(<StageSvg pose={pose} marks={[]} labels={LABELS} sun={null} />)
    expect(screen.getByText('A room')).toHaveClass('label-caps')
    expect(screen.getByText('A look')).toHaveClass('font-serif', 'italic')
    expect(screen.getByText('Another room')).toBeInTheDocument()
  })

  it("draws the sun with its label, and its path's arc when it has one", () => {
    const { container, rerender } = render(<StageSvg pose={pose} marks={[]} labels={null} sun={sunScene(hero.home, HERO_SUN)} />)
    expect(screen.getByText(sunScene(hero.home, HERO_SUN)!.label)).toBeInTheDocument()
    expect(container.querySelector('polyline')).toBeInTheDocument()
    rerender(<StageSvg pose={pose} marks={[]} labels={null} sun={sunScene(hero.home, { ...HERO_SUN, path: undefined })} />)
    expect(container.querySelector('polyline')).not.toBeInTheDocument()
  })
})

describe("the stage's controls (§8.1)", () => {
  it('turns to Plan and back, and the labels off and on', async () => {
    const onMode = vi.fn()
    const onLabels = vi.fn()
    render(<StageTools mode="3d" onMode={onMode} labels onLabels={onLabels} />)
    await userEvent.click(screen.getByRole('button', { name: 'Plan' }))
    expect(onMode).toHaveBeenCalledWith('plan')
    await userEvent.click(screen.getByRole('switch', { name: 'Labels' }))
    expect(onLabels).toHaveBeenCalledWith(false)
  })

  it('rotates a step, zooms in until the last step, and fits back to the fitted view in the same mode', async () => {
    const onView = vi.fn()
    const view: View = { mode: 'plan', rotateDeg: SPEC.rotate.stepDeg, zoom: ZOOM_STEPS[ZOOM_STEPS.length - 1] }
    render(<ViewControls view={view} onView={onView} />)
    expect(screen.getByRole('button', { name: 'Zoom in' })).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Rotate view' }))
    expect(onView).toHaveBeenLastCalledWith({ ...view, rotateDeg: nextRotation(view.rotateDeg) })
    await userEvent.click(screen.getByRole('button', { name: 'Fit home' }))
    expect(onView).toHaveBeenLastCalledWith({ ...FIT_VIEW, mode: 'plan' })
  })

  it('names the four states the lights show', () => {
    render(<Legend />)
    const items = within(screen.getByRole('list', { name: 'What the lights show' })).getAllByRole('listitem')
    expect(items.map((item) => item.textContent)).toEqual(['Live colour', 'Own effect', 'Offline', 'Switched off elsewhere'])
  })

  it('reads the sun out while it is up, and says nothing at night or without a sun', () => {
    const { container, rerender } = render(<SunReadout sun={HERO_SUN} />)
    expect(screen.getByText(sunReadout(HERO_SUN)!)).toBeInTheDocument()
    rerender(<SunReadout sun={{ ...HERO_SUN, elevation: -1 }} />)
    expect(container).toBeEmptyDOMElement()
    rerender(<SunReadout sun={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('links each room with lights to where a click on it goes, and no other room', () => {
    const rooms = hero.home.rooms
    const element = <RoomLinks rooms={rooms} to={(room) => `/live/put?zone=${room.id}`} />
    render(<RouterProvider router={createMemoryRouter([{ path: '*', element }])} />)
    const links = within(screen.getByRole('navigation', { name: 'Rooms' })).getAllByRole('link')
    const lit = rooms.filter((room) => room.hasLights)
    expect(links.map((link) => link.getAttribute('href'))).toEqual(lit.map((room) => `/live/put?zone=${room.id}`))
    expect(links.map((link) => link.textContent)).toEqual(lit.map((room) => `Put a look on ${room.name}`))
  })
})

describe('the light tooltip (§8.1)', () => {
  const light = hero.lights.find((candidate) => candidate.status === 'streaming')!
  const state = lightState(light, undefined)
  const text = tooltipText(light, hero.running, new Map(hero.zones.map((zone) => [zone.id, zone.name])))

  it("names the light and paints its colour now from the frames, with the look and the model", () => {
    decodeFrame(encodeFrame(2, light.id, 1, new Uint8Array(light.leds * 3).fill(128)), 2, frames, 0)
    render(<LightTooltip light={light} state={state} text={text} at={[100, 100]} stage={STAGE} frozen={false} />)
    const tooltip = screen.getByRole('tooltip')
    expect(tooltip).toHaveTextContent(light.name)
    expect(tooltip).toHaveTextContent('#808080 · 50%')
    expect(tooltip).toHaveTextContent(text.device)
    if (text.running !== null) expect(tooltip).toHaveTextContent(text.running)
  })

  it("turns to the light's left near the stage's right edge", () => {
    const at: [number, number] = [STAGE.width - 4, 100]
    render(<LightTooltip light={light} state={state} text={text} at={at} stage={STAGE} frozen />)
    expect(parseFloat(screen.getByRole('tooltip').style.left)).toBeLessThan(at[0])
  })
})
