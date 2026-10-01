import { OrthographicCamera, Vector3 } from 'three'
import { describe, expect, it } from 'vitest'
import type { Vec2, Vec3 } from '@/api/contract'
import { homeFixture } from '@/api/mocks/fixtures'
import { applyPose, FIT_VIEW, fitPadding, fitPose, floorPoint, LIVE_PADDING, projectPoint, type View } from './camera'
import { RENDER, SPEC } from './design-numbers'
import { toWorld } from './plan'

const OUTLINE = homeFixture.outline
const STAGE = { width: RENDER.stage.widthPx, height: RENDER.stage.heightPx }
const VIEWS: View[] = [FIT_VIEW, { mode: '3d', rotateDeg: SPEC.rotate.maxDeg, zoom: 1.5 }, { mode: 'plan', rotateDeg: -SPEC.rotate.stepDeg, zoom: 1 }]
const { eastWest, northSouth } = homeFixture.size

describe('the camera (§7.2)', () => {
  it.each(VIEWS)("projects a point as three's camera does: %o", (view) => {
    const pose = fitPose(OUTLINE, STAGE, view)!
    const camera = new OrthographicCamera()
    applyPose(camera, pose)
    for (const point of [[0, 0, 0], [eastWest, northSouth, 0], [3, 4, 2.2]] as Vec3[]) {
      const ndc = new Vector3(...toWorld(point)).project(camera)
      const [x, y] = projectPoint(pose, point)
      expect(x).toBeCloseTo(((ndc.x + 1) / 2) * STAGE.width, 6)
      expect(y).toBeCloseTo(((1 - ndc.y) / 2) * STAGE.height, 6)
    }
  })

  it('fits the outline and its height inside the padding, touching it', () => {
    const pose = fitPose(OUTLINE, STAGE, FIT_VIEW)!
    const points = OUTLINE.flatMap(([x, y]) => [projectPoint(pose, [x, y, 0]), projectPoint(pose, [x, y, SPEC.fit.heightM])])
    const xs = points.map((p) => p[0])
    const ys = points.map((p) => p[1])
    const [left, right, top, bottom] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)]
    expect(left).toBeGreaterThanOrEqual(LIVE_PADDING.side - 1e-6)
    expect(right).toBeLessThanOrEqual(STAGE.width - LIVE_PADDING.side + 1e-6)
    expect(top).toBeGreaterThanOrEqual(LIVE_PADDING.top - 1e-6)
    expect(bottom).toBeLessThanOrEqual(STAGE.height - LIVE_PADDING.bottom + 1e-6)
    const touchesSides = Math.abs(left - LIVE_PADDING.side) < 1e-6 && Math.abs(right - (STAGE.width - LIVE_PADDING.side)) < 1e-6
    const touchesEnds = Math.abs(top - LIVE_PADDING.top) < 1e-6 && Math.abs(bottom - (STAGE.height - LIVE_PADDING.bottom)) < 1e-6
    expect(touchesSides || touchesEnds).toBe(true)
  })

  it('keeps north roughly up and west on the left, in 3D and in Plan', () => {
    for (const mode of ['3d', 'plan'] as const) {
      const pose = fitPose(OUTLINE, STAGE, { ...FIT_VIEW, mode })!
      const [nwX, nwY] = projectPoint(pose, [0, 0, 0])
      const [neX] = projectPoint(pose, [eastWest, 0, 0])
      const [, swY] = projectPoint(pose, [0, northSouth, 0])
      expect(neX).toBeGreaterThan(nwX)
      expect(swY).toBeGreaterThan(nwY)
    }
  })

  it('looks straight down in Plan, so height moves nothing', () => {
    const pose = fitPose(OUTLINE, STAGE, { ...FIT_VIEW, mode: 'plan' })!
    const [x0, y0] = projectPoint(pose, [4, 5, 0])
    const [x1, y1] = projectPoint(pose, [4, 5, 3])
    expect(x1).toBeCloseTo(x0, 6)
    expect(y1).toBeCloseTo(y0, 6)
  })

  it('zooms about the same target', () => {
    const fit = fitPose(OUTLINE, STAGE, FIT_VIEW)!
    const zoomed = fitPose(OUTLINE, STAGE, { ...FIT_VIEW, zoom: 2 })!
    expect(zoomed.zoom).toBeCloseTo(fit.zoom * 2)
    expect(zoomed.target).toEqual(fit.target)
  })

  it('finds the floor point under a pixel', () => {
    for (const view of VIEWS) {
      const pose = fitPose(OUTLINE, STAGE, view)!
      for (const point of [[1, 2], [eastWest / 2, northSouth / 3]] as Vec2[]) {
        const [x, y] = projectPoint(pose, [point[0], point[1], 0])
        const [px, py] = floorPoint(pose, x, y)
        expect(px).toBeCloseTo(point[0], 6)
        expect(py).toBeCloseTo(point[1], 6)
      }
    }
  })

  it("keeps Live's padding at Main.png's stage size, and shrinks it in proportion below", () => {
    expect(fitPadding(STAGE)).toEqual(LIVE_PADDING)
    expect(fitPadding({ width: STAGE.width * 2, height: STAGE.height * 2 })).toEqual(LIVE_PADDING)
    const phone = fitPadding(SPEC.phoneStage)
    const k = Math.min(SPEC.phoneStage.width / STAGE.width, SPEC.phoneStage.height / STAGE.height)
    expect(phone.side).toBeCloseTo(LIVE_PADDING.side * k)
    expect(phone.top).toBeCloseTo(LIVE_PADDING.top * k)
    expect(phone.bottom).toBeCloseTo(LIVE_PADDING.bottom * k)
  })

  // Review focus 4: a narrow window, a phone's stage, or one not laid out yet.
  it('fits a 320 px stage and a zero-size one without NaN', () => {
    const narrow = fitPose(OUTLINE, { width: 320, height: 220 }, FIT_VIEW)!
    expect([...narrow.target, narrow.zoom].every(Number.isFinite)).toBe(true)
    expect(narrow.zoom).toBeGreaterThan(0)
    for (const [x, y] of OUTLINE.map(([px, py]) => projectPoint(narrow, [px, py, 0]))) {
      expect(x).toBeGreaterThanOrEqual(0)
      expect(x).toBeLessThanOrEqual(320)
      expect(y).toBeGreaterThanOrEqual(0)
      expect(y).toBeLessThanOrEqual(220)
    }
    expect(fitPose(OUTLINE, { width: 0, height: 0 }, FIT_VIEW)).toBeNull()
    expect(fitPose(OUTLINE, { width: Number.NaN, height: 10 }, FIT_VIEW)).toBeNull()
    expect(fitPose([], STAGE, FIT_VIEW)).toBeNull()
    const tiny = fitPose(OUTLINE, { width: 1, height: 1 }, FIT_VIEW)!
    expect(Number.isFinite(tiny.zoom) && tiny.zoom > 0).toBe(true)
  })
})
