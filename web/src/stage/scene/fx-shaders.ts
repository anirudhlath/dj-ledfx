// "Effects in space" (§7.4): what the zones' looks are doing in the room, drawn faintly over it, as the light the
// engine lights the lamps with. The peak of each, face on, is SPEC.window.glassAlpha (§7.1's glass pane) times its colour,
// which carries the zone's brightness (§12.4). All three add (additive blending, as the halos and pools do) and neither
// test depth nor write it: the engine's light passes through walls, the render paints its fireflies over them, and a
// depth test would cut a wide glow off at the floor in a straight line. Rings and planes stop at the home's outline;
// particles don't, since they may wander past it.
// - A particle lights an LED by exp(-(d/size)^2), out to PARTICLE_REACH_SIZES sizes, and its glow falls off the same way
//   across the screen at any height: neither the floor nor the ceiling dims it, as neither stops the engine's light, so
//   a stronger particle always adds more than a weaker one. In its middle is RENDER.particle's core (§7.4's "tiny glowing
//   points"): a share of its size in CSS px, held between the render's smallest and largest cores, its colour lifted
//   towards white at its own intensity.
// - A ring's or a plane's glow is its field's light summed along each line of sight between the floor and the ceiling,
//   so that one crossing through the field's peak, face on, is its peak.
// - A ring's light falls off as a Gaussian from its radius, to 1/e at half its `width` either side (§12.4). A `sphere` is
//   a shell seen through: a disc facing the camera, its rim brightest, with the floor's and the ceiling's cuts in it. A
//   `circle` lies level on the floor's pools' lift, and is that profile with nothing to sum.
// - A plane's light falls off the same way from the plane. With a `ray` it's the half on that side of its point, a wedge
//   whose light falls off by angle, to 1/e at half its `width` in radians either side, and which is as bright to cross
//   anywhere along it, as the LEDs it lights are. Either is drawn on a quad facing the camera, as wide as the home.
import { AdditiveBlending, DoubleSide, ShaderMaterial, Vector2, Vector3, type DataTexture } from 'three'
import { RENDER, SPEC } from '../design-numbers'
import type { RoomMask } from '../room-mask'
import { POOL_LIFT_M } from './light-shaders'

/** A GLSL float literal. */
const glsl = (value: number): string => (Number.isInteger(value) ? `${value}.0` : `${value}`)

const ADDS = { blending: AdditiveBlending, transparent: true, depthTest: false, depthWrite: false } as const

// The camera's axes in three's world: the view matrix's rows.
const RIGHT = 'vec3(viewMatrix[0][0], viewMatrix[1][0], viewMatrix[2][0])'
const UP = 'vec3(viewMatrix[0][1], viewMatrix[1][1], viewMatrix[2][1])'
const BACK = 'vec3(viewMatrix[0][2], viewMatrix[1][2], viewMatrix[2][2])'

/** One crossing of exp(-(d/h)^2) sums to h times this. */
const SQRT_PI = '1.7724538509'

/** How far from a point of some height, along the way back to the camera, the sight meets the floor and the ceiling. */
const ROOM_SPAN = /* glsl */ `
  uniform float ceiling;
  vec2 roomSpan(float height) {
    return vec2(-height, ceiling - height) / max(viewMatrix[1][2], 0.001);
  }
`

/** Whether a point in three's world is inside the home's outline: 1 or 0. */
const OUTLINE = /* glsl */ `
  uniform sampler2D mask;
  uniform vec2 maskOrigin;
  uniform vec2 maskSize;
  float inHome(vec3 world) {
    vec2 uv = (world.xz - maskOrigin) / maskSize;
    if (uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0) return 0.0;
    return texture2D(mask, uv).r == 0.0 ? 0.0 : 1.0;
  }
`

/** How many sizes a particle's light reaches: the engine's REACH (effects/particle_tools.py), where it's 0.2% of its peak. */
export const PARTICLE_REACH_SIZES = 2.5

/**
 * Particles: a quad per particle facing the camera, as wide as its light reaches, or as its core. A sight `d` metres from the
 * particle's middle passes exp(-(d/size)^2) times what it passes through the middle.
 */
export function particleMaterial(): ShaderMaterial {
  const { share, minPx, maxPx, lift } = RENDER.particle.core
  return new ShaderMaterial({
    uniforms: { pxPerM: { value: 1 }, glassAlpha: { value: SPEC.window.glassAlpha } },
    vertexShader: /* glsl */ `
      attribute vec3 centre;
      attribute vec3 colour;
      attribute float size;
      uniform float pxPerM;
      varying vec2 vOffsetM;
      varying vec3 vColour;
      varying float vSize;
      void main() {
        float quad = max(size * ${glsl(PARTICLE_REACH_SIZES)}, ${glsl(maxPx + 0.5)} / pxPerM);
        vOffsetM = position.xy * quad;
        vec4 view = modelViewMatrix * vec4(centre, 1.0);
        view.xy += vOffsetM;
        gl_Position = projectionMatrix * view;
        vColour = colour;
        vSize = size;
      }
    `,
    fragmentShader: /* glsl */ `
      uniform float pxPerM;
      uniform float glassAlpha;
      varying vec2 vOffsetM;
      varying vec3 vColour;
      varying float vSize;
      void main() {
        float d = length(vOffsetM);
        float corePx = clamp(vSize * pxPerM * ${glsl(share)}, ${glsl(minPx)}, ${glsl(maxPx)});
        float core = 1.0 - smoothstep(corePx - 0.5, corePx + 0.5, d * pxPerM);
        float r = d / vSize;
        float halo = r > ${glsl(PARTICLE_REACH_SIZES)} ? 0.0 : glassAlpha * exp(-r * r);
        if (core <= 0.0 && halo <= 0.0) discard;
        float intensity = max(vColour.r, max(vColour.g, vColour.b));
        vec3 lifted = vColour + ${glsl(lift)} * (vec3(intensity) - vColour);
        gl_FragColor = vec4(mix(vColour * halo, lifted, core), 1.0);
      }
    `,
    ...ADDS,
  })
}

/**
 * A ring's quad, and the stretch of a sight summed through a ring or a plane, reach this many widths past its middle:
 * three half-widths, where its light is under e^-9 of its peak. A beam's wedge reaches as many of its widths, in radians.
 */
export const REACH_WIDTHS = 1.5
/** Steps along the line of sight through each side of a sphere's shell. */
export const RING_SAMPLES = 8
/** Steps along the line of sight through a plane. */
export const PLANE_SAMPLES = 8
/** Steps along the line of sight through a beam, even in how it sums (planeMaterial): they bunch up near the beam's point. */
export const BEAM_SAMPLES = 16
/** The narrowest width a ring or a plane is drawn with: a width of 0 would divide by zero. */
export const MIN_WIDTH = 1e-4
/** How near a beam's point its light stops growing, metres: there's an infinity at the point itself. */
const BEAM_MIN_DISTANCE_M = 0.02

/** Where rings and planes may light: the home's outline as a room mask (one room), and its floor and ceiling. */
export interface HomeBounds {
  mask: RoomMask
  texture: DataTexture
  ceilingM: number
}

const withinHome = ({ mask, texture, ceilingM }: HomeBounds) => ({
  mask: { value: texture },
  maskOrigin: { value: new Vector2(...mask.origin) },
  maskSize: { value: new Vector2(mask.width * mask.cellM, mask.height * mask.cellM) },
  ceiling: { value: ceilingM },
  glassAlpha: { value: SPEC.window.glassAlpha },
})

/**
 * Rings: a sphere's disc faces the camera, and a circle's lies level; `shape` is radius, width and form (1 a circle).
 * `width` is the ring's full thickness where its light falls to 1/e (§12.4), so its half-width h = width / 2 and
 * its light is exp(-(d/h)^2) at d metres from the radius. A circle is that profile on the floor, d = |rho - radius|.
 * A sphere's is the profile summed along the line of sight inside the home, d being the distance from the shell there, and
 * normalised so that one crossing of the shell face on is glassAlpha: a pass through its front and back is twice that.
 */
export function ringMaterial(bounds: HomeBounds): ShaderMaterial {
  return new ShaderMaterial({
    uniforms: { ...withinHome(bounds), lift: { value: POOL_LIFT_M } },
    vertexShader: /* glsl */ `
      attribute vec3 centre;
      attribute vec3 colour;
      attribute vec3 shape;
      uniform float lift;
      varying vec2 vOffsetM;
      varying vec3 vWorld;
      varying vec3 vColour;
      varying vec3 vShape;
      void main() {
        float width = max(shape.y, ${glsl(MIN_WIDTH)});
        float reach = shape.x + ${glsl(REACH_WIDTHS)} * width;
        vOffsetM = position.xy * reach;
        vWorld = shape.z > 0.5
          ? centre + vec3(vOffsetM.x, lift, vOffsetM.y)
          : centre + ${RIGHT} * vOffsetM.x + ${UP} * vOffsetM.y;
        gl_Position = projectionMatrix * viewMatrix * vec4(vWorld, 1.0);
        vColour = colour;
        vShape = vec3(shape.x, width, shape.z);
      }
    `,
    fragmentShader: /* glsl */ `
      ${ROOM_SPAN}
      ${OUTLINE}
      uniform float glassAlpha;
      varying vec2 vOffsetM;
      varying vec3 vWorld;
      varying vec3 vColour;
      varying vec3 vShape;
      // The shell's light summed over a stretch of the sight, s metres from the disc's plane.
      float stretch(float from, float to, float rho, float radius, float hw) {
        if (to <= from) return 0.0;
        vec3 back = ${BACK};
        float ds = (to - from) / ${glsl(RING_SAMPLES)};
        float sum = 0.0;
        for (int i = 0; i < ${RING_SAMPLES}; i++) {
          float s = from + (float(i) + 0.5) * ds;
          float t = (sqrt(rho * rho + s * s) - radius) / hw;
          sum += exp(-t * t) * inHome(vWorld + s * back);
        }
        return sum * ds;
      }
      void main() {
        float radius = vShape.x;
        float hw = vShape.y * 0.5;
        float reach = radius + ${glsl(REACH_WIDTHS)} * vShape.y;
        float rho = length(vOffsetM);
        if (rho > reach) discard;
        float alpha;
        if (vShape.z > 0.5) {
          float t = (rho - radius) / hw;
          alpha = glassAlpha * exp(-t * t) * inHome(vWorld);
        } else {
          // Where the sight is in the shell's reach, on each side of the disc's plane, and between the floor and the ceiling.
          float inner = max(radius - ${glsl(REACH_WIDTHS)} * vShape.y, 0.0);
          float s0 = sqrt(max(inner * inner - rho * rho, 0.0));
          float s1 = sqrt(max(reach * reach - rho * rho, 0.0));
          vec2 room = roomSpan(vWorld.y);
          float sum = stretch(max(s0, room.x), min(s1, room.y), rho, radius, hw)
            + stretch(max(-s1, room.x), min(-s0, room.y), rho, radius, hw);
          alpha = min(1.0, glassAlpha * sum / (hw * ${SQRT_PI}));
        }
        gl_FragColor = vec4(vColour * alpha, 1.0);
      }
    `,
    ...ADDS,
    side: DoubleSide,
  })
}

/** And a plane's quad: the home's middle, in three's world, and how far its farthest corner is from there. */
export interface PlaneBounds extends HomeBounds {
  centre: [number, number, number]
  reachM: number
}

/**
 * Planes: a quad round the home's middle, facing the camera, covering all of the home, summing along each line of sight
 * inside the home. A plane's light is exp(-(d/h)^2) at d metres from it, h = width / 2, and one crossing sums to
 * h * sqrt(pi). A beam's is exp(-(angle/h)^2) off its ray, h = width / 2 in radians, and it's over distance * h * sqrt(pi),
 * so that one crossing at any distance sums to the same; its stretch of a sight is first cut to the wedge it reaches, where
 * that is narrower than a half-plane (a wider beam reaches round behind its point, as its LEDs' field does). A line sums
 * 1 / distance as asinh(metres past its nearest point / how near it passes), so the sight is stepped evenly in that, and
 * only the angle is left to sum: even steps in metres would land on the light close to the point, or miss it, by chance.
 */
export function planeMaterial({ centre, reachM, ...bounds }: PlaneBounds): ShaderMaterial {
  return new ShaderMaterial({
    uniforms: { ...withinHome(bounds), homeCentre: { value: new Vector3(...centre) }, reach: { value: reachM } },
    vertexShader: /* glsl */ `
      attribute vec3 point;
      attribute vec3 planeNormal; // three declares its own normal
      attribute vec3 ray;
      attribute vec3 colour;
      attribute float width;
      uniform vec3 homeCentre;
      uniform float reach;
      varying vec3 vWorld;
      varying vec3 vPoint;
      varying vec3 vNormal;
      varying vec3 vRay;
      varying vec3 vColour;
      varying float vWidth;
      void main() {
        vWorld = homeCentre + (${RIGHT} * position.x + ${UP} * position.y) * reach;
        gl_Position = projectionMatrix * viewMatrix * vec4(vWorld, 1.0);
        vPoint = point;
        vNormal = planeNormal;
        vRay = ray;
        vColour = colour;
        vWidth = max(width, ${glsl(MIN_WIDTH)});
      }
    `,
    fragmentShader: /* glsl */ `
      ${ROOM_SPAN}
      ${OUTLINE}
      uniform float glassAlpha;
      varying vec3 vWorld;
      varying vec3 vPoint;
      varying vec3 vNormal;
      varying vec3 vRay;
      varying vec3 vColour;
      varying float vWidth;
      // The part of a span where a line, its value at s being atStart + slope * s, is at least 0. None runs backwards.
      vec2 inSide(vec2 span, float atStart, float slope) {
        if (abs(slope) < 1e-5) return atStart < 0.0 ? vec2(1.0, 0.0) : span;
        float s = -atStart / slope;
        return slope > 0.0 ? vec2(max(span.x, s), span.y) : vec2(span.x, min(span.y, s));
      }
      void main() {
        vec3 back = ${BACK};
        vec3 from = vWorld - vPoint;
        vec2 span = roomSpan(vWorld.y);
        float hw = vWidth * 0.5;
        float sum = 0.0;
        if (dot(vRay, vRay) > 0.0) {
          // Along the ray and off it, at the quad and for each metre along the sight.
          vec2 start = vec2(dot(from, vRay), dot(from, vNormal));
          vec2 run = vec2(dot(back, vRay), dot(back, vNormal));
          float cut = ${glsl(REACH_WIDTHS)} * vWidth;
          if (cut < 1.5707963) {
            float sn = sin(cut);
            float cs = cos(cut);
            span = inSide(span, start.x * sn - start.y * cs, run.x * sn - run.y * cs);
            span = inSide(span, start.x * sn + start.y * cs, run.x * sn + run.y * cs);
          }
          if (span.y <= span.x) discard;
          // How fast the sight moves over the floor (straight down, it doesn't), where it's nearest the point, and how near.
          float speed = max(length(run), 1e-3);
          float toNearest = dot(start, run) / speed;
          float nearest = -toNearest / speed;
          float past = sqrt(max(dot(start, start) - toNearest * toNearest, ${glsl(BEAM_MIN_DISTANCE_M * BEAM_MIN_DISTANCE_M)}));
          float w0 = asinh((span.x - nearest) * speed / past);
          float dw = (asinh((span.y - nearest) * speed / past) - w0) / ${glsl(BEAM_SAMPLES)};
          for (int i = 0; i < ${BEAM_SAMPLES}; i++) {
            float s = nearest + past * sinh(w0 + (float(i) + 0.5) * dw) / speed;
            vec2 at = start + s * run;
            float t = atan(at.y, at.x) / hw;
            sum += exp(-t * t) * inHome(vWorld + s * back);
          }
          sum *= dw / (speed * hw * ${SQRT_PI});
        } else {
          float off = dot(from, vNormal);
          float slope = dot(back, vNormal);
          float reachM = ${glsl(REACH_WIDTHS)} * vWidth;
          if (abs(slope) > 1e-5) {
            float s0 = (-reachM - off) / slope;
            float s1 = (reachM - off) / slope;
            span = vec2(max(span.x, min(s0, s1)), min(span.y, max(s0, s1)));
          } else if (abs(off) > reachM) discard;
          if (span.y <= span.x) discard;
          float ds = (span.y - span.x) / ${glsl(PLANE_SAMPLES)};
          for (int i = 0; i < ${PLANE_SAMPLES}; i++) {
            float s = span.x + (float(i) + 0.5) * ds;
            float t = (off + s * slope) / hw;
            sum += exp(-t * t) * inHome(vWorld + s * back);
          }
          sum *= ds / (hw * ${SQRT_PI});
        }
        float alpha = min(1.0, glassAlpha * sum);
        if (alpha <= 0.0) discard;
        gl_FragColor = vec4(vColour * alpha, 1.0);
      }
    `,
    ...ADDS,
  })
}
