import { type InstancedBufferAttribute, InstancedMesh, type Object3D, OrthographicCamera, PlaneGeometry, Scene, ShaderMaterial } from 'three'
import { describe, expect, it, vi } from 'vitest'
import { FxStore } from '@/api/fx'
import type { ZoneFx } from '@/api/ws-messages'
import { heroPose } from '@/test/stage'
import { buildScenario } from '@/api/mocks/scenarios'
import { HERO_NOW } from '@/test/live'
import { RENDER, SPEC } from '../design-numbers'
import { FxWriter, LIVE_ONLY } from '../fx-writer'
import { compileFx, FxMaterials, FxMeshes } from './fx-meshes'
import { MIN_RING_WIDTH_M, RING_REACH_WIDTHS, RING_SAMPLES } from './fx-shaders'

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
  return { show, meshes, writer, first: show(...zones) }
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
    const { show, first, writer } = drawn(particles(3))
    const [mesh] = first
    expect(show(particles(10))).toEqual([mesh])
    expect(show()[0].visible).toBe(false)
    const [grown] = show(particles(40))
    expect(grown).not.toBe(mesh)
    expect(grown.count).toBe(40)
    // The new mesh is over the writer's new arrays, not the ones it let go of.
    expect(grown.geometry.getAttribute('centre').array).toBe(writer.particles.arrays[0])
    expect(grown.geometry.getAttribute('size').array).toBe(writer.particles.arrays[2])
  })

  it('sends only the instances it draws up to the GPU', () => {
    const { show } = drawn(particles(3))
    const [mesh] = show(particles(5))
    const centre = mesh.geometry.getAttribute('centre') as InstancedBufferAttribute
    const size = mesh.geometry.getAttribute('size') as InstancedBufferAttribute
    expect(centre.array.length).toBeGreaterThan(5 * 3)
    expect(centre.updateRanges).toEqual([{ start: 0, count: 5 * 3 }])
    expect(size.updateRanges).toEqual([{ start: 0, count: 5 }])
  })

  it('makes its meshes again after it has let go of them', () => {
    const { meshes, writer } = drawn(particles(3))
    meshes.dispose()
    meshes.update()
    expect(meshes.group.children).toHaveLength(1)
    expect((meshes.group.children[0] as InstancedMesh).count).toBe(writer.particles.count)
  })

  it("lets go of its meshes' geometry when they're done, and the materials' own go with FxMaterials", () => {
    const { meshes, first } = drawn(particles(3))
    const geometry = vi.spyOn(first[0].geometry, 'dispose')
    const mesh = vi.spyOn(first[0], 'dispose')
    meshes.dispose()
    expect(meshes.group.children).toEqual([])
    expect(geometry).toHaveBeenCalledOnce()
    expect(mesh).toHaveBeenCalledOnce()
    const materials = new FxMaterials(home)
    const disposed = [materials.particle, materials.ring, materials.plane].map((material) => vi.spyOn(material, 'dispose'))
    materials.dispose()
    for (const dispose of disposed) expect(dispose).toHaveBeenCalledOnce()
  })

  // Final review 1: the programs a draw uses are linked ahead, on meshes like the ones that draw, for the stage's scene.
  it('compiles each material ahead on one instance of an instanced mesh, for the stage, then lets that mesh go', async () => {
    const materials = new FxMaterials(home)
    const camera = new OrthographicCamera()
    const stage = new Scene()
    let compiled: Object3D[] = []
    const compileAsync = vi.fn(async (ahead: Object3D) => {
      compiled = [...ahead.children]
      return ahead
    })
    await compileFx({ compileAsync }, materials, camera, stage)
    expect(compileAsync).toHaveBeenCalledExactlyOnceWith(expect.any(Scene), camera, stage)
    const meshes = compiled as InstancedMesh[]
    expect(meshes.map((mesh) => [mesh instanceof InstancedMesh, mesh.count, mesh.instanceColor])).toEqual(Array(3).fill([true, 1, null]))
    expect(meshes.map((mesh) => mesh.material)).toEqual([materials.particle, materials.ring, materials.plane])
    expect(meshes[0].geometry).toBeInstanceOf(PlaneGeometry)
    const drawnOn = drawn(particles(1)).first[0].geometry as PlaneGeometry
    expect((meshes[0].geometry as PlaneGeometry).parameters).toEqual(drawnOn.parameters)
    // Its geometry goes once the compile is done.
    const geometry = vi.spyOn(PlaneGeometry.prototype, 'dispose')
    await compileFx({ compileAsync }, materials, camera, stage)
    expect(geometry).toHaveBeenCalledOnce()
  })

  it("draws the particles as the render's fireflies, and planes and rings at the glass's alpha", () => {
    const materials = new FxMaterials(home)
    // The glow is the render's gradient: each stop's place and alpha, as the shader's mix between neighbours.
    const stops = RENDER.particle.glow.stops
    const glsl = (value: number) => (Number.isInteger(value) ? `${value}.0` : `${value}`)
    stops.slice(1).forEach((stop, i) => {
      const from = stops[i]
      expect(materials.particle.fragmentShader).toContain(
        `if (r <= ${glsl(stop.at)}) return mix(${glsl(from.alpha)}, ${glsl(stop.alpha)}, (r - ${glsl(from.at)}) / ${glsl(stop.at - from.at)});`,
      )
    })
    expect(materials.ring.uniforms.glassAlpha.value).toBe(SPEC.window.glassAlpha)
    expect(materials.plane.uniforms.glassAlpha.value).toBe(SPEC.window.glassAlpha)
    expect(materials.plane.uniforms.ceiling.value).toBe(home.ceiling)
    const pose = heroPose()
    materials.setView(pose)
    expect(materials.particle.uniforms.pxPerM.value).toBe(pose.zoom)
    expect(materials.plane.uniforms.back.value.toArray()).toEqual(pose.back)
  })

  it('draws a ring as the engine means its width: light falling to 1/e at half of it either side', () => {
    const { ring } = new FxMaterials(home)
    expect(ring).toBeInstanceOf(ShaderMaterial)
    // The quad reaches RING_REACH_WIDTHS widths past the radius, and discards beyond it, so the tail isn't cut.
    const reach = `${RING_REACH_WIDTHS}`
    expect(ring.vertexShader).toContain(`shape.x + ${reach} * width`)
    expect(ring.fragmentShader).toContain(`radius + ${reach} * vShape.y`)
    expect(ring.fragmentShader).toContain('if (rho > reach) discard')
    // The profile is a Gaussian in the distance from the radius over half the width, summed over the sight line for a sphere.
    expect(ring.fragmentShader).toContain('/ hw')
    expect(ring.fragmentShader).toContain('exp(-t * t)')
    expect(ring.fragmentShader).toContain(`i < ${RING_SAMPLES}`)
    // A width of 0 can't divide by zero.
    expect(ring.vertexShader).toContain(`max(shape.y, ${MIN_RING_WIDTH_M})`)
    expect(MIN_RING_WIDTH_M).toBeGreaterThan(0)
  })
})
