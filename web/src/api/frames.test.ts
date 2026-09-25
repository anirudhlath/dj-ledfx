import { beforeEach, describe, expect, it, vi } from 'vitest'
import { FrameStore, decodeFrame, encodeFrame } from './frames'

const rgb = (...values: number[]) => new Uint8Array(values)
const bytes = (...values: number[]) => new Uint8Array(values).buffer

let frames: FrameStore
beforeEach(() => {
  frames = new FrameStore()
})

describe('decodeFrame', () => {
  it("stores a v1 frame under its light's id, as live", () => {
    expect(decodeFrame(encodeFrame(1, 'rope', 7, rgb(1, 2, 3, 4, 5, 6)), 1, frames, 10)).toBe(true)
    expect(frames.get('rope')).toEqual({ rgb: rgb(1, 2, 3, 4, 5, 6), seq: 7, count: 2, at: 10, recent: 1 })
    expect(frames.version).toBe(1)
  })

  it("keeps v2's live and preview streams apart", () => {
    decodeFrame(encodeFrame(2, 'tube', 1, rgb(9, 9, 9), 'live'), 2, frames, 0)
    decodeFrame(encodeFrame(2, 'tube', 1, rgb(1, 1, 1), 'preview'), 2, frames, 0)
    expect(frames.get('tube')?.rgb).toEqual(rgb(9, 9, 9))
    expect(frames.get('tube', 'preview')?.rgb).toEqual(rgb(1, 1, 1))
  })

  it('reads an id that is not ASCII', () => {
    decodeFrame(encodeFrame(2, 'lampe-été', 1, rgb(0, 0, 0)), 2, frames, 0)
    expect(frames.live.has('lampe-été')).toBe(true)
  })

  it('skips a frame it already has, and takes the next seq', () => {
    decodeFrame(encodeFrame(1, 'rope', 5, rgb(1, 1, 1)), 1, frames, 0)
    decodeFrame(encodeFrame(1, 'rope', 5, rgb(2, 2, 2)), 1, frames, 1)
    expect(frames.get('rope')?.rgb).toEqual(rgb(1, 1, 1))
    expect(frames.version).toBe(1)
    decodeFrame(encodeFrame(1, 'rope', 6, rgb(2, 2, 2)), 1, frames, 1)
    expect(frames.get('rope')?.rgb).toEqual(rgb(2, 2, 2))
  })

  // M7: the same seq again, the one frame the store would otherwise skip.
  it('takes a seq it has seen once a reconnect has reset the seqs', () => {
    decodeFrame(encodeFrame(2, 'rope', 500, rgb(1, 1, 1)), 2, frames, 0)
    frames.resetSeqs()
    decodeFrame(encodeFrame(2, 'rope', 500, rgb(2, 2, 2)), 2, frames, 1)
    expect(frames.get('rope')).toMatchObject({ seq: 500, rgb: rgb(2, 2, 2) })
  })

  it('writes into the same buffer while the LED count stays the same', () => {
    decodeFrame(encodeFrame(2, 'rope', 1, rgb(1, 1, 1, 2, 2, 2)), 2, frames, 0)
    const buffer = frames.get('rope')?.rgb
    decodeFrame(encodeFrame(2, 'rope', 2, rgb(3, 3, 3, 4, 4, 4)), 2, frames, 0)
    expect(frames.get('rope')?.rgb).toBe(buffer)
    expect(buffer).toEqual(rgb(3, 3, 3, 4, 4, 4))
  })

  // Review focus 5: a part added to the PC, or a light rediscovered with more LEDs.
  it('reallocates when the LED count changes, and takes a light with no LEDs', () => {
    decodeFrame(encodeFrame(2, 'pc', 1, rgb(1, 1, 1)), 2, frames, 0)
    decodeFrame(encodeFrame(2, 'pc', 2, rgb(1, 1, 1, 2, 2, 2)), 2, frames, 0)
    expect(frames.get('pc')).toMatchObject({ count: 2, rgb: rgb(1, 1, 1, 2, 2, 2) })
    expect(decodeFrame(encodeFrame(2, 'pc', 3, rgb()), 2, frames, 0)).toBe(true)
    expect(frames.get('pc')).toMatchObject({ count: 0, rgb: rgb() })
  })

  it('decodes each id once, however many frames carry it', () => {
    const decode = vi.spyOn(TextDecoder.prototype, 'decode')
    for (let seq = 1; seq <= 100; seq++) decodeFrame(encodeFrame(2, 'rope', seq, rgb(seq, 0, 0)), 2, frames, 0)
    expect(decode).toHaveBeenCalledTimes(1)
  })

  const good = [...new Uint8Array(encodeFrame(2, 'rope', 1, rgb(1, 2, 3)))]
  // Review focus 5: each is dropped and counted, and nothing else changes.
  it.each([
    ['an empty message', bytes()],
    ['an unknown stream byte', bytes(0x07, ...good.slice(1))],
    ['a message too short for its id length', bytes(0x01, 1)],
    ['an id length past the end', bytes(0x01, 200, 0, 0x72, 0x6f)],
    ['a zero-length id', bytes(0x01, 0, 0, 1, 0, 0, 0, 1, 2, 3)],
    ['a missing seq', bytes(0x01, 4, 0, 0x72, 0x6f, 0x70, 0x65, 1, 0)],
    ['an RGB tail that is not whole LEDs', bytes(...good, 9)],
    ['an id that is not UTF-8', bytes(0x01, 2, 0, 0xff, 0xfe, 1, 0, 0, 0, 1, 2, 3)],
  ])('drops and counts %s, and leaves the other lights alone', (_, message) => {
    decodeFrame(encodeFrame(2, 'tube', 1, rgb(7, 7, 7)), 2, frames, 0)
    const version = frames.version
    expect(decodeFrame(message, 2, frames, 1)).toBe(false)
    expect(frames.malformed).toBe(1)
    expect(frames.version).toBe(version)
    expect(frames.get('tube')?.rgb).toEqual(rgb(7, 7, 7))
    expect([...frames.live.keys()]).toEqual(['tube'])
  })

  it('drops a truncated v1 message too', () => {
    expect(decodeFrame(bytes(4, 0, 0x72), 1, frames, 0)).toBe(false)
    expect(frames.malformed).toBe(1)
  })
})

describe('FrameStore', () => {
  it('samples the most live frames any one light received, then starts again', () => {
    for (let seq = 1; seq <= 60; seq++) decodeFrame(encodeFrame(2, 'rope', seq, rgb(0, 0, 0)), 2, frames, 0)
    for (let seq = 1; seq <= 30; seq++) decodeFrame(encodeFrame(2, 'tube', seq, rgb(0, 0, 0)), 2, frames, 0)
    for (let seq = 1; seq <= 90; seq++) decodeFrame(encodeFrame(2, 'tube', seq, rgb(0, 0, 0), 'preview'), 2, frames, 0)
    expect(frames.sampleFps()).toBe(60)
    expect(frames.sampleFps()).toBe(0)
  })

  it("drops the preview's frames when the preview ends, and says so", () => {
    decodeFrame(encodeFrame(2, 'tube', 1, rgb(1, 1, 1), 'preview'), 2, frames, 0)
    frames.clearPreview()
    expect(frames.preview.size).toBe(0)
    expect(frames.version).toBe(2)
  })

  it('remembers when the last frame arrived, on the wall clock', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 8, 23, 19, 14, 32))
    decodeFrame(encodeFrame(2, 'rope', 1, rgb(0, 0, 0)), 2, frames, 0)
    expect(frames.lastFrameAt).toBe(new Date(2026, 8, 23, 19, 14, 32).getTime())
  })

  it('empties, as on a page just opened', () => {
    decodeFrame(encodeFrame(2, 'rope', 1, rgb(0, 0, 0)), 2, frames, 0)
    decodeFrame(encodeFrame(2, 'tube', 1, rgb(0, 0, 0), 'preview'), 2, frames, 0)
    frames.reject()
    frames.clear()
    expect(frames).toMatchObject({ version: 0, lastFrameAt: null, malformed: 0 })
    expect(frames.live.size + frames.preview.size).toBe(0)
  })
})

describe('encodeFrame', () => {
  it('lays v1 and v2 out as §12.4 says', () => {
    expect([...new Uint8Array(encodeFrame(1, 'ab', 258, rgb(1, 2, 3)))]).toEqual([2, 0, 97, 98, 2, 1, 0, 0, 1, 2, 3])
    expect([...new Uint8Array(encodeFrame(2, 'ab', 258, rgb(1, 2, 3), 'preview'))]).toEqual([
      2, 2, 0, 97, 98, 2, 1, 0, 0, 1, 2, 3,
    ])
  })
})
