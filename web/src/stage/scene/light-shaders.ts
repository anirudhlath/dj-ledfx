// The lights' shaders (§7.3). Halos and cores are screen-space discs: a quad (−1…1) grown to its
// radius in CSS px around its centre, whatever the zoom ("sizeAttenuation: false"). Pools are discs
// on the floor, in metres, drawn only where the room mask holds the pool's own room. Halos and pools
// add (additive blending); falloffs are §7.3's, from SPEC.
import { AdditiveBlending, DataTexture, DoubleSide, NearestFilter, RedFormat, ShaderMaterial, UnsignedByteType, Vector2 } from 'three'
import { SPEC } from '../design-numbers'
import type { RoomMask } from '../room-mask'

/** A disc `size` CSS px in radius around `centre`, facing the camera. */
const DISC_VERTEX = /* glsl */ `
  attribute vec3 centre;
  attribute vec3 colour;
  attribute float size;
  uniform vec2 viewport;
  varying vec2 vOffset;
  varying vec3 vColour;
  void main() {
    vec4 clip = projectionMatrix * modelViewMatrix * vec4(centre, 1.0);
    clip.xy += position.xy * size * 2.0 / viewport * clip.w;
    gl_Position = clip;
    vOffset = position.xy;
    vColour = colour;
  }
`

/** §7.3's falloff: centre at 0, mid at midAt, 0 at the edge. */
const FALLOFF = /* glsl */ `
  uniform float falloffCentre;
  uniform float falloffMid;
  uniform float falloffMidAt;
  float falloff(float r) {
    if (r >= 1.0) return 0.0;
    if (r <= falloffMidAt) return falloffCentre + (falloffMid - falloffCentre) * r / falloffMidAt;
    return falloffMid * (1.0 - (r - falloffMidAt) / (1.0 - falloffMidAt));
  }
`

const falloffUniforms = ({ centre, mid, midAt }: Record<'centre' | 'mid' | 'midAt', number>) => ({
  falloffCentre: { value: centre },
  falloffMid: { value: mid },
  falloffMidAt: { value: midAt },
})

/** §7.3 Halo: additive, the colour (hue × intensity, from the frame writer) times the falloff. */
export function haloMaterial(): ShaderMaterial {
  return new ShaderMaterial({
    uniforms: { viewport: { value: new Vector2(1, 1) }, ...falloffUniforms(SPEC.halo.falloff) },
    vertexShader: DISC_VERTEX,
    fragmentShader: /* glsl */ `
      ${FALLOFF}
      varying vec2 vOffset;
      varying vec3 vColour;
      void main() {
        float f = falloff(length(vOffset));
        if (f <= 0.0) discard;
        gl_FragColor = vec4(vColour * f, 1.0);
      }
    `,
    blending: AdditiveBlending,
    transparent: true,
    depthWrite: false,
  })
}

/** §7.3 Core: a solid dot. */
export function coreMaterial(): ShaderMaterial {
  return new ShaderMaterial({
    uniforms: { viewport: { value: new Vector2(1, 1) } },
    vertexShader: DISC_VERTEX,
    fragmentShader: /* glsl */ `
      varying vec2 vOffset;
      varying vec3 vColour;
      void main() {
        if (length(vOffset) > 1.0) discard;
        gl_FragColor = vec4(vColour, 1.0);
      }
    `,
  })
}

/** The room mask as a texture: one byte per cell, read without filtering. */
export function maskTexture(mask: RoomMask): DataTexture {
  const texture = new DataTexture(mask.data, mask.width, mask.height, RedFormat, UnsignedByteType)
  texture.magFilter = NearestFilter
  texture.minFilter = NearestFilter
  texture.needsUpdate = true
  return texture
}

/** How far above the floor the pools lie, so the floor never hides them. */
export const POOL_LIFT_M = 0.002

/** §7.3 Floor pool: additive, on the floor under its sample, clipped to its room by the mask. */
export function poolMaterial(mask: RoomMask, texture: DataTexture): ShaderMaterial {
  return new ShaderMaterial({
    uniforms: {
      mask: { value: texture },
      maskOrigin: { value: new Vector2(...mask.origin) },
      maskSize: { value: new Vector2(mask.width * mask.cellM, mask.height * mask.cellM) },
      floorY: { value: POOL_LIFT_M },
      ...falloffUniforms(SPEC.pool.falloff),
    },
    vertexShader: /* glsl */ `
      attribute vec3 centre;
      attribute vec3 colour;
      attribute float radius;
      attribute float room;
      uniform float floorY;
      varying vec2 vOffset;
      varying vec3 vColour;
      varying vec2 vPlan;
      varying float vRoom;
      void main() {
        vec3 world = vec3(centre.x + position.x * radius, floorY, centre.z + position.y * radius);
        gl_Position = projectionMatrix * viewMatrix * vec4(world, 1.0);
        vOffset = position.xy;
        vColour = colour;
        vPlan = world.xz;
        vRoom = room;
      }
    `,
    fragmentShader: /* glsl */ `
      ${FALLOFF}
      uniform sampler2D mask;
      uniform vec2 maskOrigin;
      uniform vec2 maskSize;
      varying vec2 vOffset;
      varying vec3 vColour;
      varying vec2 vPlan;
      varying float vRoom;
      void main() {
        float f = falloff(length(vOffset));
        vec2 uv = (vPlan - maskOrigin) / maskSize;
        if (f <= 0.0 || uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0) discard;
        if (abs(texture2D(mask, uv).r * 255.0 - vRoom) > 0.5) discard;
        gl_FragColor = vec4(vColour * f, 1.0);
      }
    `,
    blending: AdditiveBlending,
    transparent: true,
    depthWrite: false,
    // The disc lies on the floor: seen from above, plan (x, y) → world (x, z) turns its winding round.
    side: DoubleSide,
  })
}
