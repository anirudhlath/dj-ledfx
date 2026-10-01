// A light's colour on the stage (§7.3) and in a swatch (§6.6). One decomposition serves both: an RGB
// triple's intensity is its brightest channel over 255, and its colour is each channel over that
// brightest one. Every number comes from SPEC (src/stage/design-numbers.ts).
import { SPEC } from './design-numbers'

/** Bytes, 0–255, as frames carry them. */
export type RGB = readonly [number, number, number]
/** sRGB channels, 0–1, as the stage draws them (the canvas is `linear`: no conversion). */
export type Colour = [number, number, number]

/** "#RRGGBB" (either case, "#" optional) as bytes; null for anything else. */
export function parseHex(value: string | null | undefined): RGB | null {
  const match = /^#?([0-9a-f]{6})$/i.exec(value?.trim() ?? '')
  if (match === null) return null
  const n = parseInt(match[1], 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}

/** "#RRGGBB" in capitals (§10: hex is uppercase), rounded and clamped. */
export function hexOf([r, g, b]: RGB): string {
  const byte = (v: number) =>
    Math.round(Math.min(255, Math.max(0, v)))
      .toString(16)
      .padStart(2, '0')
  return `#${byte(r)}${byte(g)}${byte(b)}`.toUpperCase()
}

/** 0–1: the brightest channel. */
export const intensityOf = ([r, g, b]: RGB): number => Math.max(r, g, b) / 255

/** §6.6: a light at or below this intensity is dark. The stage uses the same line. */
export const isDark = (intensity: number): boolean => intensity <= SPEC.swatch.darkAt

/** The colour at full brightness: each channel over the brightest. Black stays black. */
export function hueOf([r, g, b]: RGB): Colour {
  const max = Math.max(r, g, b)
  return max === 0 ? [0, 0, 0] : [r / max, g / max, b / max]
}

/** §7.3 Core: how far the colour is lifted toward white. */
export const liftOf = (intensity: number): number => SPEC.core.liftBase + SPEC.core.liftPerIntensity * intensity

/** The core's colour: the hue lifted toward white. */
export function coreColour(hue: Colour, intensity: number): Colour {
  const lift = liftOf(intensity)
  return [hue[0] + (1 - hue[0]) * lift, hue[1] + (1 - hue[1]) * lift, hue[2] + (1 - hue[2]) * lift]
}

/** §7.3 Halo: radius in CSS px; a compact light's is the single-point one, a strip sample's the other. */
export function haloRadiusPx(compact: boolean, intensity: number): number {
  return (compact ? SPEC.halo.pointPx : SPEC.halo.stripPx) * (SPEC.halo.base + SPEC.halo.perIntensity * intensity)
}

/** §7.3 Floor pool: radius in metres for a sample `z` metres up; smaller for a light of many samples. */
export function poolRadiusM(z: number, intensity: number, samples: number): number {
  const { baseM, perZ, intensityBase, perIntensity, multiSample } = SPEC.pool
  return (baseM + perZ * z) * (intensityBase + perIntensity * intensity) * (samples > 1 ? multiSample : 1)
}

export interface Falloff {
  readonly centre: number
  readonly mid: number
  readonly midAt: number
}

/** §7.3's radial falloff at `r` (0 at the centre, 1 at the edge), before intensity: the shaders' formula. */
export function falloff({ centre, mid, midAt }: Falloff, r: number): number {
  if (r >= 1) return 0
  if (r <= midAt) return centre + ((mid - centre) * r) / midAt
  return mid * (1 - (r - midAt) / (1 - midAt))
}

/** `a` toward `b` by `t`. */
export function mix(a: Colour, b: Colour, t: number): Colour {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]
}

const toBytes = (c: Colour): RGB => [c[0] * 255, c[1] * 255, c[2] * 255]
const toColour = (rgb: RGB): Colour => [rgb[0] / 255, rgb[1] / 255, rgb[2] / 255]

/** §6.6 Live: the fill, mixed from SPEC.swatch.fromColour toward the hue; dark shows SPEC.swatch.darkColour. */
export function swatchFill(rgb: RGB): string {
  const intensity = intensityOf(rgb)
  if (isDark(intensity)) return hexOf(parseHex(SPEC.swatch.darkColour)!)
  const from = toColour(parseHex(SPEC.swatch.fromColour)!)
  return hexOf(toBytes(mix(from, hueOf(rgb), Math.min(1, SPEC.swatch.mixBase + intensity))))
}

/** §6.6 Live: the glow, the hue at the intensity's opacity; none when dark. */
export function swatchGlow(rgb: RGB, px: number): string {
  const intensity = intensityOf(rgb)
  if (isDark(intensity)) return 'none'
  const [r, g, b] = toBytes(hueOf(rgb)).map(Math.round)
  return `0 0 ${px}px rgba(${r}, ${g}, ${b}, ${Math.round(intensity * 1000) / 1000})`
}
