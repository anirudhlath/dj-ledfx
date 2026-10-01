import ReactThreeTestRenderer from '@react-three/test-renderer'
import { Profiler, type ReactNode } from 'react'
import { InstancedMesh, type Object3D, OrthographicCamera } from 'three'
import { LineSegments2 } from 'three/addons/lines/LineSegments2.js'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { liveStore } from '@/api/live-store'
import { buildScenario, type ScenarioName } from '@/api/mocks/scenarios'
import { HERO_NOW, startMockDataLayer } from '@/test/live'
import { stageBodies } from '../bodies'
import { bearingDeg, FIT_VIEW, fitPose, LIVE_PADDING } from '../camera'
import { RENDER, SPEC } from '../design-numbers'
import { FrameWriter, writerEntries } from '../frame-writer'
import type { RGB } from '../light-maths'
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
  const entries = writerEntries(stageBodies(lights), lights, states, home.rooms)
  return {
    home,
    writer: new FrameWriter(entries, WRITER_COLOURS),
    entries,
    mask: roomMask(home.rooms),
    pose: fitPose(home.outline, STAGE, LIVE_PADDING, FIT_VIEW)!,
    bearing: bearingDeg(0),
    cadenceMs: null,
    ...overrides,
  }
}

/** The light layer's three objects, and their materials, in the scene's order: all but the home's group, which comes first. */
function lightLayer(scene: Object3D) {
  const objects: (InstancedMesh | LineSegments2)[] = []
  for (const child of scene.children.slice(1)) {
    child.traverse((object) => {
      if (object instanceof InstancedMesh || object instanceof LineSegments2) objects.push(object)
    })
  }
  return { objects, materials: objects.map((object) => object.material) }
}

/** The stage's scene on test-renderer's canvas, with the camera the test can look at. */
async function renderScene(element: ReactNode) {
  const camera = Object.assign(new OrthographicCamera(), { manual: true })
  const renderer = await ReactThreeTestRenderer.create(element, { camera, frameloop: 'demand', linear: true, flat: true })
  return { renderer, camera }
}

// From HERO_NOW, so the animation frames (every 16 ms from the fake clock's start) keep one phase
// against the mock's ticks, run after run.
beforeEach(() => {
  vi.useFakeTimers({ now: HERO_NOW })
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
  // stream rate, and the cadence draws each frame in the animation frame after it arrives.
  it('draws every LED of every frame for a second, and React commits nothing', async () => {
    startMockDataLayer({ scenario: 'firmware' })
    const props = stageProps('firmware', { cadenceMs: 1000 / SPEC.target.fps })
    let commits = 0
    await renderScene(
      <Profiler id="stage" onRender={() => void (commits += 1)}>
        <StageScene {...props} />
      </Profiler>,
    )
    // Connect and subscribe; the frames start.
    await vi.advanceTimersByTimeAsync(1000)
    commits = 0
    const write = vi.spyOn(props.writer, 'write')
    await vi.advanceTimersByTimeAsync(1000)
    expect(write).toHaveBeenCalledTimes(FPS)
    expect(props.writer.leds).toBe(SPEC.target.leds)
    expect(commits).toBe(0)
  })

  // Review focus 3: the link drops (the reconnecting scenario drops it a second after it connects).
  // No frame comes while it's down, so the last one stays; a light whose state changed still draws.
  it('keeps the last frame when the link drops, and draws a light whose state changed', async () => {
    startMockDataLayer({ scenario: 'reconnecting' })
    const props = stageProps('reconnecting', { cadenceMs: 1000 / SPEC.target.fps })
    const { renderer } = await renderScene(<StageScene {...props} />)
    await vi.advanceTimersByTimeAsync(1500)
    expect(liveStore.getState().connection.status).toBe('reconnecting')
    // The last frame, from before the drop.
    expect(props.writer.leds).toBeGreaterThan(0)
    const write = vi.spyOn(props.writer, 'write')
    await vi.advanceTimersByTimeAsync(1000)
    expect(write).not.toHaveBeenCalled()

    const changed = props.entries.map((entry, index) => (index === 0 ? { ...entry, streamed: false } : entry))
    await renderer.update(<StageScene {...props} entries={changed} />)
    await vi.advanceTimersByTimeAsync(100)
    expect(write).toHaveBeenCalledTimes(1)
  })

  // I1: the engine pushes `lights` every 5 s while a look plays. One that changes only colours draws
  // into the light layer as it is; one that changes what's drawn makes new meshes, but no new
  // materials, so no shader compiles again.
  it('draws a push that changes only colours into the same meshes and materials', async () => {
    const props = stageProps()
    const { renderer } = await renderScene(<StageScene {...props} />)
    const scene = renderer.scene.instance as Object3D
    const before = lightLayer(scene)
    expect(before.objects.length).toBeGreaterThan(0)
    const green: RGB = [0, 255, 0]
    const recoloured = props.entries.map((entry, index) => (index === 0 ? { ...entry, streamed: false, resting: green } : entry))
    await renderer.update(<StageScene {...props} entries={recoloured} />)
    const after = lightLayer(scene)
    // Identity only: three's objects are too big to compare by value.
    expect(after.objects.length).toBe(before.objects.length)
    expect(after.objects.every((object, index) => object === before.objects[index])).toBe(true)
    expect(after.materials.every((material, index) => material === before.materials[index])).toBe(true)
    expect([...props.writer.haloColours.slice(0, 3)]).toEqual([0, 1, 0])
  })

  it('keeps the materials when a light stops being drawn and the meshes are made again', async () => {
    const props = stageProps()
    const { renderer } = await renderScene(<StageScene {...props} />)
    const scene = renderer.scene.instance as Object3D
    const before = lightLayer(scene)
    const fewer = props.entries.slice(1)
    await renderer.update(<StageScene {...props} writer={new FrameWriter(fewer, WRITER_COLOURS)} entries={fewer} />)
    const after = lightLayer(scene)
    expect(after.objects[0] === before.objects[0]).toBe(false)
    expect(after.materials.every((material) => before.materials.includes(material))).toBe(true)
  })

  it('lets go of the home when the stage goes', async () => {
    const dispose = vi.spyOn(HomeScene.prototype, 'dispose')
    const { renderer } = await renderScene(<StageScene {...stageProps()} />)
    await renderer.unmount()
    expect(dispose).toHaveBeenCalled()
  })
})
