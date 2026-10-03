// The stage's camera (§7.2): orthographic, turned and tilted as §7.2 says, fitted to the outline
// plus SPEC.fit.heightM of height inside the padding. A pose is plain numbers, so the canvas and the
// overlays (labels, marks, the tooltip) project with the same one, and tests need no WebGL.
import type { OrthographicCamera } from 'three'
import type { Vec2, Vec3 } from '@/api/contract'
import type { ElementSize } from '@/lib/use-element-size'
import { RENDER, SPEC } from './design-numbers'
import { bearingVector, radians, toWorld } from './plan'

export type ViewMode = '3d' | 'plan'

/** What the owner chose with the view controls (§7.2). */
export interface View {
  mode: ViewMode
  /** Orbit around the vertical, in degrees: SPEC.rotate's steps within ±SPEC.rotate.maxDeg. */
  rotateDeg: number
  /** 1 is the fit. */
  zoom: number
}

export const FIT_VIEW: View = { mode: '3d', rotateDeg: 0, zoom: 1 }

/** CSS px kept clear at the stage's edges. */
export interface Padding {
  side: number
  top: number
  bottom: number
}

/** Desktop Live's padding (§7.2). */
export const LIVE_PADDING: Padding = { side: SPEC.fit.sidePx, top: SPEC.fit.topPx, bottom: SPEC.fit.bottomPx }

/** Everything that places the camera: three's world, in metres; zoom is CSS px per metre. */
export interface CameraPose {
  target: Vec3
  /** Unit vectors: screen right, screen up, and from the target toward the camera. */
  right: Vec3
  up: Vec3
  back: Vec3
  zoom: number
  width: number
  height: number
}

/** How far the camera stands back from its target; any distance past the home does. */
export const EYE_DISTANCE_M = 100
const NEAR_M = 1
const FAR_M = 200

const dot = (a: Vec3, b: Vec3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
const cross = (a: Vec3, b: Vec3): Vec3 => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
function unit(v: Vec3): Vec3 {
  const length = Math.hypot(v[0], v[1], v[2]) || 1
  return [v[0] / length, v[1] / length, v[2] / length]
}
const along = (v: Vec3, k: number): Vec3 => [v[0] * k, v[1] * k, v[2] * k]
const plus = (...vs: Vec3[]): Vec3 => vs.reduce((sum, v) => [sum[0] + v[0], sum[1] + v[1], sum[2] + v[2]], [0, 0, 0])

/**
 * Where the camera stands, as a plan bearing from the home: clockwise from north. §7.2's turn puts
 * it south-south-east of the home looking north-north-west; rotating orbits it.
 */
export const bearingDeg = (rotateDeg: number) => 180 - SPEC.camera.turnDeg + rotateDeg

/** The camera's axes in three's world for a bearing and a tilt above the horizon. */
export function axes(bearing: number, tiltDeg: number): { right: Vec3; up: Vec3; back: Vec3 } {
  const [x, y] = bearingVector(bearing)
  const t = radians(tiltDeg)
  // three's (x, z) is the plan's (x, y).
  const back = unit([Math.cos(t) * x, Math.sin(t), Math.cos(t) * y])
  // Straight down, "up" on screen is the way the camera faces, so Plan keeps the turn.
  const forward: Vec3 = [-x, 0, -y]
  const worldUp: Vec3 = tiltDeg >= 89.999 ? forward : [0, 1, 0]
  const right = unit(cross(worldUp, back))
  const up = cross(back, right)
  return { right, up, back }
}

/**
 * The padding for a stage of this size: Live's at Main.png's stage size or larger, and in proportion
 * on a smaller one (a narrow window, the phone's stage), so the home keeps the same share of it.
 */
export function fitPadding(size: ElementSize): Padding {
  const k = Math.min(1, size.width / RENDER.stage.widthPx, size.height / RENDER.stage.heightPx)
  return { side: LIVE_PADDING.side * k, top: LIVE_PADDING.top * k, bottom: LIVE_PADDING.bottom * k }
}

/**
 * The pose that fits the outline, from the floor to SPEC.fit.heightM, inside the padding, for the
 * view, tilted `tiltDeg` above the horizon (§7.2; focus framing tilts SPEC.focus.tiltDeg); Plan looks
 * straight down whatever the tilt. Null while the stage has no size or the outline no points.
 */
export function fitPose(outline: readonly Vec2[], size: ElementSize, view: View, tiltDeg: number = SPEC.camera.tiltDeg): CameraPose | null {
  if (!(size.width > 0 && size.height > 0) || outline.length === 0) return null
  const { right, up, back } = axes(bearingDeg(view.rotateDeg), view.mode === 'plan' ? 90 : tiltDeg)
  const corners = outline.flatMap(([x, y]) => [toWorld([x, y, 0]), toWorld([x, y, SPEC.fit.heightM])])
  const span = (axis: Vec3): Vec2 => {
    const values = corners.map((corner) => dot(corner, axis))
    return [Math.min(...values), Math.max(...values)]
  }
  const [u0, u1] = span(right)
  const [v0, v1] = span(up)
  const [w0, w1] = span(back)
  const pad = fitPadding(size)
  const fits = [(size.width - 2 * pad.side) / (u1 - u0), (size.height - pad.top - pad.bottom) / (v1 - v0)].filter(
    (k) => Number.isFinite(k) && k > 0,
  )
  const fit = fits.length > 0 ? Math.min(...fits) : 1
  // The box sits between the top and bottom padding, not in the middle of the stage.
  const lift = (pad.top - pad.bottom) / 2 / fit
  const target = plus(along(right, (u0 + u1) / 2), along(up, (v0 + v1) / 2 + lift), along(back, (w0 + w1) / 2))
  return { target, right, up, back, zoom: fit * view.zoom, width: size.width, height: size.height }
}

/** A plan point (metres) in CSS px from the stage's top left, as the camera draws it. */
export function projectPoint(pose: CameraPose, point: Vec3): Vec2 {
  const world = toWorld(point)
  const rel: Vec3 = [world[0] - pose.target[0], world[1] - pose.target[1], world[2] - pose.target[2]]
  return [pose.width / 2 + dot(rel, pose.right) * pose.zoom, pose.height / 2 - dot(rel, pose.up) * pose.zoom]
}

/** The plan point (x, y) on the floor under a CSS px position on the stage. */
export function floorPoint(pose: CameraPose, x: number, y: number): Vec2 {
  const u = (x - pose.width / 2) / pose.zoom
  const v = (pose.height / 2 - y) / pose.zoom
  const onScreen = plus(pose.target, along(pose.right, u), along(pose.up, v))
  // Slide along the view direction down to the floor (three's y = 0).
  const toFloor = onScreen[1] / pose.back[1]
  return [onScreen[0] - pose.back[0] * toFloor, onScreen[2] - pose.back[2] * toFloor]
}

/** Puts three's camera where the pose says. */
export function applyPose(camera: OrthographicCamera, pose: CameraPose): void {
  camera.left = -pose.width / 2
  camera.right = pose.width / 2
  camera.top = pose.height / 2
  camera.bottom = -pose.height / 2
  camera.near = NEAR_M
  camera.far = FAR_M
  camera.zoom = pose.zoom
  camera.position.set(...plus(pose.target, along(pose.back, EYE_DISTANCE_M)))
  camera.up.set(...pose.up)
  camera.lookAt(...pose.target)
  camera.updateProjectionMatrix()
  camera.updateMatrixWorld()
}
