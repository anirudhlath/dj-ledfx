// The beat on the client (spec §12.4, §5.4). The server sends it at up to 30 Hz, and the UI
// samples it on every animation frame. Between messages the clock runs on at the tempo, and each
// message pulls it back: softly under 5 ms, with a snap at 5 ms or more, as the engine's BeatClock
// corrects its drift. Engine M1's beat carries no server time, so its arrival times it, and its
// band is 50 ms: delivery jitter eases in rather than stepping the beat back and forth.
import type { TempoSource } from './contract'
import type { BeatMessage } from './ws-messages'

/**
 * Seconds since the epoch on the performance clock. It only moves forward, and Playwright's fixed
 * clock (which fixes Date) leaves it running, so beats and watchdogs keep time in e2e.
 */
export function clientNow(): number {
  return (performance.timeOrigin + performance.now()) / 1000
}

/** One beat message, whichever protocol sent it. */
export interface Beat {
  /** Pitch-adjusted. */
  bpm: number
  beatPhase: number
  barPhase: number
  /** 1–4. */
  beatInBar: number
  /** null: the source counts no bars (engine M1's beat). */
  bar: number | null
  pitchPercent: number
  source: TempoSource
  stale: boolean
  /** The beat moves: false while stale, stopped, or at 0 BPM. */
  playing: boolean
  /** Seconds since the epoch on the server's clock; null from engine M1. */
  serverTime: number | null
  /** clientNow() when it arrived. */
  receivedAt: number
}

export function normaliseBeat(message: BeatMessage, receivedAt: number): Beat {
  const shared = {
    bpm: message.bpm,
    beatPhase: message.beat_phase,
    barPhase: message.bar_phase,
    pitchPercent: message.pitch_percent,
    receivedAt,
  }
  if ('source' in message) {
    return {
      ...shared,
      beatInBar: message.beat_in_bar,
      bar: message.bar,
      source: message.source,
      stale: message.stale,
      playing: !message.stale && message.bpm > 0,
      serverTime: message.server_time,
    }
  }
  // Engine M1: Pro DJ Link is its only source, and it counts no bars (decision 9).
  return {
    ...shared,
    beatInBar: message.beat_pos,
    bar: null,
    source: 'prodjlink',
    stale: false,
    playing: message.is_playing && message.bpm > 0,
    serverTime: null,
  }
}

const WINDOW = 64

/** How far the client's clock runs ahead of the server's, in seconds (decision 2). */
export class ClockOffset {
  private readonly gaps = new Float64Array(WINDOW)
  private count = 0
  private next = 0

  add(serverTime: number, receivedAt: number): void {
    if (!Number.isFinite(serverTime) || !Number.isFinite(receivedAt)) return
    this.gaps[this.next] = receivedAt - serverTime
    this.next = (this.next + 1) % WINDOW
    this.count = Math.min(this.count + 1, WINDOW)
  }

  /** The smallest gap in the window, the least-delayed message's; null before any. */
  get value(): number | null {
    if (this.count === 0) return null
    let smallest = Infinity
    for (let i = 0; i < this.count; i++) smallest = Math.min(smallest, this.gaps[i])
    return smallest
  }

  reset(): void {
    this.count = 0
    this.next = 0
  }
}

/** The engine's BeatClock threshold: under it a correction eases in, at or over it the clock snaps. */
const SNAP_S = 0.005
/** The threshold for a beat timed by its arrival: wide enough for delivery jitter. */
const JITTER_SNAP_S = 0.05
/** How much of a small error each message corrects. */
const SOFT_GAIN = 0.1

interface BeatSample {
  beatPhase: number
  barPhase: number
  /** 1–4. */
  beatInBar: number
  bar: number | null
  bpm: number
  running: boolean
}

/** Beats within the bar, in [0, 4). */
const withinBar = (beats: number) => ((beats % 4) + 4) % 4
/** An error in beats, wrapped to (−2, 2]: the near way round the bar. */
const nearWay = (beats: number) => beats - 4 * Math.ceil((beats - 2) / 4)

/**
 * The beat between messages. A position is in beats: counted from the first bar's downbeat when
 * the source counts bars, else within the bar.
 */
export class BeatClock {
  private position = 0
  private at = 0
  private bpm = 0
  private running = false
  private counted = false

  /** A beat with a number that isn't finite is ignored, so a malformed message can't stop the clock. */
  receive(beat: Beat, offset: number | null): void {
    const { bpm, barPhase, bar, serverTime, receivedAt } = beat
    if (![bpm, barPhase, bar ?? 0, serverTime ?? 0, receivedAt, offset ?? 0].every(Number.isFinite)) return
    const counted = bar !== null
    // When the message's beat was true, on this client's clock. Untimed, its arrival stands in.
    const timed = serverTime !== null && offset !== null
    const measuredAt = timed ? serverTime + offset : receivedAt
    let target = (counted ? (bar - 1) * 4 : 0) + barPhase * 4
    if (beat.playing) target += ((receivedAt - measuredAt) * bpm) / 60
    if (!beat.playing || !this.running || counted !== this.counted) {
      this.anchor(target, receivedAt, bpm, beat.playing, counted)
      return
    }
    const predicted = this.positionAt(receivedAt)
    const error = counted ? target - predicted : nearWay(target - predicted)
    const errorS = (Math.abs(error) * 60) / bpm
    const soft = errorS < (timed ? SNAP_S : JITTER_SNAP_S)
    this.anchor(predicted + (soft ? error * SOFT_GAIN : error), receivedAt, bpm, true, counted)
  }

  /** The beat at `now`. Pass the last sample back as `out` to fill it instead of allocating. */
  sample(now: number, out?: BeatSample): BeatSample {
    const position = this.positionAt(now)
    const beats = withinBar(position)
    const sample: BeatSample = out ?? { beatPhase: 0, barPhase: 0, beatInBar: 1, bar: null, bpm: 0, running: false }
    sample.beatPhase = beats % 1
    sample.barPhase = beats / 4
    sample.beatInBar = Math.floor(beats) + 1
    sample.bar = this.counted ? Math.floor(position / 4) + 1 : null
    sample.bpm = this.bpm
    sample.running = this.running
    return sample
  }

  /** Forget the beat: after a reconnect, the next message anchors afresh. */
  reset(): void {
    this.anchor(0, 0, 0, false, false)
  }

  private positionAt(now: number): number {
    return this.running ? this.position + ((now - this.at) * this.bpm) / 60 : this.position
  }

  private anchor(position: number, at: number, bpm: number, running: boolean, counted: boolean): void {
    this.position = counted ? position : withinBar(position)
    this.at = at
    this.bpm = bpm
    this.running = running
    this.counted = counted
  }
}
