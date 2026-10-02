import { createRoot } from '@react-three/fiber'
import { act, render, screen } from '@testing-library/react'
import { Component, isValidElement, StrictMode, type ReactElement, type ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { heroPose, sceneProps } from '@/test/stage'
import { SPEC } from './design-numbers'
import { StageScene, type StageSceneProps } from './scene/stage-scene'
import { StageCanvas } from './stage-canvas'

// jsdom has no WebGL, so R3F's createRoot is a stand-in that records what the canvas asks of it, and
// its store hands out a renderer whose compileAsync the test settles.
const root = vi.hoisted(() => ({
  canvas: null as HTMLCanvasElement | null,
  configure: vi.fn(),
  render: vi.fn(),
  unmount: vi.fn(),
  ready: { status: 'fulfilled' as 'fulfilled' | 'rejected' },
}))
vi.mock('@react-three/fiber', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@react-three/fiber')>()),
  createRoot: vi.fn((canvas: HTMLCanvasElement) => {
    root.canvas = canvas
    return root
  }),
}))
const state = { gl: { compileAsync: vi.fn() }, scene: { isScene: true }, camera: { isCamera: true }, invalidate: vi.fn() }
let compiled: () => void

beforeEach(() => {
  root.canvas = null
  root.ready.status = 'fulfilled'
  root.configure.mockReturnValue(Promise.resolve(root))
  root.render.mockReturnValue({ getState: () => state })
  state.gl.compileAsync.mockReturnValue(new Promise<void>((resolve) => (compiled = resolve)))
})

/** The scene the canvas last asked its root to draw. */
function drawnScene(): ReactElement<StageSceneProps> {
  const wrapper = root.render.mock.lastCall![0] as ReactElement<{ children: ReactNode }>
  const scene = wrapper.props.children
  if (!isValidElement<StageSceneProps>(scene) || scene.type !== StageScene) throw new Error('the canvas drew something other than the scene')
  return scene
}

class Boundary extends Component<{ children: ReactNode }, { error: unknown }> {
  state = { error: null }
  static getDerivedStateFromError(error: unknown) {
    return { error }
  }
  render() {
    return this.state.error === null ? this.props.children : <p>{String(this.state.error)}</p>
  }
}

describe("the stage's canvas (§7.5)", () => {
  // E2: R3F's createRoot, not <Canvas>, which registers all of three.js and measures and listens for itself.
  it('draws the scene with its own root, sized from the pose, with no pointer events', () => {
    const props = sceneProps()
    const { container } = render(<StageCanvas {...props} />)
    expect(root.canvas).toBe(container.querySelector('canvas'))
    expect(root.canvas).toHaveAttribute('aria-hidden', 'true')
    expect(root.configure).toHaveBeenCalledWith({
      // E10: the picture is opaque (the scene's background), and the stage needn't wake a discrete GPU.
      gl: { alpha: false, antialias: true, powerPreference: 'default' },
      orthographic: true,
      camera: { manual: true },
      linear: true,
      flat: true,
      frameloop: 'never',
      dpr: [1, SPEC.dprCap],
      size: { width: props.pose.width, height: props.pose.height, top: 0, left: 0 },
      scene: { background: expect.anything() },
    })
    expect(root.configure.mock.lastCall![0]).not.toHaveProperty('events')
    expect(drawnScene().props).toEqual(props)
  })

  // E10: at a pixel ratio of 2 the edges are fine enough, and multisampling cost a software renderer
  // (SwiftShader) 40% of its frame rate on Main.png's stage.
  it('draws without antialiasing at a pixel ratio of 2 or more', () => {
    vi.stubGlobal('devicePixelRatio', 2)
    render(<StageCanvas {...sceneProps()} />)
    expect(root.configure.mock.lastCall![0]).toMatchObject({ gl: { antialias: false } })
  })

  // E4: three links the programs it needs at a draw synchronously, so the first draw waits for them.
  it("draws nothing until three has compiled the scene's shaders off the main thread, then draws on demand", async () => {
    const props = { ...sceneProps(), cadenceMs: 1000 / 60 }
    render(<StageCanvas {...props} />)
    expect(state.gl.compileAsync).toHaveBeenCalledExactlyOnceWith(state.scene, state.camera)
    expect(root.configure.mock.lastCall![0]).toMatchObject({ frameloop: 'never' })
    expect(drawnScene().props.cadenceMs).toBeNull()
    expect(state.invalidate).not.toHaveBeenCalled()
    // An opaque canvas is black until it draws, so it stays hidden until then; the stage's own
    // background shows through.
    expect(root.canvas).not.toBeVisible()
    await act(async () => compiled())
    expect(root.canvas).toBeVisible()
    expect(root.configure.mock.lastCall![0]).toMatchObject({ frameloop: 'demand' })
    expect(drawnScene().props.cadenceMs).toBe(1000 / 60)
    expect(state.invalidate).toHaveBeenCalled()
  })

  it('makes one root and compiles once, though StrictMode runs its effects twice', () => {
    render(
      <StrictMode>
        <StageCanvas {...sceneProps()} />
      </StrictMode>,
    )
    expect(createRoot).toHaveBeenCalledOnce()
    expect(state.gl.compileAsync).toHaveBeenCalledOnce()
    expect(root.unmount).not.toHaveBeenCalled()
  })

  it('follows the pose to a new size, and lets go of its root when the stage goes', () => {
    const { rerender, unmount } = render(<StageCanvas {...sceneProps()} />)
    const smaller = sceneProps('hero', { pose: heroPose({ width: 600, height: 400 }) })
    rerender(<StageCanvas {...smaller} />)
    expect(root.configure.mock.lastCall![0]).toMatchObject({ size: { width: 600, height: 400 } })
    expect(drawnScene().props.pose).toBe(smaller.pose)
    expect(root.unmount).not.toHaveBeenCalled()
    unmount()
    expect(root.unmount).toHaveBeenCalledOnce()
  })

  it("hands a renderer that couldn't start to the page's error boundary", async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    root.ready.status = 'rejected'
    root.configure.mockReturnValue(Promise.reject(new Error('no WebGL 2 context')))
    render(
      <Boundary>
        <StageCanvas {...sceneProps()} />
      </Boundary>,
    )
    expect(await screen.findByText('Error: no WebGL 2 context')).toBeInTheDocument()
    expect(root.render).not.toHaveBeenCalled()
  })
})
