import { type InstancedBufferAttribute, InstancedMesh, ShaderMaterial } from 'three'
import { LineSegments2 } from 'three/addons/lines/LineSegments2.js'
import { describe, expect, it, vi } from 'vitest'
import { homeFixture, lightFixtures } from '@/api/mocks/fixtures'
import { HERO_SINCE } from '@/test/live'
import { heroPose, stageWriter } from '@/test/stage'
import { FrameWriter } from '../frame-writer'
import { roomMask } from '../room-mask'
import { LIFT_M, LightMaterials, LightMeshes } from './light-meshes'

const LIGHTS = lightFixtures(HERO_SINCE).map((light) => ({ ...light, status: 'streaming' as const }))
const writer = () => stageWriter(LIGHTS).writer
const materials = () => new LightMaterials(roomMask(homeFixture.rooms))

describe("the lights' meshes (§7.5)", () => {
  it('draws one instanced mesh for halos, one for cores, one for pools, and the strips', () => {
    const frames = writer()
    const meshes = new LightMeshes(frames, materials())
    const instanced = meshes.lifted.children.filter((child) => child instanceof InstancedMesh) as InstancedMesh[]
    expect(instanced.map((mesh) => mesh.count)).toEqual([frames.glows, frames.cores])
    expect(meshes.pools!.count).toBe(frames.glows)
    expect(meshes.lifted.children.filter((child) => child instanceof LineSegments2)).toHaveLength(2)
    // The writer's arrays are the attributes: a frame is written once, and a sample's halo and pool
    // share its centre and colour.
    expect(instanced[0].geometry.getAttribute('colour').array).toBe(frames.glowColours)
    for (const name of ['centre', 'colour']) expect(meshes.pools!.geometry.getAttribute(name)).toBe(instanced[0].geometry.getAttribute(name))
    meshes.dispose()
  })

  it('sends a written frame to the GPU, and nothing else', () => {
    const meshes = new LightMeshes(writer(), materials())
    const halo = meshes.lifted.children[0] as InstancedMesh
    const colour = halo.geometry.getAttribute('colour') as InstancedBufferAttribute
    const centre = halo.geometry.getAttribute('centre') as InstancedBufferAttribute
    const [colourVersion, centreVersion] = [colour.version, centre.version]
    meshes.update()
    expect(colour.version).toBe(colourVersion + 1)
    expect(centre.version).toBe(centreVersion)
    meshes.dispose()
  })

  it('sizes its discs and lines to the stage and lifts them toward the camera', () => {
    const shared = materials()
    const meshes = new LightMeshes(writer(), shared)
    const pose = heroPose({ width: 900, height: 700 })
    shared.setView(pose)
    meshes.setView(pose)
    const halo = (meshes.lifted.children[0] as InstancedMesh).material as ShaderMaterial
    expect(halo.uniforms.viewport.value.toArray()).toEqual([900, 700])
    expect(shared.wide.resolution.toArray()).toEqual([900, 700])
    expect(meshes.lifted.position.toArray()).toEqual(pose.back.map((v) => v * LIFT_M))
    meshes.dispose()
  })

  // I1: the materials are the mask's, so meshes made again for new lights compile no shader.
  it('draws with the materials it is given, and leaves them to their owner', () => {
    const shared = materials()
    const meshes = new LightMeshes(writer(), shared)
    const used = [meshes.pools!, ...meshes.lifted.children].map((object) => (object as InstancedMesh | LineSegments2).material)
    const expected = [shared.pool, shared.halo, shared.core, shared.narrow, shared.wide]
    // Identity only: three's objects are too big to compare by value.
    expect(used.length).toBe(expected.length)
    expect(used.every((material, index) => material === expected[index])).toBe(true)
    const dispose = vi.spyOn(shared.halo, 'dispose')
    meshes.dispose()
    expect(dispose).not.toHaveBeenCalled()
    shared.dispose()
    expect(dispose).toHaveBeenCalledOnce()
  })

  // Mi6: three frees an instanced mesh's own buffers (its instance matrices) only when it's disposed.
  it('lets go of its instanced meshes, not only their geometries and materials', () => {
    const meshes = new LightMeshes(writer(), materials())
    const instanced = [meshes.pools!, ...meshes.lifted.children.filter((child) => child instanceof InstancedMesh)]
    expect(instanced).toHaveLength(3)
    const disposed = instanced.map((mesh) => vi.spyOn(mesh as InstancedMesh, 'dispose'))
    meshes.dispose()
    for (const spy of disposed) expect(spy).toHaveBeenCalledOnce()
  })

  it('makes nothing for a home with no placed lights', () => {
    const empty = new FrameWriter([])
    const meshes = new LightMeshes(empty, materials())
    expect(meshes.lifted.children).toHaveLength(0)
    expect(meshes.pools).toBeNull()
    meshes.dispose()
  })
})
