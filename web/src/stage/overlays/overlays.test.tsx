import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { SunInput } from '@/api/contract'
import { decodeFrame, encodeFrame } from '@/api/frames'
import { frames } from '@/api/live'
import { applyMessage, liveStore } from '@/api/live-store'
import { buildScenario } from '@/api/mocks/scenarios'
import { ButtonLink } from '@/design/button'
import { HERO_NOW, pushFrame } from '@/test/live'
import { linkNames, renderAt } from '@/test/router'
import { stageBehaviour, type StageOptions } from '../behaviour'
import { useCadence } from '../cadence'
import { FIT_VIEW, fitPose, type CameraPose, type View } from '../camera'
import { RENDER, SPEC } from '../design-numbers'
import type { StageLabel } from '../labels'
import type { Mark } from '../marks'
import { lightState } from '../show'
import { sunPosition, sunScene, sunsetTime } from '../sun'
import { deviceLine, tooltipText } from '../tooltip'
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
const pose: CameraPose = fitPose(hero.home.outline, STAGE, FIT_VIEW)!
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
    expect(screen.getByText(sunScene(hero.home, HERO_SUN)!.label!)).toBeInTheDocument()
    expect(container.querySelector('polyline')).toBeInTheDocument()
    rerender(<StageSvg pose={pose} marks={[]} labels={null} sun={sunScene(hero.home, { ...HERO_SUN, path: undefined })} />)
    expect(container.querySelector('polyline')).not.toBeInTheDocument()
    // Where the stage has no labels (behaviour.ts), the sun has none either.
    rerender(<StageSvg pose={pose} marks={[]} labels={null} sun={sunScene(hero.home, HERO_SUN, false)} />)
    expect(container.querySelector('circle')).toBeInTheDocument()
    expect(container.querySelector('text')).not.toBeInTheDocument()
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
    expect(container).toHaveTextContent(`Sun ${sunPosition(HERO_SUN)} · sets ${sunsetTime(HERO_SUN)}`, { normalizeWhitespace: false })
    // Main.png: the elevation and the compass point in mono and the text colour, the rest in the readout's.
    expect(screen.getByText(sunPosition(HERO_SUN)!)).toHaveClass('num', 'text-text')
    rerender(<SunReadout sun={{ ...HERO_SUN, sunset: 'soon' }} />)
    expect(container.textContent).toBe(`Sun ${sunPosition(HERO_SUN)}`)
    rerender(<SunReadout sun={{ ...HERO_SUN, elevation: -1 }} />)
    expect(container).toBeEmptyDOMElement()
    rerender(<SunReadout sun={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('links each room with lights to where a click on it goes, and no other room', () => {
    const rooms = hero.home.rooms
    renderAt('/live', <RoomLinks rooms={rooms} to={(room) => `/live/put?zone=${room.id}`} />)
    const nav = screen.getByRole('navigation', { name: 'Rooms' })
    const lit = rooms.filter((room) => room.hasLights)
    expect(within(nav).getAllByRole('link').map((link) => link.getAttribute('href'))).toEqual(lit.map((room) => `/next/live/put?zone=${room.id}`))
    expect(linkNames(nav)).toEqual(lit.map((room) => `Put a look on ${room.name}`))
  })

  // R1: they're the system's small buttons, with their hover, transition and the phone's touch height.
  it('draws each room link as a small button', () => {
    renderAt(
      '/live',
      <>
        <RoomLinks rooms={hero.home.rooms} to={() => '/live'} />
        <ButtonLink to="/live" size="sm">A button</ButtonLink>
      </>,
    )
    const button = screen.getByRole('link', { name: 'A button' })
    for (const link of within(screen.getByRole('navigation', { name: 'Rooms' })).getAllByRole('link')) {
      expect(link).toHaveClass(...button.classList)
    }
  })
})

describe('the light tooltip (§8.1)', () => {
  const light = hero.lights.find((candidate) => candidate.status === 'streaming')!
  const state = lightState(light, undefined)
  const text = tooltipText(light, hero.running, new Map(hero.zones.map((zone) => [zone.id, zone.name])))

  it("names the light and paints its colour now from the frames, with the look and the model", () => {
    decodeFrame(encodeFrame(2, light.id, 1, new Uint8Array(light.leds * 3).fill(128)), 2, frames, 0)
    render(<LightTooltip light={light} state={state} text={text} at={[100, 100]} stage={STAGE} />)
    const tooltip = screen.getByRole('tooltip')
    expect(tooltip).toHaveTextContent(light.name)
    expect(tooltip).toHaveTextContent('#808080 · 50%')
    expect(tooltip).toHaveTextContent(deviceLine(light, null))
    if (text.running !== null) expect(tooltip).toHaveTextContent(text.running)
  })

  /** The stage's draw tick, as its canvas runs it (scene/light-layer.tsx), drawing nothing here. */
  function DrawTick({ cadenceMs }: { cadenceMs: number | null }) {
    useCadence(cadenceMs, () => {})
    return null
  }

  function renderOnStage(options: Omit<StageOptions, 'mode' | 'labels'>) {
    const { cadenceMs } = stageBehaviour({ mode: 'live', labels: true, ...options })
    render(
      <>
        <DrawTick cadenceMs={cadenceMs} />
        <LightTooltip light={light} state={state} text={text} at={[100, 100]} stage={STAGE} />
      </>,
    )
    return { tooltip: screen.getByRole('tooltip'), cadenceMs: cadenceMs! }
  }

  /** Every LED of the light one grey. */
  const grey = (level: number) => new Uint8Array(light.leds * 3).fill(level)

  // Mi5: the tooltip shows the light as the stage draws it, so with reduced motion or on a phone it
  // changes no more often than the canvas does (§5.4, §7.5).
  it.each([
    ['once per SPEC.reducedMotionMs with reduced motion', { variant: 'desktop', reducedMotion: true }],
    ["at the phone's rate on a phone", { variant: 'phone', reducedMotion: false }],
  ] as const)('repaints its colour as the stage draws: %s', (_, options) => {
    vi.useFakeTimers()
    const { tooltip, cadenceMs } = renderOnStage(options)
    const line = tooltip.querySelector('.num')!
    // Two seconds of frames, a new colour in every animation frame (Vitest's come every 16 ms).
    const painted: number[] = []
    let last = line.textContent
    for (let seq = 1; seq <= 125; seq++) {
      pushFrame(light.id, seq, grey(seq))
      vi.advanceTimersToNextFrame()
      if (line.textContent === last) continue
      last = line.textContent
      painted.push(performance.now())
    }
    const gaps = painted.slice(1).map((at, index) => at - painted[index])
    expect(painted.length).toBeGreaterThan(1)
    // An animation frame that comes a little early still draws: half of one.
    expect(Math.min(...gaps)).toBeGreaterThanOrEqual(cadenceMs - 8)
  })

  // E3: the tooltip writes to the page only when what it says changes, not on every frame.
  it("writes nothing while its light's colour holds, whatever else streams", () => {
    vi.useFakeTimers()
    const other = hero.lights.find((candidate) => candidate.id !== light.id && candidate.leds > 0)!
    pushFrame(light.id, 1, grey(128))
    const { tooltip } = renderOnStage({ variant: 'desktop', reducedMotion: false })
    const observer = new MutationObserver(() => {})
    observer.observe(tooltip, { subtree: true, childList: true, characterData: true, attributes: true })
    for (let seq = 2; seq <= 60; seq++) {
      pushFrame(light.id, seq, grey(128))
      pushFrame(other.id, seq, new Uint8Array(other.leds * 3).fill(seq))
      vi.advanceTimersToNextFrame()
    }
    expect(observer.takeRecords()).toHaveLength(0)
    expect(tooltip).toHaveTextContent('#808080 · 50%')
  })

  it("follows its light's latency on the stats channel", () => {
    render(<LightTooltip light={light} state={state} text={text} at={[100, 100]} stage={STAGE} />)
    const tooltip = screen.getByRole('tooltip')
    expect(tooltip).toHaveTextContent(deviceLine(light, null))
    const stat = { id: light.id, send_fps: 60, latency_ms: 123, dropped_pct: 0 }
    act(() => applyMessage(liveStore, { channel: 'stats', devices: [], lights: [stat] }, 0))
    expect(tooltip).toHaveTextContent('123 ms')
  })

  it("turns to the light's left near the stage's right edge", () => {
    const at: [number, number] = [STAGE.width - 4, 100]
    render(<LightTooltip light={light} state={state} text={text} at={at} stage={STAGE} />)
    expect(parseFloat(screen.getByRole('tooltip').style.left)).toBeLessThan(at[0])
  })
})
