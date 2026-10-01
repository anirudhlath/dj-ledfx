// Turns the frame store's bytes into what the GPU draws (§7.3, §7.5): for each sample a halo and a
// floor pool, for each compact light one core, for each strip its segments. It writes into arrays
// made once, when which bodies are drawn changes (sameLayout()), so a frame allocates nothing, and
// nor does a `lights` push that changes only colours: setEntries() takes those in place. The light
// layer hands these very arrays to three. Offline and switched-off lights have no entry (§9.1): their
// marks are the overlay's.
import type { Id, Light, Room } from '@/api/contract'
import type { FrameStore, LightFrame } from '@/api/frames'
import type { Body } from './bodies'
import { SPEC } from './design-numbers'
import { haloRadiusPx, isDark, liftOf, poolRadiusM, type Colour, type RGB } from './light-maths'
import { toWorld } from './plan'
import { isDrawn, isStreamed, restingColour, type LightState } from './show'

export interface WriterEntry {
  body: Body
  /** Its light's frames are streamed: drawn from them once one has come. */
  streamed: boolean
  /** The colour drawn without a frame; null draws the light dark. */
  resting: RGB | null
  /** The room whose floor its pools may light: 1-based in home.rooms; 0 lights none. */
  room: number
}

export interface WriterColours {
  /** A compact light's core when dark: `--color-stage-light-off`. */
  lightOff: Colour
  /** A strip's segments when dark: RENDER.strip.darkColour. */
  stripDark: Colour
}

/** One LineSegments2's data: six floats per segment, its start then its end. */
export interface StripBuffers {
  segments: number
  positions: Float32Array
  colours: Float32Array
}

interface Slot {
  body: Body
  room: number
  streamed: boolean
  resting: RGB | null
  /** Its first halo and pool. */
  glow: number
  /** Its core, or −1. */
  core: number
  strip: StripBuffers | null
  /** Its first segment in `strip`. */
  segment: number
  /** The first of its light's bodies: the one that counts the light's LEDs. */
  counts: boolean
}

function strip(segments: number): StripBuffers {
  return { segments, positions: new Float32Array(segments * 6), colours: new Float32Array(segments * 6) }
}

export class FrameWriter {
  readonly glows: number
  /** World positions, three floats per sample: the halo's centre; the pool sits on the floor under it. */
  readonly glowCentres: Float32Array
  readonly glowRooms: Float32Array
  readonly haloColours: Float32Array
  /** Radii in CSS px; 0 hides the halo. */
  readonly haloSizes: Float32Array
  readonly poolColours: Float32Array
  /** Radii in metres; 0 hides the pool. */
  readonly poolRadii: Float32Array
  readonly cores: number
  readonly coreCentres: Float32Array
  readonly coreColours: Float32Array
  /** Radii in CSS px. */
  readonly coreSizes: Float32Array
  readonly narrow: StripBuffers
  readonly wide: StripBuffers
  /** The LEDs the last write took from frames. */
  leds = 0
  private readonly slots: Slot[] = []
  private readonly colours: WriterColours
  /** Scratch: each sample's average, three bytes' worth per sample of the longest body. */
  private readonly average: Float32Array

  /** Laid out for these entries' bodies and rooms; setEntries() changes the rest in place. */
  constructor(entries: readonly WriterEntry[], colours: WriterColours) {
    this.colours = colours
    const segments = (wide: boolean) =>
      entries.reduce((sum, e) => sum + (e.body.form === 'strip' && e.body.wide === wide ? e.body.samples.length - 1 : 0), 0)
    this.glows = entries.reduce((sum, e) => sum + e.body.samples.length, 0)
    this.cores = entries.filter((e) => e.body.form === 'compact').length
    this.glowCentres = new Float32Array(this.glows * 3)
    this.glowRooms = new Float32Array(this.glows)
    this.haloColours = new Float32Array(this.glows * 3)
    this.haloSizes = new Float32Array(this.glows)
    this.poolColours = new Float32Array(this.glows * 3)
    this.poolRadii = new Float32Array(this.glows)
    this.coreCentres = new Float32Array(this.cores * 3)
    this.coreColours = new Float32Array(this.cores * 3)
    this.coreSizes = new Float32Array(this.cores)
    this.narrow = strip(segments(false))
    this.wide = strip(segments(true))
    this.average = new Float32Array(3 * Math.max(1, ...entries.map((e) => e.body.samples.length)))

    const counted = new Set<Id>()
    let glow = 0
    let core = 0
    const next = { narrow: 0, wide: 0 }
    for (const { body, room, streamed, resting } of entries) {
      const slot: Slot = { body, room, streamed, resting, glow, core: -1, strip: null, segment: 0, counts: !counted.has(body.lightId) }
      counted.add(body.lightId)
      body.samples.forEach((sample, s) => {
        this.glowCentres.set(toWorld(sample), (glow + s) * 3)
        this.glowRooms[glow + s] = room
      })
      glow += body.samples.length
      if (body.form === 'compact') {
        slot.core = core
        this.coreCentres.set(toWorld(body.samples[body.samples.length - 1]), core * 3)
        core += 1
      } else {
        const which = body.wide ? 'wide' : 'narrow'
        slot.strip = this[which]
        slot.segment = next[which]
        for (let s = 0; s + 1 < body.samples.length; s++) {
          slot.strip.positions.set([...toWorld(body.samples[s]), ...toWorld(body.samples[s + 1])], (slot.segment + s) * 6)
        }
        next[which] += body.samples.length - 1
      }
      this.slots.push(slot)
    }
  }

  /**
   * Whether each light streams and the colour it rests on, from entries laid out as this writer's
   * (sameLayout()): a `lights` push that changes only those reallocates nothing.
   */
  setEntries(entries: readonly WriterEntry[]): void {
    if (entries.length !== this.slots.length) throw new Error('FrameWriter.setEntries: the entries are laid out differently')
    entries.forEach((entry, index) => {
      const slot = this.slots[index]
      slot.streamed = entry.streamed
      slot.resting = entry.resting
    })
  }

  /** Every drawn light from the store's latest frames (or its resting colour). Allocates nothing. */
  write(frames: FrameStore): void {
    let leds = 0
    for (const slot of this.slots) {
      const { body } = slot
      const frame = slot.streamed ? frames.get(body.lightId) : undefined
      if (frame !== undefined && slot.counts) leds += Math.min(frame.count, body.ledCount)
      this.averageOf(slot, frame)
      this.paint(slot)
    }
    this.leds = leds
  }

  private averageOf(slot: Slot, frame: LightFrame | undefined): void {
    const { body, resting: fallback } = slot
    const out = this.average
    for (let s = 0; s < body.samples.length; s++) {
      let r = 0
      let g = 0
      let b = 0
      let n = 0
      if (frame !== undefined) {
        // Only LEDs the frame has: one shorter than the map leaves the rest dark, and one longer is cut.
        for (let k = body.offsets[s]; k < body.offsets[s + 1]; k++) {
          const led = body.leds[k]
          if (led >= frame.count) continue
          r += frame.rgb[led * 3]
          g += frame.rgb[led * 3 + 1]
          b += frame.rgb[led * 3 + 2]
          n += 1
        }
      } else if (fallback !== null) {
        r = fallback[0]
        g = fallback[1]
        b = fallback[2]
        n = 1
      }
      out[s * 3] = n > 0 ? r / n : 0
      out[s * 3 + 1] = n > 0 ? g / n : 0
      out[s * 3 + 2] = n > 0 ? b / n : 0
    }
  }

  private paint(slot: Slot): void {
    const { body, room } = slot
    const { lightOff, stripDark } = this.colours
    const compact = body.form === 'compact'
    const count = body.samples.length
    const avg = this.average
    for (let s = 0; s < count; s++) {
      const max = Math.max(avg[s * 3], avg[s * 3 + 1], avg[s * 3 + 2])
      const intensity = max / 255
      const dark = isDark(intensity)
      // The hue: each channel over the brightest.
      const hr = max > 0 ? avg[s * 3] / max : 0
      const hg = max > 0 ? avg[s * 3 + 1] / max : 0
      const hb = max > 0 ? avg[s * 3 + 2] / max : 0
      const at = slot.glow + s
      // Halo and pool: the hue at the light's intensity; the shaders apply the falloff.
      const lit = dark ? 0 : intensity
      this.haloSizes[at] = dark ? 0 : haloRadiusPx(compact, intensity)
      this.haloColours[at * 3] = hr * lit
      this.haloColours[at * 3 + 1] = hg * lit
      this.haloColours[at * 3 + 2] = hb * lit
      this.poolRadii[at] = dark || room === 0 ? 0 : poolRadiusM(body.samples[s][2], intensity, count)
      this.poolColours[at * 3] = hr * lit
      this.poolColours[at * 3 + 1] = hg * lit
      this.poolColours[at * 3 + 2] = hb * lit
      if (slot.strip !== null) {
        // Visible even when dark: from the dark strip colour toward the hue, by intensity.
        const out = slot.strip.colours
        const r = stripDark[0] + (hr - stripDark[0]) * intensity
        const g = stripDark[1] + (hg - stripDark[1]) * intensity
        const b = stripDark[2] + (hb - stripDark[2]) * intensity
        if (s > 0) {
          const end = (slot.segment + s - 1) * 6 + 3
          out[end] = r
          out[end + 1] = g
          out[end + 2] = b
        }
        if (s + 1 < count) {
          const start = (slot.segment + s) * 6
          out[start] = r
          out[start + 1] = g
          out[start + 2] = b
        }
      }
      if (slot.core >= 0 && s === count - 1) {
        // The core sits on the last sample: a point's only one, a candle's top.
        const lift = liftOf(intensity)
        const at3 = slot.core * 3
        this.coreSizes[slot.core] = dark ? SPEC.core.darkPx : SPEC.core.px
        this.coreColours[at3] = dark ? lightOff[0] : hr + (1 - hr) * lift
        this.coreColours[at3 + 1] = dark ? lightOff[1] : hg + (1 - hg) * lift
        this.coreColours[at3 + 2] = dark ? lightOff[2] : hb + (1 - hb) * lift
      }
    }
  }
}

/** Each drawn body with whether its light streams, the colour it rests on, and its room. */
export function writerEntries(
  bodies: readonly Body[],
  lights: readonly Light[],
  states: ReadonlyMap<Id, LightState>,
  rooms: readonly Room[],
): WriterEntry[] {
  const byId = new Map(lights.map((light) => [light.id, light]))
  return bodies.flatMap((body) => {
    const light = byId.get(body.lightId)
    const state = states.get(body.lightId)
    if (light === undefined || state === undefined || !isDrawn(state)) return []
    const room = rooms.findIndex((candidate) => candidate.id === light.room) + 1
    return [{ body, streamed: isStreamed(state), resting: restingColour(state), room }]
  })
}

/** Whether two sets of entries make the same arrays: the same bodies drawn, in the same rooms. */
export function sameLayout(a: readonly WriterEntry[], b: readonly WriterEntry[]): boolean {
  return a.length === b.length && a.every((entry, index) => entry.body === b[index].body && entry.room === b[index].room)
}
