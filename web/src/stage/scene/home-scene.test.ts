import { BufferAttribute, Mesh, ShaderMaterial } from 'three'
import { LineSegments2 } from 'three/addons/lines/LineSegments2.js'
import { describe, expect, it } from 'vitest'
import { homeFixture } from '@/api/mocks/fixtures'
import { bearingDeg } from '../camera'
import { STAGE_PALETTE } from '../palette'
import { HomeScene } from './home-scene'

/** Every vertex colour of the solids (walls, columns, furniture). */
function sideColours(scene: HomeScene): number[][] {
  const solid = scene.group.children.find((child) => child instanceof Mesh && (child.material as { vertexColors?: boolean }).vertexColors) as Mesh
  const colours = solid.geometry.getAttribute('color') as BufferAttribute
  return Array.from({ length: colours.count }, (_, i) => [colours.getX(i), colours.getY(i), colours.getZ(i)])
}

describe('the static home (§7.1)', () => {
  it('draws the courtyard, the balcony, the floors, the solids, the glass and the lines', () => {
    const scene = new HomeScene(homeFixture, STAGE_PALETTE, bearingDeg(0))
    const meshes = scene.group.children.filter((child) => child instanceof Mesh && !(child instanceof LineSegments2))
    const lines = scene.group.children.filter((child) => child instanceof LineSegments2)
    // Courtyard, balcony, floors, solids, glass.
    expect(meshes).toHaveLength(5)
    expect(meshes.filter((mesh) => (mesh as Mesh).material instanceof ShaderMaterial)).toHaveLength(2)
    // Balcony edge, floor edges, furniture edges, glass edges, ghost volume.
    expect(lines).toHaveLength(5)
    scene.dispose()
  })

  it('recolours the sides when the camera turns round', () => {
    const scene = new HomeScene(homeFixture, STAGE_PALETTE, bearingDeg(0))
    const before = sideColours(scene)
    scene.turn(bearingDeg(0) + 180)
    const after = sideColours(scene)
    const changed = before.filter((colour, i) => colour.join() !== after[i].join())
    expect(changed.length).toBeGreaterThan(0)
    const [facing, other] = [STAGE_PALETTE.wallSide, STAGE_PALETTE.wallSide2].map((c) => c.map(Math.fround).join())
    const swapped = before.findIndex((colour, i) => colour.join() === facing && after[i].join() === other)
    expect(swapped).toBeGreaterThanOrEqual(0)
    scene.dispose()
  })

  it('sizes its lines and patterns for the stage', () => {
    const scene = new HomeScene(homeFixture, STAGE_PALETTE, bearingDeg(0))
    scene.setView({ width: 800, height: 600 }, 2)
    const line = scene.group.children.find((child) => child instanceof LineSegments2) as LineSegments2
    expect(line.material.resolution.toArray()).toEqual([800, 600])
    const pattern = scene.group.children.map((child) => (child as Mesh).material).find((material) => material instanceof ShaderMaterial) as ShaderMaterial
    expect(pattern.uniforms.pixelRatio.value).toBe(2)
    scene.dispose()
  })

  it('draws a home with no outdoor areas and no windows', () => {
    const plain = { ...homeFixture, outdoor: undefined, walls: homeFixture.walls.filter((wall) => wall.kind === 'wall') }
    const scene = new HomeScene(plain, STAGE_PALETTE, bearingDeg(0))
    expect(scene.group.children.filter((child) => child instanceof Mesh && !(child instanceof LineSegments2))).toHaveLength(2)
    scene.dispose()
  })
})
