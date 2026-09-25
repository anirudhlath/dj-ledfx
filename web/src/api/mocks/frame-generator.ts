// Simple moving versions of the looks for the mock's frames (spec §12.5). They only keep the stage
// alive without the engine: the hues are picked here and are no design value, and F2's stage and F5's
// thumbnails draw the real looks. paint() runs 60 times a second for every light, so it allocates
// nothing.
import type { Id, Look } from '../contract'

export const MOTIFS = ['gradient', 'twinkle', 'chase', 'pulse', 'flicker', 'ripple', 'glow'] as const
export type Motif = (typeof MOTIFS)[number]

export interface MotifSpec {
  motif: Motif
  /** Degrees. */
  hue: number
  /** How far the hue wanders along the light, in degrees. */
  spread: number
}

const BY_CATEGORY: Record<Look['category'], MotifSpec> = {
  ambient: { motif: 'glow', hue: 30, spread: 40 },
  tempo: { motif: 'chase', hue: 190, spread: 60 },
  audio: { motif: 'pulse', hue: 280, spread: 50 },
  home: { motif: 'gradient', hue: 25, spread: 30 },
  firmware: { motif: 'flicker', hue: 35, spread: 20 },
}

// The looks the scenarios run get a motif of their own.
const BY_LOOK: Partial<Record<Id, MotifSpec>> = {
  homesunset: { motif: 'gradient', hue: 18, spread: 35 },
  sunset: { motif: 'gradient', hue: 28, spread: 40 },
  fireflies: { motif: 'twinkle', hue: 60, spread: 25 },
  comets: { motif: 'chase', hue: 195, spread: 40 },
  embers: { motif: 'flicker', hue: 14, spread: 18 },
  lava: { motif: 'ripple', hue: 8, spread: 30 },
  doorbell: { motif: 'ripple', hue: 205, spread: 20 },
  goodnight: { motif: 'glow', hue: 240, spread: 15 },
}

export function motifFor(look: Pick<Look, 'id' | 'category'>): MotifSpec {
  return BY_LOOK[look.id ?? ''] ?? BY_CATEGORY[look.category]
}

const clamp01 = (value: number) => Math.min(1, Math.max(0, value))

/** HSV to RGB, written into out[at..at+2]. */
function writeHsv(out: Uint8Array, at: number, hue: number, saturation: number, value: number): void {
  const h = (((hue % 360) + 360) % 360) / 60
  const chroma = value * saturation
  const x = chroma * (1 - Math.abs((h % 2) - 1))
  const m = value - chroma
  let r = 0
  let g = 0
  let b = 0
  if (h < 1) {
    r = chroma
    g = x
  } else if (h < 2) {
    r = x
    g = chroma
  } else if (h < 3) {
    g = chroma
    b = x
  } else if (h < 4) {
    g = x
    b = chroma
  } else if (h < 5) {
    r = x
    b = chroma
  } else {
    r = chroma
    b = x
  }
  out[at] = Math.round((r + m) * 255)
  out[at + 1] = Math.round((g + m) * 255)
  out[at + 2] = Math.round((b + m) * 255)
}

/**
 * Paints `spec` into `out`, three bytes per LED, at `t` seconds. `beatPhase` is 0–1 through the
 * beat, `brightness` 0–1, and `seed` sets one light apart from another running the same look.
 */
export function paint(out: Uint8Array, spec: MotifSpec, t: number, beatPhase: number, brightness: number, seed: number): void {
  const count = out.length / 3
  const onBeat = 1 - beatPhase
  // What each light shares across its LEDs, worked out once per frame.
  const drift = 8 * Math.sin(t * 0.2 + seed)
  const breath = 0.4 * Math.sin(t * 0.8 + seed)
  const level = clamp01(brightness)
  for (let i = 0; i < count; i++) {
    const x = count > 1 ? i / (count - 1) : 0.5
    let hue = spec.hue
    let value = 1
    switch (spec.motif) {
      case 'gradient':
        hue += spec.spread * x + drift
        value = 0.75 + 0.25 * Math.sin(t * 0.5 + x * 3)
        break
      case 'twinkle':
        value = Math.max(0, Math.sin(t * 1.7 + i * 2.39 + seed * 7.1)) ** 6
        break
      case 'chase': {
        const head = (t * 0.25 + beatPhase * 0.25 + seed * 0.13) % 1
        value = Math.max(0, 1 - Math.abs(x - head) * 6)
        hue += spec.spread * value
        break
      }
      case 'pulse':
        value = 0.25 + 0.75 * onBeat * onBeat
        hue += spec.spread * x
        break
      case 'flicker':
        value = 0.55 + 0.45 * Math.sin(t * 9.1 + i * 1.3 + seed) * Math.sin(t * 3.7 + i * 0.7)
        hue += spec.spread * 0.5 * Math.sin(t + i)
        break
      case 'ripple': {
        const wave = Math.sin((x - t * 0.6 - seed * 0.1) * Math.PI * 4)
        value = 0.5 + 0.5 * wave
        hue += spec.spread * 0.5 * (1 + wave)
        break
      }
      case 'glow':
        value = 0.6 + breath
        hue += spec.spread * x
        break
    }
    writeHsv(out, i * 3, hue, 0.85, clamp01(value) * level)
  }
}
