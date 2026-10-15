// "Effects in space" (§7.4): what the zones' looks are doing in the room, drawn faintly over it. All
// three add (additive blending, as the halos and pools do) and test depth without writing it, so a
// wall in front hides them and they never hide one another.
// - A particle is Main.html's firefly (RENDER.particle): a glow whose radius is the particle's `size`
//   in metres, so the reach drawn is the reach it lights the lamps with, falling off as the render's
//   gradient does, round a core of a share of the glow's radius in CSS px, held between the render's
//   smallest and largest cores, its colour lifted towards white at its own intensity.
// - A ring's `sphere` is a shell seen through: a disc facing the camera, as bright at each point as
//   the shell is thick along the line of sight there, so its rim is brightest. A `circle` lies level,
//   an annulus `width` across, on the floor's pools' lift.
// - A plane is a sheet through the home, clipped to its outline and between its floor and ceiling;
//   with a `ray`, only the half on that side of its point.
// Their brightness is the stage's one number for a translucent surface, SPEC.window.glassAlpha (§7.1's
// glass pane), times the colour, which carries the zone's brightness (§12.4).
import { AdditiveBlending, DoubleSide, ShaderMaterial, Vector2, Vector3, type DataTexture } from 'three'
import { RENDER, SPEC } from '../design-numbers'
import type { RoomMask } from '../room-mask'
import { POOL_LIFT_M } from './light-shaders'

/** A GLSL float literal. */
const glsl = (value: number): string => (Number.isInteger(value) ? `${value}.0` : `${value}`)

/** RENDER.particle's glow: straight lines between the render's gradient stops, 0 past the last. */
const GLOW = /* glsl */ `
  float glow(float r) {
    ${RENDER.particle.glow.stops
      .slice(1)
      .map((stop, i) => {
        const from = RENDER.particle.glow.stops[i]
        return `if (r <= ${glsl(stop.at)}) return mix(${glsl(from.alpha)}, ${glsl(stop.alpha)}, (r - ${glsl(from.at)}) / ${glsl(stop.at - from.at)});`
      })
      .join('\n    ')}
    return 0.0;
  }
`

const ADDS = { blending: AdditiveBlending, transparent: true, depthWrite: false } as const

/** Particles: a quad per particle facing the camera, `size` metres in radius, or wide enough for its core. */
export function particleMaterial(): ShaderMaterial {
  const { share, minPx, maxPx, lift } = RENDER.particle.core
  return new ShaderMaterial({
    uniforms: { pxPerM: { value: 1 } },
    vertexShader: /* glsl */ `
      attribute vec3 centre;
      attribute vec3 colour;
      attribute float size;
      uniform float pxPerM;
      varying vec2 vOffsetM;
      varying vec3 vColour;
      varying float vSize;
      void main() {
        float quad = max(size, ${glsl(maxPx)} / pxPerM);
        vec4 view = modelViewMatrix * vec4(centre, 1.0);
        view.xy += position.xy * quad;
        gl_Position = projectionMatrix * view;
        vOffsetM = position.xy * quad;
        vColour = colour;
        vSize = size;
      }
    `,
    fragmentShader: /* glsl */ `
      ${GLOW}
      uniform float pxPerM;
      varying vec2 vOffsetM;
      varying vec3 vColour;
      varying float vSize;
      void main() {
        float d = length(vOffsetM);
        float corePx = clamp(vSize * pxPerM * ${glsl(share)}, ${glsl(minPx)}, ${glsl(maxPx)});
        float core = 1.0 - smoothstep(corePx - 0.5, corePx + 0.5, d * pxPerM);
        float halo = glow(d / vSize);
        if (core <= 0.0 && halo <= 0.0) discard;
        float intensity = max(vColour.r, max(vColour.g, vColour.b));
        vec3 lifted = vColour + ${glsl(lift)} * (vec3(intensity) - vColour);
        gl_FragColor = vec4(mix(vColour * halo, lifted, core), 1.0);
      }
    `,
    ...ADDS,
  })
}

/** Rings: a sphere's disc faces the camera, and a circle's lies level; `shape` is radius, width and form (1 a circle). */
export function ringMaterial(): ShaderMaterial {
  return new ShaderMaterial({
    uniforms: { glassAlpha: { value: SPEC.window.glassAlpha }, lift: { value: POOL_LIFT_M } },
    vertexShader: /* glsl */ `
      attribute vec3 centre;
      attribute vec3 colour;
      attribute vec3 shape;
      uniform float lift;
      varying vec2 vOffsetM;
      varying vec3 vColour;
      varying vec3 vShape;
      void main() {
        float outer = shape.x + shape.y * 0.5;
        vOffsetM = position.xy * outer;
        if (shape.z > 0.5) {
          vec3 world = centre + vec3(vOffsetM.x, lift, vOffsetM.y);
          gl_Position = projectionMatrix * viewMatrix * vec4(world, 1.0);
        } else {
          vec4 view = modelViewMatrix * vec4(centre, 1.0);
          view.xy += vOffsetM;
          gl_Position = projectionMatrix * view;
        }
        vColour = colour;
        vShape = shape;
      }
    `,
    fragmentShader: /* glsl */ `
      uniform float glassAlpha;
      varying vec2 vOffsetM;
      varying vec3 vColour;
      varying vec3 vShape;
      void main() {
        float rho = length(vOffsetM);
        float outer = vShape.x + vShape.y * 0.5;
        float inner = max(0.0, vShape.x - vShape.y * 0.5);
        if (rho > outer) discard;
        float alpha;
        if (vShape.z > 0.5) {
          if (rho < inner) discard;
          alpha = glassAlpha;
        } else {
          // The shell's thickness along the line of sight here, as a share of its width.
          float chord = 2.0 * (sqrt(max(outer * outer - rho * rho, 0.0)) - sqrt(max(inner * inner - rho * rho, 0.0)));
          alpha = min(1.0, glassAlpha * chord / vShape.y);
        }
        gl_FragColor = vec4(vColour * alpha, 1.0);
      }
    `,
    ...ADDS,
    side: DoubleSide,
  })
}

/** Where a plane may draw: the home's outline as a room mask (one room), its floor and ceiling, and the sphere round it. */
export interface PlaneBounds {
  mask: RoomMask
  texture: DataTexture
  ceilingM: number
  /** The home's middle, in three's world, and how far its farthest corner is from there. */
  centre: [number, number, number]
  reachM: number
}

/**
 * Planes: a square in the plane round the point nearest the home's middle, as wide as the home, drawn
 * inside its outline, between its floor and ceiling and, with a ray, on the ray's side only. Face on it
 * is glassAlpha; turned away it thickens, as a pane of glass seen along it does, to 1.
 */
export function planeMaterial({ mask, texture, ceilingM, centre, reachM }: PlaneBounds): ShaderMaterial {
  return new ShaderMaterial({
    uniforms: {
      mask: { value: texture },
      maskOrigin: { value: new Vector2(...mask.origin) },
      maskSize: { value: new Vector2(mask.width * mask.cellM, mask.height * mask.cellM) },
      ceiling: { value: ceilingM },
      homeCentre: { value: new Vector3(...centre) },
      reach: { value: reachM },
      back: { value: new Vector3(0, 0, 1) },
      glassAlpha: { value: SPEC.window.glassAlpha },
    },
    vertexShader: /* glsl */ `
      attribute vec3 point;
      attribute vec3 planeNormal; // three declares its own normal
      attribute vec3 ray;
      attribute vec3 colour;
      uniform vec3 homeCentre;
      uniform float reach;
      varying vec3 vWorld;
      varying vec3 vPoint;
      varying vec3 vNormal;
      varying vec3 vRay;
      varying vec3 vColour;
      void main() {
        vec3 middle = homeCentre - dot(homeCentre - point, planeNormal) * planeNormal;
        vec3 across = abs(planeNormal.y) < 0.99 ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0);
        vec3 u = normalize(cross(planeNormal, across));
        vec3 v = cross(planeNormal, u);
        vWorld = middle + (u * position.x + v * position.y) * reach;
        gl_Position = projectionMatrix * viewMatrix * vec4(vWorld, 1.0);
        vPoint = point;
        vNormal = planeNormal;
        vRay = ray;
        vColour = colour;
      }
    `,
    fragmentShader: /* glsl */ `
      uniform sampler2D mask;
      uniform vec2 maskOrigin;
      uniform vec2 maskSize;
      uniform float ceiling;
      uniform vec3 back;
      uniform float glassAlpha;
      varying vec3 vWorld;
      varying vec3 vPoint;
      varying vec3 vNormal;
      varying vec3 vRay;
      varying vec3 vColour;
      void main() {
        if (vWorld.y < 0.0 || vWorld.y > ceiling) discard;
        if (dot(vRay, vRay) > 0.0 && dot(vWorld - vPoint, vRay) < 0.0) discard;
        vec2 uv = (vWorld.xz - maskOrigin) / maskSize;
        if (uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0 || texture2D(mask, uv).r == 0.0) discard;
        float facing = abs(dot(vNormal, back));
        float alpha = min(1.0, glassAlpha / max(facing, glassAlpha));
        gl_FragColor = vec4(vColour * alpha, 1.0);
      }
    `,
    ...ADDS,
    side: DoubleSide,
  })
}
