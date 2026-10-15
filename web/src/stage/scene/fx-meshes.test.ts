import { InstancedMesh } from 'three'
import { describe, expect, it } from 'vitest'
import { FxStore } from '@/api/fx'
import type { ZoneFx } from '@/api/ws-messages'
import { heroPose } from '@/test/stage'
import { buildScenario } from '@/api/mocks/scenarios'
import { HERO_NOW } from '@/test/live'
import { RENDER, SPEC } from '../design-numbers'
import { FxWriter, LIVE_ONLY } from '../fx-writer'
import { FxMaterials, FxMeshes } from './fx-meshes'

const { home } = buildScenario('hero', HERO_NOW)

const particles = (count: number): ZoneFx => ({
  zoneId: 'living',
  stream: 'live',
  particles: Array.from({ length: count }, (_, i) => [i, 1, 1, 1, 1, 1, 0.3] as [number, number, number, number, number, number, number]),
})

function drawn(...zones: ZoneFx[]) {
  const fx = new FxStore()
  const writer = new FxWriter()
  const meshes = new FxMeshes(writer, new FxMaterials(home))
  const show = (...next: ZoneFx[]) => {
    fx.apply({ channel: 'fx', zones: next })
    writer.write(fx, LIVE_ONLY)
    meshes.update()
    return meshes.group.children as InstancedMesh[]
  }
  return { show, meshes, first: show(...zones) }
}

describe('the effects in space (§7.4)', () => {
  it('draws as many of each as the picture holds, one mesh each', () => {
    const { first } = drawn(particles(3), {
      zoneId: 'office',
      stream: 'live',
      rings: [{ center: [1, 1, 0], radius: 1, width: 0.2, rgb: [1, 1, 1], form: 'circle' }],
    })
    expect(first.map((mesh) => mesh.count)).toEqual([3, 1])
    expect(first.every((mesh) => mesh.frustumCulled === false)).toBe(true)
  })

  it('keeps its meshes while the arrays hold the picture, hides one with nothing to draw, and makes a new one when they grow', () => {
    const { show, first } = drawn(particles(3))
    const [mesh] = first
    expect(show(particles(10))).toEqual([mesh])
    expect(show()[0].visible).toBe(false)
    const [grown] = show(particles(40))
    expect(grown).not.toBe(mesh)
    expect(grown.count).toBe(40)
  })

  it("lets go of its meshes, and the materials of theirs, when they're done", () => {
    const { meshes } = drawn(particles(3))
    meshes.dispose()
    expect(meshes.group.children).toEqual([])
  })

  it("draws the particles as the render's fireflies, and planes and rings at the glass's alpha", () => {
    const materials = new FxMaterials(home)
    for (const stop of RENDER.particle.glow.stops) expect(materials.particle.fragmentShader).toContain(`${stop.alpha}`)
    expect(materials.ring.uniforms.glassAlpha.value).toBe(SPEC.window.glassAlpha)
    expect(materials.plane.uniforms.glassAlpha.value).toBe(SPEC.window.glassAlpha)
    expect(materials.plane.uniforms.ceiling.value).toBe(home.ceiling)
    const pose = heroPose()
    materials.setView(pose)
    expect(materials.particle.uniforms.pxPerM.value).toBe(pose.zoom)
    expect(materials.plane.uniforms.back.value.toArray()).toEqual(pose.back)
  })
})
