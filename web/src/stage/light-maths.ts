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

/** A channel of the hue, the colour at full brightness: the channel over the brightest, `max`. Black stays black. */
export const hueOf = (channel: number, max: number): number => (max > 0 ? channel / max : 0)

/** `a` toward `b` by `t`, a channel at a time. */
export const mix = (a: number, b: number, t: number): number => a + (b - a) * t

/** §7.3 Core: how far the colour is lifted toward white. */
export const liftOf = (intensity: number): number => SPEC.core.liftBase + SPEC.core.liftPerIntensity * intensity

/** §7.3 Core: a channel of the core's colour, the hue's channel lifted toward white. */
export const coreOf = (hue: number, intensity: number): number => mix(hue, 1, liftOf(intensity))

/** §7.3 Halo: radius in CSS px; a compact light's is the single-point one, a strip sample's the other. */
export function haloRadiusPx(compact: boolean, intensity: number): number {
  return (compact ? SPEC.halo.pointPx : SPEC.halo.stripPx) * (SPEC.halo.base + SPEC.halo.perIntensity * intensity)
}

/** §7.3 Floor pool: radius in metres for a sample `z` metres up; smaller for a light of many samples. */
export function poolRadiusM(z: number, intensity: number, samples: number): number {
  const { baseM, perZ, intensityBase, perIntensity, multiSample } = SPEC.pool
  return (baseM + perZ * z) * (intensityBase + perIntensity * intensity) * (samples > 1 ? multiSample : 1)
}

// §6.6's two swatch colours, read once: the dark fill, and the colour a live fill is mixed from (0–1).
const DARK_FILL = hexOf(parseHex(SPEC.swatch.darkColour)!)
const FILL_FROM = parseHex(SPEC.swatch.fromColour)!.map((byte) => byte / 255)

/** §6.6 Live: the fill, mixed from SPEC.swatch.fromColour toward the hue; dark shows SPEC.swatch.darkColour. */
export function swatchFill(rgb: RGB): string {
  const intensity = intensityOf(rgb)
  if (isDark(intensity)) return DARK_FILL
  const max = Math.max(...rgb)
  const t = Math.min(1, SPEC.swatch.mixBase + intensity)
  const channel = (c: 0 | 1 | 2) => mix(FILL_FROM[c], hueOf(rgb[c], max), t) * 255
  return hexOf([channel(0), channel(1), channel(2)])
}

/** §6.6 Live: the glow, the hue at the intensity's opacity; none when dark. */
export function swatchGlow(rgb: RGB, px: number): string {
  const intensity = intensityOf(rgb)
  if (isDark(intensity)) return 'none'
  const max = Math.max(...rgb)
  const [r, g, b] = rgb.map((channel) => Math.round(hueOf(channel, max) * 255))
  return `0 0 ${px}px rgba(${r}, ${g}, ${b}, ${Math.round(intensity * 1000) / 1000})`
}
