// Binary LED frames (spec §12.4), decoded into buffers the stage reads in place.
//   v1 (engine M1): [2B id_len LE][id UTF-8][4B seq LE][RGB × leds]
//   v2 (engine M2): [1B stream: 0x01 live | 0x02 preview][2B id_len LE][id UTF-8][4B seq LE][RGB × leds]
// Once a light has its buffer, decoding a frame allocates only a view of the message, and React
// never subscribes to any of this: 60 fps of frames must cost no renders (§13.1). The stage (F2) reads `live` and
// `preview` on each animation frame, and redraws when `version` has moved.
import type { FrameStream, Id } from './contract'

export type FrameVersion = 1 | 2

const STREAM_BYTE: Record<FrameStream, number> = { live: 0x01, preview: 0x02 }

export interface LightFrame {
  /** RGB bytes, three per LED: the same array while the LED count stays the same. */
  rgb: Uint8Array
  /** The server's sequence number for this light and stream; -1 once a reconnect resets it. */
  seq: number
  /** LEDs in the frame: set with the buffer. */
  count: number
  /** When it arrived, in the client clock's seconds. */
  at: number
  /** Frames since the last fps sample. */
  recent: number
}

// A server that sends ids nobody has seen before, frame after frame, can't grow the table forever.
const MAX_IDS = 1024

/** Light ids by their UTF-8 bytes: after the first frame, an id is compared, never decoded. */
class IdTable {
  private readonly byLength = new Map<number, { bytes: Uint8Array; id: Id }[]>()
  private readonly decoder = new TextDecoder('utf-8', { fatal: true })
  private size = 0

  /** The id in bytes[start, start + length), or null if those bytes aren't UTF-8. */
  lookup(bytes: Uint8Array, start: number, length: number): Id | null {
    const known = this.byLength.get(length)
    if (known !== undefined) {
      for (const entry of known) if (sameBytes(entry.bytes, bytes, start)) return entry.id
    }
    const copy = bytes.slice(start, start + length)
    let id: Id
    try {
      id = this.decoder.decode(copy)
    } catch {
      return null
    }
    if (this.size >= MAX_IDS) {
      this.byLength.clear()
      this.size = 0
    }
    const entries = this.byLength.get(length) ?? []
    entries.push({ bytes: copy, id })
    this.byLength.set(length, entries)
    this.size += 1
    return id
  }
}

function sameBytes(known: Uint8Array, bytes: Uint8Array, start: number): boolean {
  for (let i = 0; i < known.length; i++) if (known[i] !== bytes[start + i]) return false
  return true
}

/** Every light's latest frame, per stream. */
export class FrameStore {
  readonly live = new Map<Id, LightFrame>()
  readonly preview = new Map<Id, LightFrame>()
  readonly ids = new IdTable()
  /** Moves with every frame stored: redraw when it has moved. */
  version = 0
  /** Wall-clock ms of the last frame, for §9.4's "This is the last frame, from 19:14:32". */
  lastFrameAt: number | null = null
  /** Binary messages dropped as malformed. */
  malformed = 0

  get(id: Id, stream: FrameStream = 'live'): LightFrame | undefined {
    return (stream === 'live' ? this.live : this.preview).get(id)
  }

  /** Counts a malformed message; decodeFrame returns what this returns. */
  reject(): false {
    this.malformed += 1
    return false
  }

  /** The most live frames any one light received since the last call. */
  sampleFps(): number {
    let most = 0
    for (const frame of this.live.values()) {
      if (frame.recent > most) most = frame.recent
      frame.recent = 0
    }
    return most
  }

  /** After a reconnect a restarted server counts from 1 again, so any seq is new once. */
  resetSeqs(): void {
    for (const frame of this.live.values()) frame.seq = -1
    for (const frame of this.preview.values()) frame.seq = -1
  }

  /** Empty, as on a page just opened. */
  clear(): void {
    this.live.clear()
    this.preview.clear()
    this.version = 0
    this.lastFrameAt = null
    this.malformed = 0
  }

  /** The preview ended (F4): its frames go. */
  clearPreview(): void {
    this.preview.clear()
    this.version += 1
  }
}

/** Decodes one binary message into `frames`. False, and counted, when it's malformed. */
export function decodeFrame(data: ArrayBuffer, version: FrameVersion, frames: FrameStore, now: number): boolean {
  const bytes = new Uint8Array(data)
  // v1 has no stream byte: its frames are live. An empty v2 message reads undefined: rejected.
  const stream = version === 2 ? bytes[0] : STREAM_BYTE.live
  const target = stream === STREAM_BYTE.live ? frames.live : stream === STREAM_BYTE.preview ? frames.preview : null
  if (target === null) return frames.reject()
  let offset = version === 2 ? 1 : 0
  if (bytes.length < offset + 2) return frames.reject()
  const idLength = bytes[offset] | (bytes[offset + 1] << 8)
  offset += 2
  if (idLength === 0 || bytes.length < offset + idLength + 4) return frames.reject()
  const id = frames.ids.lookup(bytes, offset, idLength)
  if (id === null) return frames.reject()
  offset += idLength
  const seq = (bytes[offset] | (bytes[offset + 1] << 8) | (bytes[offset + 2] << 16) | (bytes[offset + 3] << 24)) >>> 0
  offset += 4
  const length = bytes.length - offset
  if (length % 3 !== 0) return frames.reject()

  let frame = target.get(id)
  // v1 sends every light at each poll, whether or not it has a new frame.
  if (frame !== undefined && frame.seq === seq) return true
  if (frame === undefined || frame.rgb.length !== length) {
    frame = { rgb: new Uint8Array(length), seq, count: length / 3, at: now, recent: 0 }
    target.set(id, frame)
  }
  const rgb = frame.rgb
  for (let i = 0; i < length; i++) rgb[i] = bytes[offset + i]
  frame.seq = seq
  frame.at = now
  frame.recent += 1
  frames.version += 1
  frames.lastFrameAt = Date.now()
  return true
}

const encoder = new TextEncoder()
/** Each id's UTF-8 bytes: the mock encodes every light's id at 60 fps. */
const idBytesCache = new Map<Id, Uint8Array>()

/** One frame as the server sends it: for the mock server and the tests. */
export function encodeFrame(
  version: FrameVersion,
  id: Id,
  seq: number,
  rgb: Uint8Array,
  stream: FrameStream = 'live',
): ArrayBuffer {
  let idBytes = idBytesCache.get(id)
  if (idBytes === undefined) {
    idBytes = encoder.encode(id)
    idBytesCache.set(id, idBytes)
  }
  const head = version === 2 ? 1 : 0
  const length = idBytes.length
  const out = new Uint8Array(head + 2 + length + 4 + rgb.length)
  if (version === 2) out[0] = STREAM_BYTE[stream]
  out[head] = length & 0xff
  out[head + 1] = length >> 8
  out.set(idBytes, head + 2)
  const at = head + 2 + length
  out[at] = seq & 0xff
  out[at + 1] = (seq >>> 8) & 0xff
  out[at + 2] = (seq >>> 16) & 0xff
  out[at + 3] = seq >>> 24
  out.set(rgb, at + 4)
  return out.buffer
}
