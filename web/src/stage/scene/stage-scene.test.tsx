import ReactThreeTestRenderer from '@react-three/test-renderer'
import { Profiler, type ReactNode } from 'react'
import { OrthographicCamera } from 'three'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { frames } from '@/api/live'
import { buildScenario, type ScenarioName } from '@/api/mocks/scenarios'
import { HERO_NOW, startMockDataLayer } from '@/test/live'
import { stageBodies } from '../bodies'
import { bearingDeg, FIT_VIEW, fitPose, LIVE_PADDING } from '../camera'
import { RENDER, SPEC } from '../design-numbers'
import { FrameWriter, writerEntries } from '../frame-writer'
import { WRITER_COLOURS } from '../palette'
import { roomMask } from '../room-mask'
import { lightState } from '../show'
import { HomeScene } from './home-scene'
import { StageScene, type StageSceneProps } from './stage-scene'

const STAGE = { width: RENDER.stage.widthPx, height: RENDER.stage.heightPx }
/** The rate the mock streams at: §14's. */
const FPS = SPEC.quality.streamFps

function stageProps(name: ScenarioName = 'hero', overrides: Partial<StageSceneProps> = {}): StageSceneProps {
  const { home, lights } = buildScenario(name, HERO_NOW)
  const states = new Map(lights.map((light) => [light.id, lightState(light, undefined)]))
  return {
    home,
    writer: new FrameWriter(writerEntries(stageBodies(lights), lights, states, home.rooms), WRITER_COLOURS),
    mask: roomMask(home.rooms),
    pose: fitPose(home.outline, STAGE, LIVE_PADDING, FIT_VIEW)!,
    bearing: bearingDeg(0),
    frozen: false,
    cadenceMs: null,
    ...overrides,
  }
}

/** The stage's scene on test-renderer's canvas, with the camera the test can look at. */
async function renderScene(element: ReactNode) {
  const camera = Object.assign(new OrthographicCamera(), { manual: true })
  const renderer = await ReactThreeTestRenderer.create(element, { camera, frameloop: 'demand', linear: true, flat: true })
  return { renderer, camera }
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(HERO_NOW)
})

describe('the stage scene (§7.2, §7.5)', () => {
  it('puts the camera where the pose says', async () => {
    const props = stageProps()
    const { camera } = await renderScene(<StageScene {...props} />)
    expect(camera.zoom).toBe(props.pose.zoom)
    expect(camera.right).toBe(props.pose.width / 2)
  })

  // Done when (§13.1 M2): the frame rate with every LED (SPEC.target). The firmware scenario streams
  // every light (own effects and streamed copies alike), all SPEC.target.leds of them, at §14's
  // stream rate.
  it('draws every LED of every frame for a second, and React commits nothing', async () => {
    startMockDataLayer({ scenario: 'firmware' })
    const props = stageProps('firmware')
    let commits = 0
    const { renderer } = await renderScene(
      <Profiler id="stage" onRender={() => void (commits += 1)}>
        <StageScene {...props} />
      </Profiler>,
    )
    // Connect and subscribe; the frames start.
    await vi.advanceTimersByTimeAsync(1000)
    commits = 0
    let drawn = 0
    for (let i = 0; i < FPS; i++) {
      const version = frames.version
      await vi.advanceTimersByTimeAsync(1000 / FPS)
      expect(frames.version).toBeGreaterThan(version)
      await renderer.advanceFrames(1, 1 / FPS)
      if (props.writer.leds === SPEC.target.leds) drawn += 1
    }
    expect(drawn).toBe(FPS)
    expect(commits).toBe(0)
  })

  it('keeps the last frame while frozen, and draws a light whose state changed', async () => {
    startMockDataLayer()
    const props = stageProps()
    const { renderer } = await renderScene(<StageScene {...props} />)
    await vi.advanceTimersByTimeAsync(1000)
    await renderer.advanceFrames(1, 1 / 60)
    const write = vi.spyOn(props.writer, 'write')
    await renderer.update(<StageScene {...props} frozen />)
    await vi.advanceTimersByTimeAsync(1000)
    await renderer.advanceFrames(5, 1 / 60)
    expect(write).not.toHaveBeenCalled()

    const changed = stageProps('hero', { frozen: true })
    const writeChanged = vi.spyOn(changed.writer, 'write')
    await renderer.update(<StageScene {...props} writer={changed.writer} frozen />)
    await renderer.advanceFrames(3, 1 / 60)
    expect(writeChanged).toHaveBeenCalledTimes(1)
  })

  it('lets go of the home when the stage goes', async () => {
    const dispose = vi.spyOn(HomeScene.prototype, 'dispose')
    const { renderer } = await renderScene(<StageScene {...stageProps()} />)
    await renderer.unmount()
    expect(dispose).toHaveBeenCalled()
  })
})
