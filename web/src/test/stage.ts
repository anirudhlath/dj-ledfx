// The stage's test scaffolding: Main.png's stage size and the pose that fits the home to it, the
// light layer's writer and the canvas's props for a scenario, the wait for the stage's lazy chunk,
// one seeding helper, and the stand-ins for what jsdom can't run. vi.mock runs its factory before
// the test file's imports, so a factory reaches this module with a dynamic import:
//   vi.mock('./webgl', () => import('@/test/stage').then((stage) => stage.webglMock()))
// This module imports none of the modules it stands in for.
import { screen } from '@testing-library/react'
import { createElement } from 'react'
import { expect, vi } from 'vitest'
import type { Id, Light, Room } from '@/api/contract'
import { homeFixture } from '@/api/mocks/fixtures'
import { buildScenario, type ScenarioName, type ScenarioState } from '@/api/mocks/scenarios'
import type { ElementSize } from '@/lib/use-element-size'
import { stageBodies } from '@/stage/bodies'
import { FIT_VIEW, fitPose, type CameraPose, type View } from '@/stage/camera'
import { RENDER } from '@/stage/design-numbers'
import { FrameWriter, writerEntries, type WriterEntry } from '@/stage/frame-writer'
import { roomMask } from '@/stage/room-mask'
import type { StageSceneProps } from '@/stage/scene/stage-scene'
import { lightStates, type LightState } from '@/stage/show'
import { STAGE_LABEL } from '@/stage/stage-pending'
import { countedStandIn } from './count-renders'
import { HERO_NOW, seedLive } from './live'
import { seedRest } from './rest'

/** Main.png's stage: the size a stage test lays the stage out at, unless it tests another. */
export const MAIN_STAGE: ElementSize = { width: RENDER.stage.widthPx, height: RENDER.stage.heightPx }

/** The camera's pose on the home (every scenario's) at `size`: fitted, unless given another view. */
export function heroPose(size: ElementSize = MAIN_STAGE, view: View = FIT_VIEW): CameraPose {
  return fitPose(homeFixture.outline, size, view)!
}

/** The light layer's entries and writer for `lights`, as StageView makes them. */
export function stageWriter(
  lights: readonly Light[],
  { states = lightStates(lights), rooms = homeFixture.rooms }: { states?: ReadonlyMap<Id, LightState>; rooms?: readonly Room[] } = {},
): { entries: WriterEntry[]; writer: FrameWriter } {
  const entries = writerEntries(stageBodies(lights), lights, states, rooms)
  return { entries, writer: new FrameWriter(entries) }
}

/** What StageView hands the canvas for a scenario's home and lights: at Main.png's size, fitted, and not drawing. */
export function sceneProps(name: ScenarioName = 'hero', overrides: Partial<StageSceneProps> = {}): StageSceneProps {
  const { home, lights } = buildScenario(name, HERO_NOW)
  return { home, ...stageWriter(lights, { rooms: home.rooms }), mask: roomMask(home.rooms), pose: heroPose(), cadenceMs: null, ...overrides }
}

/** A scenario's REST answers and live store, as Live finds them once it's connected. */
export function seedStage(name: ScenarioName = 'hero'): ScenarioState {
  const state = seedRest(name)
  seedLive(name)
  return state
}

/**
 * The stage's section, once its code and data have loaded. The stage's code is a lazy chunk, and
 * three.js takes a moment to load the first time. vi.waitFor moves fake timers on as it polls.
 */
export async function loadedStage(): Promise<HTMLElement> {
  const stage = () => screen.getByRole('region', { name: STAGE_LABEL })
  await vi.waitFor(() => expect(stage()).not.toHaveAttribute('aria-busy'), { timeout: 10_000 })
  return stage()
}

/** vi.mock's factory for the stage's webgl module: a browser with WebGL 2. `vi.mocked(hasWebGL2)` turns it off. */
export const webglMock = () => ({ hasWebGL2: vi.fn(() => true) })

/** The props the stand-in canvas was given last. */
export const drawn: { props: StageSceneProps | null } = { props: null }

/**
 * vi.mock's factory for the stage's canvas module. jsdom has no WebGL, so the canvas is a stand-in,
 * memoised as the real one is and counted as 'canvas' (count-renders.ts), that keeps its props in
 * `drawn` and shows its cadence.
 */
export async function canvasMock(importOriginal: <T>() => Promise<T>) {
  const { StageCanvas } = await importOriginal<typeof import('@/stage/stage-canvas')>()
  return {
    StageCanvas: countedStandIn('canvas', StageCanvas, (props: StageSceneProps) => {
      drawn.props = props
      return createElement('div', { 'data-testid': 'stage-canvas', 'data-cadence': String(props.cadenceMs) })
    }),
  }
}
