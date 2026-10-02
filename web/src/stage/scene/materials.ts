// The home's materials (§7.1). The canvas is `linear` and `flat`, so a colour's 0–1 sRGB numbers
// reach the screen as they are: colours are set with setRGB on three's working space, never from a
// hex string, which three would convert. Patterns the renders draw in screen space (the courtyard's
// dots, the balcony's hatch) are drawn per pixel, in CSS px. Every face is two-sided: home.json's
// polygons wind either way, and plan (x, y) → world (x, z) turns a winding round besides.
import { Color, DoubleSide, MeshBasicMaterial, ShaderMaterial } from 'three'
import { LineMaterial } from 'three/addons/lines/LineMaterial.js'
import { RENDER, SPEC } from '../design-numbers'
import type { Colour } from '../light-maths'
import { STAGE_PALETTE } from '../palette'
import { radians } from '../plan'

/** A palette colour for three, set as it is (see above). */
export const rgb = (colour: Colour): Color => new Color().setRGB(...colour)

/** One flat colour. */
export function flatMaterial(colour: Colour): MeshBasicMaterial {
  return new MeshBasicMaterial({ color: rgb(colour), side: DoubleSide })
}

/** Walls, columns and furniture: their vertex colours. */
export function solidMaterial(): MeshBasicMaterial {
  return new MeshBasicMaterial({ vertexColors: true, side: DoubleSide })
}

/** §7.1 Windows: "a glass pane (text at SPEC.window.glassAlpha)". */
export function glassMaterial(): MeshBasicMaterial {
  return new MeshBasicMaterial({
    color: rgb(STAGE_PALETTE.text),
    transparent: true,
    opacity: SPEC.window.glassAlpha,
    side: DoubleSide,
    depthWrite: false,
  })
}

/** A screen-space line: `width` CSS px, the colour at `alpha`. Its resolution is the stage's CSS size. */
export function lineMaterial(colour: Colour, width: number, alpha = 1): LineMaterial {
  return new LineMaterial({ color: rgb(colour), linewidth: width, transparent: alpha < 1, opacity: alpha, worldUnits: false })
}

const SCREEN_VERTEX = /* glsl */ `
  void main() {
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`

/** §7.1 Courtyard: its colour, with RENDER.courtyard's faint dots on a CSS px grid. */
export function courtyardMaterial(): ShaderMaterial {
  return new ShaderMaterial({
    uniforms: {
      base: { value: rgb(STAGE_PALETTE.courtyard) },
      dot: { value: rgb(STAGE_PALETTE.courtyardDot) },
      spacing: { value: RENDER.courtyard.dotSpacingPx },
      radius: { value: RENDER.courtyard.dotRadiusPx },
      strength: { value: RENDER.courtyard.opacity },
      pixelRatio: { value: 1 },
    },
    side: DoubleSide,
    vertexShader: SCREEN_VERTEX,
    fragmentShader: /* glsl */ `
      uniform vec3 base;
      uniform vec3 dot;
      uniform float spacing;
      uniform float radius;
      uniform float strength;
      uniform float pixelRatio;
      void main() {
        vec2 cell = mod(gl_FragCoord.xy / pixelRatio, spacing) - 0.5 * spacing;
        float on = 1.0 - smoothstep(radius - 0.5, radius + 0.5, length(cell));
        gl_FragColor = vec4(mix(base, dot, on * strength), 1.0);
      }
    `,
  })
}

/** §7.1 Balcony: SPEC.balconyHatchDeg hatch lines, RENDER.balcony's spacing, width and colour. */
export function hatchMaterial(): ShaderMaterial {
  return new ShaderMaterial({
    uniforms: {
      colour: { value: rgb(STAGE_PALETTE.balconyHatch) },
      spacing: { value: RENDER.balcony.hatchSpacingPx },
      width: { value: RENDER.balcony.hatchWidthPx },
      angle: { value: radians(SPEC.balconyHatchDeg) },
      pixelRatio: { value: 1 },
    },
    transparent: true,
    depthWrite: false,
    side: DoubleSide,
    vertexShader: SCREEN_VERTEX,
    fragmentShader: /* glsl */ `
      uniform vec3 colour;
      uniform float spacing;
      uniform float width;
      uniform float angle;
      uniform float pixelRatio;
      void main() {
        vec2 p = gl_FragCoord.xy / pixelRatio;
        float across = mod(p.x * cos(angle) + p.y * sin(angle), spacing);
        float distance = min(across, spacing - across);
        float on = 1.0 - smoothstep(0.5 * width - 0.5, 0.5 * width + 0.5, distance);
        if (on <= 0.0) discard;
        gl_FragColor = vec4(colour, on);
      }
    `,
  })
}
