// A light's colour on the stage (§7.3): the core, the halo and the floor pool, built on the hue and the
// intensity src/lib/light-colour.ts splits a colour into. Every number comes from SPEC
// (src/stage/design-numbers.ts).
import { mix } from '@/lib/light-colour'
import { SPEC } from './design-numbers'

/** sRGB channels, 0–1, as the stage draws them (the canvas is `linear`: no conversion). */
export type Colour = [number, number, number]

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
