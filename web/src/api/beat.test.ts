import { describe, expect, it } from 'vitest'
import { BeatClock, ClockOffset, clientNow, normaliseBeat, type Beat } from './beat'
import type { BeatV1, BeatV2 } from './ws-messages'

const V1: BeatV1 = {
  channel: 'beat',
  bpm: 124,
  beat_phase: 0.5,
  bar_phase: 0.375,
  is_playing: true,
  beat_pos: 2,
  pitch_percent: 1.2,
  deck_number: 2,
  deck_name: 'Player 2',
}
const V2: BeatV2 = {
  channel: 'beat',
  bpm: 121.8,
  beat_phase: 0.25,
  bar_phase: 0.3125,
  bar: 42,
  beat_in_bar: 2,
  pitch_percent: 0,
  source: 'music',
  stale: false,
  server_time: 1000,
}

/** A beat at 120 BPM (two beats a second), `beats` into bar `bar`, arriving at `at`. */
function beat(bar: number | null, beats: number, at: number, extra: Partial<Beat> = {}): Beat {
  return {
    bpm: 120,
    beatPhase: beats % 1,
    barPhase: beats / 4,
    beatInBar: Math.floor(beats) + 1,
    bar,
    pitchPercent: 0,
    source: 'internal',
    stale: false,
    playing: true,
    serverTime: null,
    receivedAt: at,
    ...extra,
  }
}

describe('normaliseBeat', () => {
  // Review focus 3: engine M1's beat.
  it("reads today's v1 beat as Pro DJ Link with no bar", () => {
    expect(normaliseBeat(V1, 5)).toEqual({
      bpm: 124,
      beatPhase: 0.5,
      barPhase: 0.375,
      beatInBar: 2,
      bar: null,
      pitchPercent: 1.2,
      source: 'prodjlink',
      stale: false,
      playing: true,
      serverTime: null,
      receivedAt: 5,
    })
  })

  it('reads a v1 beat with no DJ (bpm 0) as stopped', () => {
    expect(normaliseBeat({ ...V1, bpm: 0, is_playing: false }, 5).playing).toBe(false)
  })

  it("reads §12.4's beat", () => {
    expect(normaliseBeat(V2, 7)).toEqual({
      bpm: 121.8,
      beatPhase: 0.25,
      barPhase: 0.3125,
      beatInBar: 2,
      bar: 42,
      pitchPercent: 0,
      source: 'music',
      stale: false,
      playing: true,
      serverTime: 1000,
      receivedAt: 7,
    })
  })

  it('stops the beat while its source is stale', () => {
    expect(normaliseBeat({ ...V2, stale: true }, 7).playing).toBe(false)
  })
})

describe('ClockOffset', () => {
  it('takes the least-delayed of the last 64 messages', () => {
    const offset = new ClockOffset()
    expect(offset.value).toBeNull()
    offset.add(100, 100.04)
    offset.add(101, 101.01)
    offset.add(102, 102.03)
    expect(offset.value).toBeCloseTo(0.01)
    for (let i = 0; i < 64; i++) offset.add(200 + i, 200.02 + i)
    expect(offset.value).toBeCloseTo(0.02)
    offset.reset()
    expect(offset.value).toBeNull()
  })
})

describe('BeatClock', () => {
  it('runs on at the tempo between messages', () => {
    const clock = new BeatClock()
    clock.receive(beat(42, 1.5, 100), null)
    expect(clock.sample(100.25)).toEqual({ beatPhase: 0, barPhase: 0.5, beatInBar: 3, bar: 42, bpm: 120, running: true })
  })

  // Review focus 4.
  it('wraps the beat and the bar without a jump', () => {
    const clock = new BeatClock()
    clock.receive(beat(42, 3.96, 100), null)
    const before = clock.sample(100.01)
    const after = clock.sample(100.03)
    expect(before).toMatchObject({ beatInBar: 4, bar: 42 })
    expect(before.beatPhase).toBeCloseTo(0.98)
    expect(after).toMatchObject({ beatInBar: 1, bar: 43 })
    expect(after.beatPhase).toBeCloseTo(0.02)
    expect(after.barPhase).toBeCloseTo(0.005)
  })

  it('eases a small error in and snaps a large one', () => {
    const soft = new BeatClock()
    soft.receive(beat(1, 0, 100), null)
    // Half a second on, the clock expects beat 1.0. The server says 3 ms further (0.006 beats):
    // under 5 ms, so a tenth of it is taken.
    soft.receive(beat(1, 1.006, 100.5), null)
    expect(soft.sample(100.5).beatPhase).toBeCloseTo(0.0006, 6)

    const hard = new BeatClock()
    hard.receive(beat(1, 0, 100), null)
    // 20 ms off (0.04 beats): the clock lands on the server's beat.
    hard.receive(beat(1, 1.04, 100.5), null)
    expect(hard.sample(100.5).beatPhase).toBeCloseTo(0.04, 6)
  })

  // Review focus 4: engine M1's beat counts no bars, so an error is taken the near way round.
  it('corrects a v1 beat across the bar line forwards, not back', () => {
    const clock = new BeatClock()
    clock.receive(beat(null, 3.98, 100), null)
    // 30 ms on, the clock is at 4.04 beats: 0.04 into the next bar, where the server says it is.
    clock.receive(beat(null, 0.04, 100.03), null)
    const now = clock.sample(100.03)
    expect(now.beatInBar).toBe(1)
    expect(now.barPhase).toBeCloseTo(0.01)
    expect(now.bar).toBeNull()
  })

  // Review focus 4: the server's clock is 2 s ahead, and messages arrive 5–40 ms late.
  it('follows a server clock 2 s ahead through jittery delivery', () => {
    const clock = new BeatClock()
    const offset = new ClockOffset()
    const truth = (serverTime: number) => ((serverTime - 1000) * 120) / 60 // beats since bar 1 began
    const delays = [0.005, 0.04, 0.012, 0.031, 0.007, 0.022]
    let receivedAt = 0
    for (let i = 0; i < 60; i++) {
      const serverTime = 1000 + i / 30
      receivedAt = serverTime - 2 + delays[i % delays.length]
      const beats = truth(serverTime)
      offset.add(serverTime, receivedAt)
      clock.receive({ ...beat(Math.floor(beats / 4) + 1, beats % 4, receivedAt), serverTime }, offset.value)
    }
    const now = receivedAt + 0.01
    const sample = clock.sample(now)
    const position = ((sample.bar ?? 1) - 1) * 4 + sample.barPhase * 4
    // Within 10 ms of the true beat (0.02 beats at 120 BPM).
    expect(Math.abs(position - truth(now + 2))).toBeLessThan(0.02)
  })

  it('holds still while stale, stopped or at 0 BPM', () => {
    for (const extra of [{ stale: true, playing: false }, { playing: false }, { bpm: 0, playing: false }]) {
      const clock = new BeatClock()
      clock.receive(beat(42, 1.5, 100, extra), null)
      expect(clock.sample(101)).toEqual(clock.sample(100))
      expect(clock.sample(101)).toMatchObject({ running: false, beatInBar: 2, bar: 42 })
    }
  })

  it('forgets the beat on reset', () => {
    const clock = new BeatClock()
    clock.receive(beat(42, 1.5, 100), null)
    clock.reset()
    expect(clock.sample(100.5)).toEqual({ beatPhase: 0, barPhase: 0, beatInBar: 1, bar: null, bpm: 0, running: false })
  })
})

it('reads the client clock in seconds since the epoch', () => {
  expect(Math.abs(clientNow() - Date.now() / 1000)).toBeLessThan(1)
})
