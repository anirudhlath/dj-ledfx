import { type InstancedBufferAttribute, InstancedMesh, ShaderMaterial } from 'three'
import { LineSegments2 } from 'three/addons/lines/LineSegments2.js'
import { describe, expect, it } from 'vitest'
import { homeFixture, lightFixtures } from '@/api/mocks/fixtures'
import { stageBodies } from '../bodies'
import { FIT_VIEW, fitPose, LIVE_PADDING } from '../camera'
import { FrameWriter, writerEntries } from '../frame-writer'
import { WRITER_COLOURS } from '../palette'
import { roomMask } from '../room-mask'
import { lightState } from '../show'
import { LIFT_M, LightMeshes } from './light-meshes'

const LIGHTS = lightFixtures('2026-09-23T18:04:00-05:00').map((light) => ({ ...light, status: 'streaming' as const }))
const STATES = new Map(LIGHTS.map((light) => [light.id, lightState(light, undefined)]))
const writer = () => new FrameWriter(writerEntries(stageBodies(LIGHTS), LIGHTS, STATES, homeFixture.rooms), WRITER_COLOURS)

describe("the lights' meshes (§7.5)", () => {
  it('draws one instanced mesh for halos, one for cores, one for pools, and the strips', () => {
    const frames = writer()
    const meshes = new LightMeshes(frames, roomMask(homeFixture.rooms))
    const instanced = meshes.lifted.children.filter((child) => child instanceof InstancedMesh) as InstancedMesh[]
    expect(instanced.map((mesh) => mesh.count)).toEqual([frames.glows, frames.cores])
    expect(meshes.pools!.count).toBe(frames.glows)
    expect(meshes.lifted.children.filter((child) => child instanceof LineSegments2)).toHaveLength(2)
    // The writer's arrays are the attributes: a frame is written once.
    expect(instanced[0].geometry.getAttribute('colour').array).toBe(frames.haloColours)
    meshes.dispose()
  })

  it('sends a written frame to the GPU, and nothing else', () => {
    const meshes = new LightMeshes(writer(), roomMask(homeFixture.rooms))
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
    const meshes = new LightMeshes(writer(), roomMask(homeFixture.rooms))
    const pose = fitPose(homeFixture.outline, { width: 900, height: 700 }, LIVE_PADDING, FIT_VIEW)!
    meshes.setView(pose)
    const halo = (meshes.lifted.children[0] as InstancedMesh).material as ShaderMaterial
    expect(halo.uniforms.viewport.value.toArray()).toEqual([900, 700])
    expect(meshes.lifted.position.toArray()).toEqual(pose.back.map((v) => v * LIFT_M))
    meshes.dispose()
  })

  it('makes nothing for a home with no placed lights', () => {
    const empty = new FrameWriter([], WRITER_COLOURS)
    const meshes = new LightMeshes(empty, roomMask(homeFixture.rooms))
    expect(meshes.lifted.children).toHaveLength(0)
    expect(meshes.pools).toBeNull()
    meshes.dispose()
  })
})
