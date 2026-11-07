import { expect, test, type Page } from '@playwright/test'
import type { InstancedBufferAttribute, InstancedMesh, Scene, ShaderMaterial, WebGLRenderer, OrthographicCamera } from 'three'
import home from '../src/api/mocks/home.json' with { type: 'json' }
import { SPEC } from '../src/stage/design-numbers'
import { contains } from '../src/stage/plan'
import type { Vec2 } from '../src/api/contract'
import { fxPictured, open, openStage, stageCanvas } from './helpers'

/** Three's world, the stage's: x, up, the plan's y. */
type World = [number, number, number]

const minus = (a: World, b: World): World => [a[0] - b[0], a[1] - b[1], a[2] - b[2]]
const dot = (a: World, b: World) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
const distance = (a: World, b: World) => Math.hypot(...minus(a, b))
const inHome = ([x, , z]: World) => contains(home.outline as Vec2[], [x, z])
/** A light falling off from its peak as exp(-(d/h)^2), over its sum across one crossing of the peak. */
const crossing = (d: number, h: number) => Math.exp(-((d / h) ** 2)) / (h * Math.sqrt(Math.PI))

/**
 * fx-shaders.ts's rule for a particle: the engine's falloff at a sight's nearest to it, times the glass's alpha and the particle's
 * strength, whatever its height, so that a stronger particle always adds more than a weaker one.
 */
const glowOf = (centre: World, size: number, strength: number) => (at: World, back: World) => {
  const from = minus(at, centre)
  return SPEC.window.glassAlpha * strength * Math.exp(-(dot(from, from) - dot(from, back) ** 2) / size ** 2)
}

/**
 * fx-shaders.ts's rule for a ring or a plane, worked out here in fine steps: a field's light summed along the line of sight through
 * a point, between the floor and the ceiling, times the glass's alpha, and no more than 1. Both stop at the home's outline.
 */
const seen = (light: (point: World) => number, clipped: boolean) => (at: World, back: World) => {
  const [from, to] = [-at[1] / back[1], (home.ceiling - at[1]) / back[1]]
  const steps = 2000
  const ds = (to - from) / steps
  let sum = 0
  for (let i = 0; i < steps; i++) {
    const s = from + (i + 0.5) * ds
    const point: World = [at[0] + s * back[0], at[1] + s * back[1], at[2] + s * back[2]]
    if (!clipped || inHome(point)) sum += light(point)
  }
  return Math.min(1, SPEC.window.glassAlpha * sum * ds)
}

interface LightCase {
  name: string
  /** A uniform or an attribute only this kind's mesh has. */
  mesh: 'pxPerM' | 'shape' | 'planeNormal'
  /** Its one instance, by attribute, white. */
  item: Record<string, number[]>
  /** What a point on the screen shows, from 0 to 1, by the point and the way back to the camera. */
  shows: (at: World, back: World) => number
  points: World[]
  /** How many levels out a point may be, if not LIGHT_MARGIN. */
  margin?: number
}

/** A level either way: rounding, on both sides of the sum. */
const LIGHT_MARGIN = 2
/**
 * Where the outline cuts a shell's crossing short: the shader asks of each of its samples whether it's inside, so the cut can be
 * half a sample out. They're at most about 3/4 of a half-width apart there, each worth 3/4 / sqrt(pi) of one crossing's glassAlpha.
 */
const OUTLINE_CUT_MARGIN = 6

const WHITE = [1, 1, 1]
const particle = (name: string, centre: World, size: number, points: World[], strength = 1): LightCase => ({
  name,
  mesh: 'pxPerM',
  item: { centre, colour: [strength, strength, strength], size: [size] },
  shows: glowOf(centre, size, strength),
  points,
})
const sphere = (name: string, centre: World, radius: number, width: number, points: World[]): LightCase => ({
  name,
  mesh: 'shape',
  item: { centre, colour: WHITE, shape: [radius, width, 0] },
  shows: seen((point) => crossing(distance(point, centre) - radius, width / 2), true),
  points,
})
const circle = (name: string, centre: World, radius: number, width: number, points: World[]): LightCase => ({
  name,
  mesh: 'shape',
  item: { centre, colour: WHITE, shape: [radius, width, 1] },
  shows: (at, back) => {
    // Where the sight meets the floor.
    const s = -at[1] / back[1]
    const floor: World = [at[0] + s * back[0], 0, at[2] + s * back[2]]
    return inHome(floor) ? SPEC.window.glassAlpha * Math.exp(-(((Math.hypot(floor[0] - centre[0], floor[2] - centre[2]) - radius) / (width / 2)) ** 2)) : 0
  },
  points,
})
const plane = (name: string, point: World, normal: World, width: number, points: World[]): LightCase => ({
  name,
  mesh: 'planeNormal',
  item: { point, planeNormal: normal, ray: [0, 0, 0], colour: WHITE, width: [width] },
  shows: seen((at) => crossing(dot(minus(at, point), normal), width / 2), true),
  points,
})
/** A beam's light is by its angle from the ray, so across it, at each distance, it sums to the same. */
const beam = (name: string, point: World, normal: World, ray: World, width: number, points: World[]): LightCase => ({
  name,
  mesh: 'planeNormal',
  item: { point, planeNormal: normal, ray, colour: WHITE, width: [width] },
  shows: seen((at) => {
    const from = minus(at, point)
    const [along, across] = [dot(from, ray), dot(from, normal)]
    return crossing(Math.atan2(across, along), width / 2) / Math.max(Math.hypot(along, across), 0.02)
  }, true),
  points,
})

// Well inside the home's outline, with a wall (the outline's) just past Z_WALL, at the ceiling's middle height.
const [X, Z, Z_WALL, MID] = [6, 4, 7.4, home.ceiling / 2]
const LIGHT_CASES: [look: string, what: string, cases: LightCase[], view?: 'plan'][] = [
  [
    'fireflies',
    'particles',
    [
      particle('a particle in mid-air', [X, MID, Z], 0.5, [[X + 0.25, MID, Z], [X + 0.5, MID, Z], [X + 0.75, MID, Z], [X - 0.5, MID, Z], [X, MID + 0.4, Z], [X, MID, Z + 0.6]]),
      particle('a particle half in the floor', [X, 0, Z], 0.5, [[X + 0.25, 0, Z], [X + 0.5, 0, Z], [X - 0.5, 0, Z], [X, 0.4, Z], [X, 0, Z + 0.3], [X, 0, Z - 0.3]]),
      particle('a particle half in the ceiling', [X, home.ceiling, Z], 0.5, [[X + 0.25, home.ceiling, Z], [X + 0.5, home.ceiling, Z], [X - 0.5, home.ceiling, Z], [X, home.ceiling - 0.4, Z]]),
      // A weaker particle adds less than a stronger one by its strength alone, wherever each of them is.
      ...[0, MID, home.ceiling].flatMap((height) =>
        [0.3, 0.6].map((strength) => particle(`a particle of strength ${strength} at ${height} m`, [X, height, Z], 0.5, [[X + 0.25, height, Z], [X - 0.25, height, Z]], strength)),
      ),
    ],
  ],
  [
    'shockwave',
    'spheres and circles',
    [
      sphere('a sphere with both its crossings in the room', [X, MID, Z], 1, 0.3, [[X, MID, Z], [X + 0.5, MID, Z], [X + 1, MID, Z], [X - 1.2, MID, Z]]),
      sphere('a sphere the floor cuts', [X, 0, Z], 1.5, 0.3, [[X, 0, Z], [X + 1.5, 0, Z], [X, 1.2, Z], [X + 0.8, 0, Z]]),
      {
        ...sphere('a sphere the outline cuts', [X, MID, Z_WALL], 1, 0.3, [[X, MID, Z_WALL], [X, MID, Z_WALL - 0.8], [X, MID, Z_WALL + 0.8], [X + 0.7, MID, Z_WALL]]),
        margin: OUTLINE_CUT_MARGIN,
      },
      circle('a circle on the floor', [X, 0, Z], 1, 0.3, [[X + 1, 0, Z], [X + 1.15, 0, Z], [X, 0, Z]]),
      circle('a circle the outline cuts', [0.5, 0, Z], 1, 0.3, [[1.5, 0, Z], [-0.5, 0, Z]]),
    ],
  ],
  [
    'shockwave',
    'planes and beams',
    [
      plane('a level plane in mid-air', [X, MID, Z], [0, 1, 0], 0.3, [[X, MID, Z], [X + 1, MID, Z - 1]]),
      plane('a thick level plane the floor cuts', [X, 0.25, Z], [0, 1, 0], 1, [[X, 0.25, Z]]),
      plane('a thin level plane over the floor', [X, 0.25, Z], [0, 1, 0], 0.1, [[X, 0.25, Z]]),
      plane('an upright plane', [X, MID, Z], [1, 0, 0], 0.3, [[X, MID, Z], [X + 0.3, MID, Z], [X - 0.3, MID, Z], [X + 0.6, MID, Z]]),
      beam('a beam', [X, 1, Z], [0, 0, 1], [1, 0, 0], 0.4, [[X + 1, 1, Z], [X + 1, 0, Z], [X + 1, 0, Z + 0.2], [X + 2, 0, Z + 0.4], [X + 1, 0, Z - 0.2], [X + 2, 0, Z - 0.4], [X - 1, 1, Z]]),
      beam('a beam as wide as the engine lets it', [X, 1, Z], [-0.6, 0, 0.8], [0.8, 0, 0.6], 2.0944, [[X + 1, 1, Z + 0.5], [X - 1, 1, Z], [X + 2, 1, Z], [X - 2, 0, Z - 1]]),
      // Its light grows towards the point, so sights passing close by are where a sum in too few steps goes wrong.
      beam('a beam close to its point', [X, 1, Z], [0, 0, 1], [1, 0, 0], 0.4, [[X + 0.03, 1, Z], [X + 0.06, 1, Z], [X + 0.12, 1, Z], [X + 0.03, 0.2, Z + 0.01], [X + 0.03, 2, Z - 0.01]]),
      beam('a wide beam close to its point', [X, 1, Z], [-0.6, 0, 0.8], [0.8, 0, 0.6], 2.0944, [[X + 0.04, 1, Z + 0.03], [X + 0.08, 1, Z + 0.06], [X + 0.1, 0.2, Z - 0.04]]),
      // Turned so that the camera's sights run nearly along it: they stay in its wedge for metres, closing on its point.
      beam('a beam the sights run nearly along', [X, 1, Z], [0.9724, 0, 0.233], [-0.233, 0, 0.9724], 0.349, [[X - 0.014, 1, Z + 0.058], [X - 0.023, 1, Z + 0.097], [X - 0.047, 1, Z + 0.194], [X - 0.023, 0.3, Z + 0.097], [X - 0.023, 2, Z + 0.097]]),
    ],
  ],
  // Plan looks straight down (§7.2): a sight there stays at one distance from a beam's point and one angle off its ray.
  [
    'shockwave',
    'a beam from straight above',
    [beam('a beam in Plan', [X, 1, Z], [0, 0, 1], [1, 0, 0], 0.4, [[X + 1.5, 1, Z], [X + 2, 1, Z], [X + 2, 1, Z + 0.2], [X + 1.5, 1, Z - 0.2], [X - 1, 1, Z]])],
    'plan',
  ],
]

// The stage in the browser, on the mock (the hero unless the path asks for another scenario): §8.1's
// room click, §7.6's frozen mode and §7.4's effects in space. The phone's stage has no labels or overlays (§8.10), and
// stage-view.test.tsx covers it, so this needs one project.
test.describe('the stage', () => {
  test.skip(({ isMobile }) => isMobile)

  // §8.1: "Click a room → /live/put?zone=<room>". The rooms' links (the stage's keyboard way in)
  // name a room with lights and where it goes; a click on that room's label on the floor goes there too.
  test('a click on a room with lights opens the composer for it', async ({ page }) => {
    const stage = await openStage(page)
    const link = stage.getByRole('navigation', { name: 'Rooms' }).getByRole('link').first()
    const room = (await link.textContent())!.replace(/^Put a look on /, '')
    const href = (await link.getAttribute('href'))!
    // The SVG layer lets the pointer through to the picture, so the click goes where the label is drawn.
    const label = (await stage.getByText(room, { exact: true }).boundingBox())!
    await page.mouse.click(label.x + label.width / 2, label.y + label.height / 2)
    await page.waitForURL((url) => `${url.pathname}${url.search}` === href)
  })

  // §7.4: "This is the "Effects in space" toggle (default on)". Under ?still the mock holds its frames and
  // sends one picture of the effects in space, so the canvas is the same draw after draw: the switch takes
  // the hero's fireflies and comets off it and puts them back, and Live remembers it off.
  test('draws the effects in space, and the switch takes them off and back, remembered', async ({ page }) => {
    const stage = await openStage(page, '/next/live?still')
    const effects = stage.getByRole('switch', { name: 'Effects in space' })
    await expect(effects).toHaveAttribute('aria-checked', 'true')
    const canvas = stageCanvas(page)
    const shot = () => canvas.screenshot()
    // Drawn with the picture: it changes once more after the first draw, as the picture lands, then holds.
    await expect.poll(async () => (await shot()).equals(await shot()), { timeout: 5000 }).toBe(true)
    await effects.click()
    await expect(effects).toHaveAttribute('aria-checked', 'false')
    await expect.poll(async () => (await shot()).equals(await shot())).toBe(true)
    const off = await shot()
    await effects.click()
    await expect.poll(async () => (await shot()).equals(off), { timeout: 5000 }).toBe(false)
    // Off again, and after a reload still off: putting them on changes the picture.
    await effects.click()
    await page.reload()
    const reloaded = page.getByRole('switch', { name: 'Effects in space' })
    await expect(reloaded).toHaveAttribute('aria-checked', 'false')
    await expect(canvas).toBeVisible()
    await expect.poll(async () => (await shot()).equals(await shot())).toBe(true)
    const stillOff = await shot()
    await reloaded.click()
    await expect.poll(async () => (await shot()).equals(stillOff), { timeout: 5000 }).toBe(false)
  })

  // jsdom has no WebGL, so the rings' and planes' shaders compile and draw only here. Each look is previewed under ?still on a
  // room with lights, in a scenario where nothing else runs, so the preview's picture is all the stage draws in space: with
  // reduced motion it draws none (§5.4, F10 ruling 4), so a canvas that differs between the two has drawn the picture. A look
  // that draws nothing in space is the control: reduced motion alone changes nothing on the canvas. three logs a shader that
  // fails to compile or link to the console and draws nothing, so the console is checked first. Speaker waves sends a sphere
  // alone, so a sphere that draws nothing fails it, where Shockwave's plane would hide it.
  for (const [look, kinds] of [
    ['shockwave', 'a sphere ring and a plane with a ray'],
    ['speakers', 'a sphere ring alone'],
    ['ripples', 'sphere rings'],
    ['scanner', 'a level plane'],
    ['lava', 'nothing (the control)'],
  ] as const) {
    test(`draws ${kinds} in space for ${look}, and its shaders compile`, async ({ page }) => {
      const messages: string[] = []
      page.on('console', (message) => {
        if (message.type() === 'error' || message.type() === 'warning') messages.push(message.text())
      })
      page.on('pageerror', (error) => messages.push(error.message))
      await page.emulateMedia({ reducedMotion: 'no-preference' })
      await open(page, `/next/live/put?scenario=nothing-running&zone=living&look=${look}&still`)
      const canvas = stageCanvas(page)
      await expect(canvas).toBeVisible()
      await expect(page.getByText(/^Preview on screen/)).toBeVisible()
      await fxPictured(page, { preview: look !== 'lava' })
      const shot = () => canvas.screenshot({ animations: 'disabled' })
      // The canvas at rest: unchanged over a second, past the preview's first frames and reduced motion's one draw a second (§5.4).
      const steady = async () => {
        let last = await shot()
        await expect
          .poll(
            async () => {
              await page.waitForTimeout(1200)
              const now = await shot()
              const moved = await changed(page, last, now)
              last = now
              return moved
            },
            { timeout: 15_000 },
          )
          .toBe(0)
        return last
      }
      const drawn = await steady()
      await page.emulateMedia({ reducedMotion: 'reduce' })
      const gone = await changed(page, drawn, await steady())
      // Two warnings every SwiftShader run gives, which say nothing about the stage's shaders. Checked before the canvas, so a
      // shader that fails says why.
      const benign = /KHR_parallel_shader_compile extension not supported|GPU stall due to ReadPixels/
      expect(messages.filter((text) => /WebGLProgram|Shader Error|WebGL/.test(text) && !benign.test(text))).toEqual([])
      console.log(`${look}: ${gone} pixels differ with the effects in space gone`)
      if (look === 'lava') expect(gone).toBe(0)
      else expect(gone).toBeGreaterThan(MANY_PIXELS)
    })
  }

  // §7.4 on the stage's own meshes and camera: each kind is given one white item at a place these tests know, and the canvas is
  // read with the effects and without, in one task, so nothing else moves between the two. A canvas byte is the shader's output
  // times 255 (the canvas is linear and flat). What each point should show comes from the field the engine lights LEDs with.
  for (const [look, what, cases, view] of LIGHT_CASES) {
    test(`draws ${what} as the engine lights the lamps with them`, async ({ page }) => {
      await page.addInitScript(keepStage)
      if (view !== undefined) await page.addInitScript((mode) => window.localStorage.setItem('dj-ledfx:stage-view:live', JSON.stringify({ mode, rotateDeg: 0, zoom: 1 })), view)
      await page.emulateMedia({ reducedMotion: 'no-preference' })
      await open(page, `/next/live/put?scenario=nothing-running&zone=living&look=${look}&still`)
      await expect(stageCanvas(page)).toBeVisible()
      await fxPictured(page, { preview: true })
      for (const { name, mesh, item, shows, points, margin = LIGHT_MARGIN } of cases) {
        const { shown, sights, back } = await page.evaluate(drawnAt, { mesh, item, points })
        if (view === 'plan') expect(back[1], name).toBeCloseTo(1)
        const levels = sights.map((at, i) => ({ at, shown: shown[i], expected: Math.round(255 * shows(at, back)) }))
        expect(levels.filter((level) => Math.abs(level.shown - level.expected) > margin), name).toEqual([])
        // A case that shows nothing anywhere would pass on a shader that draws nothing.
        expect(Math.max(...levels.map((level) => level.expected)), name).toBeGreaterThan(margin)
      }
    })
  }

  // Review focus 3, in the browser: the reconnecting scenario drops the link a second after it connects. The
  // rooms' links come with the stage, before its canvas, whose shaders can take most of that second to compile.
  test('freezes when the link drops: greyed, and no room opens the composer', async ({ page }) => {
    await open(page, '/next/live?scenario=reconnecting')
    const stage = page.getByRole('region', { name: 'Home, live' })
    await expect(stage.getByRole('navigation', { name: 'Rooms' })).toHaveCount(1)
    await expect(stageCanvas(page)).toBeVisible()
    await expect(page.getByRole('status')).toHaveText('Reconnecting')
    await expect(stage.locator(':scope > div').first()).toHaveCSS('filter', /grayscale/)
    await expect(stage.getByRole('navigation', { name: 'Rooms' })).toHaveCount(0)
  })
})

interface StageWindow {
  __stage: { renderer: WebGLRenderer; scene: Scene; camera: OrthographicCamera }
  __THREE_DEVTOOLS__: EventTarget
}

/** Keeps the stage's renderer, scene and camera where a test can reach them, through three's own hook for its devtools. */
function keepStage() {
  const page = window as unknown as StageWindow
  page.__THREE_DEVTOOLS__ = new EventTarget()
  page.__THREE_DEVTOOLS__.addEventListener('observe', (event) => {
    const object = (event as CustomEvent<Scene>).detail
    if (object.isScene) {
      object.onBeforeRender = (renderer, scene, camera) => {
        page.__stage = { renderer, scene, camera: camera as OrthographicCamera }
      }
    }
  })
}

/**
 * In the page: draws one item on its kind's mesh, alone, and says how much it adds at the pixel of each point, the world point
 * in the middle of that pixel (each sight is one pixel's: the light can change fast from one pixel to the next), and the way
 * back to the camera.
 */
function drawnAt({ mesh: key, item, points }: { mesh: string; item: Record<string, number[]>; points: World[] }) {
  const { renderer, scene, camera } = (window as unknown as StageWindow).__stage
  let mesh = null as InstancedMesh | null
  scene.traverse((object) => {
    const each = object as InstancedMesh
    if (each.isInstancedMesh && (each.geometry.attributes[key] ?? (each.material as ShaderMaterial).uniforms?.[key])) mesh = each
  })
  if (mesh === null) throw new Error(`no mesh with ${key}`)
  const drawn: InstancedMesh = mesh
  for (const [name, values] of Object.entries(item)) {
    const attribute = drawn.geometry.attributes[name] as InstancedBufferAttribute
    attribute.array.set(values)
    attribute.clearUpdateRanges()
    attribute.needsUpdate = true
  }
  drawn.count = 1
  for (const sibling of drawn.parent!.children) sibling.visible = sibling === drawn
  const gl = renderer.getContext()
  const view = camera.matrixWorldInverse.elements
  const projection = camera.projectionMatrix.elements
  const [right, up]: World[] = [[view[0], view[4], view[8]], [view[1], view[5], view[9]]]
  const pixels = points.map(([x, y, z]) => [
    // An orthographic camera, so a point's clip w is 1.
    (((view[0] * x + view[4] * y + view[8] * z + view[12]) * projection[0] + projection[12] + 1) / 2) * gl.drawingBufferWidth,
    (((view[1] * x + view[5] * y + view[9] * z + view[13]) * projection[5] + projection[13] + 1) / 2) * gl.drawingBufferHeight,
  ])
  const sights = points.map((point, i) => {
    const across = ((Math.floor(pixels[i][0]) + 0.5 - pixels[i][0]) * 2) / (projection[0] * gl.drawingBufferWidth)
    const upward = ((Math.floor(pixels[i][1]) + 0.5 - pixels[i][1]) * 2) / (projection[5] * gl.drawingBufferHeight)
    return point.map((value, axis) => value + right[axis] * across + up[axis] * upward) as World
  })
  const levels = (show: boolean) => {
    drawn.parent!.visible = show
    renderer.render(scene, camera)
    return pixels.map(([x, y]) => {
      const pixel = new Uint8Array(4)
      gl.readPixels(Math.floor(x), Math.floor(y), 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel)
      return pixel[1]
    })
  }
  const off = levels(false)
  const on = levels(true)
  return { shown: on.map((level, i) => level - off[i]), sights, back: [view[2], view[6], view[10]] as World }
}

/** More pixels than a stray glint: a ring or a plane drawn faintly across a room covers thousands. */
const MANY_PIXELS = 200

/**
 * How many pixels of two PNG screenshots of one size differ by more than `by` levels in a channel, counted in the page. The
 * software renderer can draw the same picture a level apart from one draw to the next, so an exact comparison would see a change;
 * a ring drawn faintly at the glass's alpha is only some levels above the floor, so the margin is no wider than that noise needs.
 */
function changed(page: Page, a: Buffer, b: Buffer, by = 2): Promise<number> {
  return page.evaluate(
    async ([a, b, by]) => {
      const pixels = async (base64: string) => {
        const bytes = Uint8Array.from(atob(base64), (char) => char.charCodeAt(0))
        const image = await createImageBitmap(new Blob([bytes], { type: 'image/png' }))
        const context = new OffscreenCanvas(image.width, image.height).getContext('2d')!
        context.drawImage(image, 0, 0)
        return context.getImageData(0, 0, image.width, image.height).data
      }
      const [x, y] = await Promise.all([pixels(a), pixels(b)])
      let count = 0
      for (let i = 0; i < x.length; i += 4) {
        if (Math.abs(x[i] - y[i]) > by || Math.abs(x[i + 1] - y[i + 1]) > by || Math.abs(x[i + 2] - y[i + 2]) > by) count++
      }
      return count
    },
    [a.toString('base64'), b.toString('base64'), by] as const,
  )
}
