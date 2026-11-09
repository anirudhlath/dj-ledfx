import { useThree } from '@react-three/fiber'
import ReactThreeTestRenderer from '@react-three/test-renderer'
import { Profiler, type ReactNode } from 'react'
import { InstancedMesh, type Object3D, OrthographicCamera, ShaderMaterial, type WebGLRenderer } from 'three'
import { LineSegments2 } from 'three/addons/lines/LineSegments2.js'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fx, wantFx } from '@/api/live'
import { liveStore } from '@/api/live-store'
import { HERO_NOW, pushFrame, startMockDataLayer } from '@/test/live'
import { sceneProps } from '@/test/stage'
import { SPEC } from '../design-numbers'
import { FrameWriter } from '../frame-writer'
import { LIVE_ONLY, type FxPick } from '../fx-writer'
import type { RGB } from '@/lib/light-colour'
import type { ZoneFx } from '@/api/ws-messages'
import { FxMaterials } from './fx-meshes'
import { HomeScene } from './home-scene'
import { StageScene } from './stage-scene'

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

/** The fx layer's mesh of one kind, found by its material's uniforms: the light layer has none of these. */
function fxMesh(scene: Object3D, uniform: string): InstancedMesh | undefined {
  let found: InstancedMesh | undefined
  scene.traverse((object) => {
    if (object instanceof InstancedMesh && object.material instanceof ShaderMaterial && uniform in object.material.uniforms) found = object
  })
  return found
}

/** A picture with every kind the effects in space draw: a particle, both forms of ring, and a plane with and without a ray. */
const EVERY_KIND: ZoneFx = {
  zoneId: 'living',
  stream: 'live',
  particles: [[1, 1, 1, 1, 1, 1, 0.3]],
  rings: [
    { center: [1, 1, 1], radius: 1, width: 0.2, rgb: [1, 0, 0], form: 'sphere' },
    { center: [1, 1, 0], radius: 1, width: 0.2, rgb: [0, 1, 0], form: 'circle' },
  ],
  planes: [
    { point: [1, 1, 1], normal: [0, 0, 1], width: 0.1, rgb: [0, 0, 1] },
    { point: [1, 1, 1], normal: [0, 1, 0], width: 0.1, rgb: [0, 0, 1], ray: [1, 0, 0] },
  ],
}

/**
 * The stage's scene on test-renderer's canvas, with the camera the test can look at. test-renderer's WebGL stand-in offers
 * KHR_parallel_shader_compile but never says a program has finished linking, so compileAsync would wait for ever: here,
 * as on a GPU done linking, every program has.
 */
async function renderScene(element: ReactNode, prepare?: (gl: WebGLRenderer) => void) {
  const camera = Object.assign(new OrthographicCamera(), { manual: true })
  const onCreated = ({ gl }: { gl: WebGLRenderer }) => {
    prepare?.(gl)
    const context = gl.getContext()
    const asked = context.getProgramParameter.bind(context)
    context.getProgramParameter = (program, name) => (name === COMPLETION_STATUS_KHR ? true : asked(program, name))
  }
  const renderer = await ReactThreeTestRenderer.create(element, { camera, frameloop: 'demand', linear: true, flat: true, onCreated })
  return { renderer, camera }
}

/** KHR_parallel_shader_compile's COMPLETION_STATUS_KHR. */
const COMPLETION_STATUS_KHR = 0x91b1

// From HERO_NOW, so the animation frames (every 16 ms from the fake clock's start) keep one phase
// against the mock's ticks, run after run.
beforeEach(() => {
  vi.useFakeTimers({ now: HERO_NOW })
})

describe('the stage scene (§7.2, §7.5)', () => {
  it('puts the camera where the pose says', async () => {
    const props = sceneProps()
    const { camera } = await renderScene(<StageScene {...props} />)
    expect(camera.zoom).toBe(props.pose.zoom)
    expect(camera.right).toBe(props.pose.width / 2)
  })

  // Done when (§13.1 M2): the frame rate with every LED (SPEC.target). The firmware scenario streams
  // every light (own effects and streamed copies alike), all SPEC.target.leds of them, at §14's
  // stream rate. Vitest's animation frames come every 16 ms, a little faster than the target rate,
  // so the cadence holds the target and drops the odd frame: §14's desktop rate is the floor.
  it('draws every LED at the target rate for a second, and React commits nothing', async () => {
    startMockDataLayer({ scenario: 'firmware' })
    const props = sceneProps('firmware', { cadenceMs: 1000 / SPEC.target.fps })
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
    expect(write.mock.calls.length).toBeGreaterThanOrEqual(SPEC.quality.desktopFps)
    expect(write.mock.calls.length).toBeLessThanOrEqual(SPEC.target.fps)
    expect(props.writer.leds).toBe(SPEC.target.leds)
    expect(commits).toBe(0)
  })

  // E5: under ?still the frames keep coming with the same bytes; they upload and render nothing.
  it('renders nothing for a frame that changes no byte', async () => {
    const props = sceneProps('hero', { cadenceMs: 1000 / SPEC.target.fps })
    const { lightId, ledCount } = props.entries.find((entry) => entry.streamed)!.body
    let gl: WebGLRenderer | undefined
    function Renderer() {
      gl = useThree((state) => state.gl)
      return null
    }
    await renderScene(
      <>
        <StageScene {...props} />
        <Renderer />
      </>,
    )
    await vi.advanceTimersByTimeAsync(100)
    const render = vi.spyOn(gl!, 'render')
    const frame = Array.from({ length: ledCount }, () => [10, 20, 30]).flat()
    pushFrame(lightId, 1, frame)
    await vi.advanceTimersByTimeAsync(100)
    expect(render).toHaveBeenCalledOnce()
    pushFrame(lightId, 2, frame)
    await vi.advanceTimersByTimeAsync(100)
    expect(render).toHaveBeenCalledOnce()
  })

  // Review focus 3: the link drops (the reconnecting scenario drops it a second after it connects).
  // No frame comes while it's down, so the last one stays; a light whose state changed still draws.
  it('keeps the last frame when the link drops, and draws a light whose state changed', async () => {
    startMockDataLayer({ scenario: 'reconnecting' })
    const props = sceneProps('reconnecting', { cadenceMs: 1000 / SPEC.target.fps })
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
    const props = sceneProps()
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
    expect([...props.writer.glowColours.slice(0, 3)]).toEqual([0, 1, 0])
  })

  it('keeps the materials when a light stops being drawn and the meshes are made again', async () => {
    const props = sceneProps()
    const { renderer } = await renderScene(<StageScene {...props} />)
    const scene = renderer.scene.instance as Object3D
    const before = lightLayer(scene)
    const fewer = props.entries.slice(1)
    await renderer.update(<StageScene {...props} writer={new FrameWriter(fewer)} entries={fewer} />)
    const after = lightLayer(scene)
    expect(after.objects[0] === before.objects[0]).toBe(false)
    expect(after.materials.every((material) => before.materials.includes(material))).toBe(true)
  })

  // F10: the effects in space draw on the lights' cadence, so the canvas renders once a draw for both. The hero's
  // fireflies and comets send particles, and Shockwave started on the office a ring and a plane.
  it("draws the hero's effects in space beside its lights, rendering once a draw", async () => {
    const server = startMockDataLayer()
    server.handle('POST', '/api/zones/office/start', { lookId: 'shockwave' })
    const release = wantFx()
    const props = sceneProps('hero', { cadenceMs: 1000 / SPEC.target.fps, fx: LIVE_ONLY })
    let gl: WebGLRenderer | undefined
    function Renderer() {
      gl = useThree((state) => state.gl)
      return null
    }
    const { renderer } = await renderScene(
      <>
        <StageScene {...props} />
        <Renderer />
      </>,
    )
    await vi.advanceTimersByTimeAsync(1000)
    expect(fx.live.size).toBeGreaterThan(0)
    const scene = renderer.scene.instance as Object3D
    const pictured = [...fx.live.values()]
    const total = (key: 'particles' | 'rings' | 'planes') => pictured.reduce((sum, zone) => sum + (zone[key]?.length ?? 0), 0)
    expect([total('particles'), total('rings'), total('planes')].every((count) => count > 0)).toBe(true)
    const particles = fxMesh(scene, 'pxPerM')
    expect(particles?.count).toBe(total('particles'))
    expect(particles?.visible).toBe(true)
    expect(fxMesh(scene, 'lift')?.count).toBe(total('rings'))
    expect(fxMesh(scene, 'homeCentre')?.count).toBe(total('planes'))
    const render = vi.spyOn(gl!, 'render')
    const draws = vi.spyOn(props.writer, 'write')
    await vi.advanceTimersByTimeAsync(1000)
    expect(render.mock.calls.length).toBeGreaterThan(0)
    expect(render.mock.calls.length).toBeLessThanOrEqual(draws.mock.calls.length)
    release()
  })

  // e2e's sign that a picture is on the canvas (e2e/helpers.ts, fxPictured()): the canvas names the fx store's
  // version it drew. It's written once a picture drawn, never once an animation frame (§7.5): the mock
  // sends at most 30 pictures a second, and the animation frames come every 16 ms.
  it('marks the canvas with the picture it drew, once a picture and not once a frame', async () => {
    startMockDataLayer()
    const release = wantFx()
    const props = sceneProps('hero', { cadenceMs: 1000 / SPEC.target.fps, fx: LIVE_ONLY })
    let canvas: HTMLCanvasElement | undefined
    function Canvas() {
      canvas = useThree((state) => state.gl.domElement)
      return null
    }
    await renderScene(
      <>
        <StageScene {...props} />
        <Canvas />
      </>,
    )
    await vi.advanceTimersByTimeAsync(1000)
    expect(fx.stored).toBeGreaterThan(0)
    expect(canvas!.getAttribute('data-fx-drawn')).toBe(String(fx.stored))
    const marks = vi.spyOn(canvas!, 'setAttribute')
    const before = fx.stored
    await vi.advanceTimersByTimeAsync(1000)
    const drawn = marks.mock.calls.filter(([name]) => name === 'data-fx-drawn').length
    expect(drawn).toBeGreaterThan(0)
    expect(drawn).toBeLessThanOrEqual(fx.stored - before)
    expect(canvas!.getAttribute('data-fx-drawn')).toBe(String(fx.stored))
    release()
  })

  // Task 8's re-review (d), (e): the mark counts the pictures stored, which a clear doesn't move, so e2e can wait for it to equal
  // the mock's count; it's written as the canvas renders, a new pick takes it away until its own render, and a picture that
  // changes nothing drawn is marked at once, as the canvas shows it already.
  it('marks the pictures it shows exactly, as it renders them, and a new pick only once it has drawn it', async () => {
    const props = sceneProps('hero', { cadenceMs: 1000 / SPEC.target.fps, fx: LIVE_ONLY })
    let gl: WebGLRenderer | undefined
    // The frame a pick's invalidate() asks for: R3F's loop is one for every root, and the tests before this one leave theirs behind.
    let frame: () => void = () => {}
    function Renderer() {
      gl = useThree((state) => state.gl)
      const advance = useThree((state) => state.advance)
      frame = () => advance(performance.now())
      return null
    }
    const scene = (fxPick: FxPick | null) => (
      <>
        <StageScene {...props} fx={fxPick} />
        <Renderer />
      </>
    )
    const { renderer } = await renderScene(scene(LIVE_ONLY))
    await vi.advanceTimersByTimeAsync(100)
    const canvas = gl!.domElement
    const mark = () => canvas.getAttribute('data-fx-drawn')
    // When the canvas renders, the mark says what it shows.
    const marked: (string | null)[] = []
    vi.spyOn(gl!, 'render').mockImplementation(() => void marked.push(mark()))
    const office: ZoneFx = { ...EVERY_KIND, zoneId: 'office' }
    fx.apply({ channel: 'fx', zones: [EVERY_KIND, office] })
    await vi.advanceTimersByTimeAsync(100)
    expect(marked).toEqual(['1'])
    expect(mark()).toBe('1')
    // A clear moves the version, not the count.
    const version = fx.version
    fx.clear()
    fx.apply({ channel: 'fx', zones: [EVERY_KIND, office] })
    await vi.advanceTimersByTimeAsync(100)
    expect(fx.version).toBe(version + 2)
    expect(mark()).toBe('2')

    // Focus on the living room: the mark goes until the canvas draws the new pick.
    const focus: FxPick = { preview: null, hidden: new Set(['office']) }
    await renderer.update(scene(focus))
    expect(mark()).toBeNull()
    frame()
    expect(marked.at(-1)).toBe('2')
    expect(mark()).toBe('2')
    // The hidden office moves: nothing drawn changes, so nothing renders, and the mark moves at once.
    const renders = marked.length
    fx.apply({ channel: 'fx', zones: [EVERY_KIND, { ...office, particles: [[2, 2, 2, 1, 1, 1, 0.3]] }] })
    await vi.advanceTimersByTimeAsync(100)
    expect([marked.length, mark()]).toEqual([renders, '3'])

    // The preview of the living room, once drawn, says so.
    const compose: FxPick = { preview: 'living', hidden: new Set(['living']) }
    await renderer.update(scene(compose))
    frame()
    fx.apply({ channel: 'fx', zones: [office, { ...EVERY_KIND, stream: 'preview' }] })
    await vi.advanceTimersByTimeAsync(100)
    expect(mark()).toBe('4 preview')
    expect(marked.at(-1)).toBe('4 preview')
    // The switch off: the canvas shows no picture.
    await renderer.update(scene(null))
    expect(mark()).toBeNull()
  })

  it('draws no effects in space while it picks none, and lets them go when it stops', async () => {
    startMockDataLayer()
    const release = wantFx()
    const props = sceneProps('hero', { cadenceMs: 1000 / SPEC.target.fps })
    const { renderer } = await renderScene(<StageScene {...props} fx={LIVE_ONLY} />)
    await vi.advanceTimersByTimeAsync(100)
    const scene = renderer.scene.instance as Object3D
    const count = scene.children.length
    await renderer.update(<StageScene {...props} />)
    expect(scene.children.length).toBe(count - 1)
    release()
  })

  // Final review 1: three links a program on the main thread the first time it draws with it. The effects' programs are linked
  // ahead (compileAsync) while the stage's scene comes up, so neither the first picture nor the first ring or plane, nor the
  // switch going on again, makes a new one mid-draw.
  it("links the effects' programs before the first picture, and keeps them across the switch", async () => {
    const props = sceneProps('hero', { cadenceMs: 1000 / SPEC.target.fps, fx: LIVE_ONLY })
    let gl: WebGLRenderer | undefined
    function Renderer() {
      gl = useThree((state) => state.gl)
      return null
    }
    const disposed = vi.spyOn(FxMaterials.prototype, 'dispose')
    const { renderer, camera } = await renderScene(
      <>
        <StageScene {...props} />
        <Renderer />
      </>,
    )
    await vi.advanceTimersByTimeAsync(100)
    // The stage's first draw, with no picture yet.
    gl!.render(renderer.scene.instance as Object3D, camera)
    const programs = gl!.info.programs!.length
    expect(programs).toBeGreaterThan(0)
    const render = vi.spyOn(gl!, 'render')
    fx.apply({ channel: 'fx', zones: [EVERY_KIND] })
    await vi.advanceTimersByTimeAsync(100)
    expect(render).toHaveBeenCalled()
    const scene = renderer.scene.instance as Object3D
    const meshes = ['pxPerM', 'lift', 'homeCentre'].map((uniform) => fxMesh(scene, uniform))
    expect(meshes.map((mesh) => mesh?.count)).toEqual([1, 2, 2])
    expect(gl!.info.programs!.length).toBe(programs)

    // Off and on again: the same materials, so the same programs.
    await renderer.update(
      <>
        <StageScene {...props} fx={null} />
        <Renderer />
      </>,
    )
    await renderer.update(
      <>
        <StageScene {...props} />
        <Renderer />
      </>,
    )
    await vi.advanceTimersByTimeAsync(100)
    const again = ['pxPerM', 'lift', 'homeCentre'].map((uniform) => fxMesh(scene, uniform))
    expect(again.map((mesh) => mesh?.material)).toEqual(meshes.map((mesh) => mesh?.material))
    expect(again.every((mesh, i) => mesh?.material === meshes[i]?.material)).toBe(true)
    expect(gl!.info.programs!.length).toBe(programs)
    expect(disposed).not.toHaveBeenCalled()
    // They go with the stage.
    await renderer.unmount()
    expect(disposed).toHaveBeenCalledOnce()
  })

  // Compiling ahead is only to keep a link off the main thread: if it fails, the programs link on first draw, as before it
  // was done, so the effects still mount, and the failure is reported (e2e's shader check is what catches a broken shader).
  it("draws the effects in space even if compiling their programs ahead fails, and says so", async () => {
    const failure = new Error('compile failed')
    const reported = vi.fn()
    vi.stubGlobal('reportError', reported)
    const props = sceneProps('hero', { cadenceMs: 1000 / SPEC.target.fps, fx: LIVE_ONLY })
    const { renderer } = await renderScene(<StageScene {...props} />, (gl) => {
      gl.compileAsync = vi.fn().mockRejectedValue(failure)
    })
    await vi.advanceTimersByTimeAsync(100)
    expect(reported).toHaveBeenCalledExactlyOnceWith(failure)
    fx.apply({ channel: 'fx', zones: [EVERY_KIND] })
    await vi.advanceTimersByTimeAsync(100)
    const scene = renderer.scene.instance as Object3D
    expect(['pxPerM', 'lift', 'homeCentre'].map((uniform) => fxMesh(scene, uniform)?.count)).toEqual([1, 2, 2])
  })

  it('lets go of the home when the stage goes', async () => {
    const dispose = vi.spyOn(HomeScene.prototype, 'dispose')
    const { renderer } = await renderScene(<StageScene {...sceneProps()} />)
    await renderer.unmount()
    expect(dispose).toHaveBeenCalled()
  })
})
