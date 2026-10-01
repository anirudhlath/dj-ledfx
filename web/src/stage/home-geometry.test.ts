import { describe, expect, it } from 'vitest'
import type { Vec2 } from '@/api/contract'
import { homeFixture } from '@/api/mocks/fixtures'
import { axes, bearingDeg } from './camera'
import { SPEC } from './design-numbers'
import { facesCamera, ghostLines, homePanes, homePrisms, outlineAt, outwardNormals, wallPolygon } from './home-geometry'

const HOME = homeFixture
const SQUARE: Vec2[] = [
  [0, 0],
  [1, 0],
  [1, 1],
  [0, 1],
]

describe("the home's static geometry (§7.1)", () => {
  it('cuts the walls at the home\'s cut height, and windows and glass doors at their sills', () => {
    const prisms = homePrisms(HOME)
    const walls = prisms.filter((prism) => prism.kind === 'wall')
    expect(walls).toHaveLength(HOME.walls.length)
    HOME.walls.forEach((wall, i) => {
      const top = { wall: HOME.wallCutHeight, window: SPEC.window.sillM, 'glass-door': SPEC.glassDoorSillM }[wall.kind]
      expect(walls[i].z1).toBe(top)
    })
    const columns = prisms.filter((prism) => prism.kind === 'column')
    expect(columns).toHaveLength(HOME.columns.length)
    expect(columns[0].z1).toBeCloseTo(HOME.wallCutHeight + SPEC.columnAboveCutM)
    const furniture = prisms.filter((prism) => prism.kind === 'furniture')
    expect(furniture).toHaveLength(HOME.furniture.length)
    const counter = HOME.furniture.find((item) => item.polygon != null)!
    expect(furniture[HOME.furniture.indexOf(counter)].polygon).toEqual(counter.polygon)
  })

  it('gives a wall its thickness either side of its line', () => {
    const polygon = wallPolygon({ a: [0, 0], b: [2, 0], thickness: 0.2 })
    expect(polygon.map(([, y]) => y).sort()).toEqual([-0.1, -0.1, 0.1, 0.1])
    expect(Math.abs(polygon[0][0] - polygon[1][0])).toBeCloseTo(2)
  })

  it('glazes each window and glass door from its sill to the cut, west windows flagged', () => {
    const panes = homePanes(HOME)
    expect(panes).toHaveLength(HOME.walls.filter((wall) => wall.kind !== 'wall').length)
    expect(panes.every((pane) => pane.z1 === HOME.wallCutHeight)).toBe(true)
    expect(panes.filter((pane) => pane.westFacing)).toHaveLength(HOME.walls.filter((wall) => wall.westFacing).length)
  })

  it('draws the ghost volume at the ceiling, with uprights from the cut', () => {
    const lines = ghostLines(HOME)
    expect(lines).toHaveLength(HOME.outline.length * 2)
    expect(lines.slice(0, HOME.outline.length).every(([a, b]) => a[2] === HOME.ceiling && b[2] === HOME.ceiling)).toBe(true)
    expect(lines.at(-1)![0][2]).toBe(HOME.wallCutHeight)
    expect(outlineAt(SQUARE, 0)).toHaveLength(4)
  })

  it('points normals out of a polygon either way it winds', () => {
    for (const polygon of [SQUARE, [...SQUARE].reverse()]) {
      const normals = outwardNormals(polygon)
      polygon.forEach((p, i) => {
        const q = polygon[(i + 1) % polygon.length]
        const middle: Vec2 = [(p[0] + q[0]) / 2 + normals[i][0] * 0.1, (p[1] + q[1]) / 2 + normals[i][1] * 0.1]
        expect(middle[0] < 0 || middle[0] > 1 || middle[1] < 0 || middle[1] > 1).toBe(true)
      })
    }
  })

  it("colours the sides that face §7.2's camera: south and east of the home", () => {
    const { back } = axes(bearingDeg(0), SPEC.camera.tiltDeg)
    expect(facesCamera([0, 1], back)).toBe(true) // a south face
    expect(facesCamera([1, 0], back)).toBe(true) // an east face
    expect(facesCamera([0, -1], back)).toBe(false) // a north face
    expect(facesCamera([-1, 0], back)).toBe(false) // a west face
  })
})
