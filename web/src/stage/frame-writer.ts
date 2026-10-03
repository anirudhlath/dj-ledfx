// Turns the frame store's bytes into what the GPU draws (§7.3, §7.5): for each sample a halo and a
// floor pool in one colour, for each compact light one core, for each strip its segments. It writes into arrays
// made once, when which bodies are drawn changes (sameLayout()), so a frame allocates nothing, and
// nor does a `lights` push that changes only colours: setEntries() takes those in place. The light
// layer hands these very arrays to three. Offline and switched-off lights have no entry (§9.1): their
// marks are the overlay's.
import type { Id, Light, Room } from '@/api/contract'
import type { FrameStore } from '@/api/frames'
import { hueOf, isDark, mix, type RGB } from '@/lib/light-colour'
import { anchorIndex, type Body } from './bodies'
import { SPEC } from './design-numbers'
import { coreOf, haloRadiusPx, poolRadiusM } from './light-maths'
import { STAGE_PALETTE } from './palette'
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
  /** The sample its core sits on (its anchor), or −1. */
  coreSample: number
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
  /** The halo's and the pool's colour: the hue at the sample's intensity. */
  readonly glowColours: Float32Array
  /** Radii in CSS px; 0 hides the halo. */
  readonly haloSizes: Float32Array
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
  /** Whether the write so far has changed a value the meshes draw. */
  private changed = false

  /** Laid out for these entries' bodies and rooms; setEntries() changes the rest in place. */
  constructor(entries: readonly WriterEntry[]) {
    const segments = (wide: boolean) =>
      entries.reduce((sum, e) => sum + (e.body.form === 'strip' && e.body.wide === wide ? e.body.samples.length - 1 : 0), 0)
    this.glows = entries.reduce((sum, e) => sum + e.body.samples.length, 0)
    this.cores = entries.filter((e) => e.body.form === 'compact').length
    this.glowCentres = new Float32Array(this.glows * 3)
    this.glowRooms = new Float32Array(this.glows)
    this.glowColours = new Float32Array(this.glows * 3)
    this.haloSizes = new Float32Array(this.glows)
    this.poolRadii = new Float32Array(this.glows)
    this.coreCentres = new Float32Array(this.cores * 3)
    this.coreColours = new Float32Array(this.cores * 3)
    this.coreSizes = new Float32Array(this.cores)
    this.narrow = strip(segments(false))
    this.wide = strip(segments(true))

    const counted = new Set<Id>()
    let glow = 0
    let core = 0
    const next = { narrow: 0, wide: 0 }
    for (const { body, room, streamed, resting } of entries) {
      const slot: Slot = {
        body,
        room,
        streamed,
        resting,
        glow,
        core: -1,
        coreSample: -1,
        strip: null,
        segment: 0,
        counts: !counted.has(body.lightId),
      }
      counted.add(body.lightId)
      body.samples.forEach((sample, s) => {
        this.glowCentres.set(toWorld(sample), (glow + s) * 3)
        this.glowRooms[glow + s] = room
      })
      glow += body.samples.length
      if (body.form === 'compact') {
        slot.core = core
        slot.coreSample = anchorIndex(body)
        this.coreCentres.set(toWorld(body.samples[slot.coreSample]), core * 3)
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

  /**
   * Every drawn light from the store's latest frames (or its resting colour). Allocates nothing, and
   * says whether it changed anything drawn: frames with the same bytes don't, and need no upload or draw.
   */
  write(frames: FrameStore): boolean {
    const { lightOff, stripDark } = STAGE_PALETTE
    this.changed = false
    let leds = 0
    for (const slot of this.slots) {
      const { body, room, resting, strip } = slot
      const frame = slot.streamed ? frames.get(body.lightId) : undefined
      if (frame !== undefined && slot.counts) leds += Math.min(frame.count, body.ledCount)
      const compact = body.form === 'compact'
      const count = body.samples.length
      for (let s = 0; s < count; s++) {
        // The sample's colour: the average of its LEDs in the frame, or without one the resting colour.
        let r = 0
        let g = 0
        let b = 0
        if (frame !== undefined) {
          let n = 0
          // Only LEDs the frame has: one shorter than the map leaves the rest dark, and one longer is cut.
          for (let k = body.offsets[s]; k < body.offsets[s + 1]; k++) {
            const led = body.leds[k]
            if (led >= frame.count) continue
            r += frame.rgb[led * 3]
            g += frame.rgb[led * 3 + 1]
            b += frame.rgb[led * 3 + 2]
            n += 1
          }
          if (n > 0) {
            r /= n
            g /= n
            b /= n
          }
        } else if (resting !== null) {
          r = resting[0]
          g = resting[1]
          b = resting[2]
        }
        const max = Math.max(r, g, b)
        const intensity = max / 255
        const dark = isDark(intensity)
        const hr = hueOf(r, max)
        const hg = hueOf(g, max)
        const hb = hueOf(b, max)
        // Halo and pool: the hue at the light's intensity; the shaders apply the falloff.
        const at = slot.glow + s
        const lit = dark ? 0 : intensity
        this.put(this.glowColours, at * 3, hr * lit)
        this.put(this.glowColours, at * 3 + 1, hg * lit)
        this.put(this.glowColours, at * 3 + 2, hb * lit)
        this.put(this.haloSizes, at, dark ? 0 : haloRadiusPx(compact, intensity))
        this.put(this.poolRadii, at, dark || room === 0 ? 0 : poolRadiusM(body.samples[s][2], intensity, count))
        if (strip !== null) {
          // Visible even when dark: from the dark strip colour toward the hue, by intensity.
          const sr = mix(stripDark[0], hr, intensity)
          const sg = mix(stripDark[1], hg, intensity)
          const sb = mix(stripDark[2], hb, intensity)
          if (s > 0) {
            const end = (slot.segment + s - 1) * 6 + 3
            this.put(strip.colours, end, sr)
            this.put(strip.colours, end + 1, sg)
            this.put(strip.colours, end + 2, sb)
          }
          if (s + 1 < count) {
            const start = (slot.segment + s) * 6
            this.put(strip.colours, start, sr)
            this.put(strip.colours, start + 1, sg)
            this.put(strip.colours, start + 2, sb)
          }
        }
        if (s === slot.coreSample) {
          const at3 = slot.core * 3
          this.put(this.coreSizes, slot.core, dark ? SPEC.core.darkPx : SPEC.core.px)
          this.put(this.coreColours, at3, dark ? lightOff[0] : coreOf(hr, intensity))
          this.put(this.coreColours, at3 + 1, dark ? lightOff[1] : coreOf(hg, intensity))
          this.put(this.coreColours, at3 + 2, dark ? lightOff[2] : coreOf(hb, intensity))
        }
      }
    }
    this.leds = leds
    return this.changed
  }

  /** Writes a value as the array stores it (a 32-bit float), noting whether it changed. */
  private put(array: Float32Array, index: number, value: number): void {
    const stored = Math.fround(value)
    if (array[index] === stored) return
    array[index] = stored
    this.changed = true
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
