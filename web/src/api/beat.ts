// The beat on the client (spec §12.4, §5.4). The server sends it at up to 30 Hz, and the UI
// samples it on every animation frame. Between messages the clock runs on at the tempo, and each
// message pulls it back: softly under 5 ms, with a snap at 5 ms or more, as the engine's BeatClock
// corrects its drift.
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
  if ('source' in message) {
    return {
      bpm: message.bpm,
      beatPhase: message.beat_phase,
      barPhase: message.bar_phase,
      beatInBar: message.beat_in_bar,
      bar: message.bar,
      pitchPercent: message.pitch_percent,
      source: message.source,
      stale: message.stale,
      playing: !message.stale && message.bpm > 0,
      serverTime: message.server_time,
      receivedAt,
    }
  }
  // Engine M1: Pro DJ Link is its only source, and it counts no bars (decision 9).
  return {
    bpm: message.bpm,
    beatPhase: message.beat_phase,
    barPhase: message.bar_phase,
    beatInBar: message.beat_pos,
    bar: null,
    pitchPercent: message.pitch_percent,
    source: 'prodjlink',
    stale: false,
    playing: message.is_playing && message.bpm > 0,
    serverTime: null,
    receivedAt,
  }
}

const WINDOW = 64

/** How far the client's clock runs ahead of the server's, in seconds (decision 2). */
export class ClockOffset {
  private readonly gaps = new Float64Array(WINDOW)
  private count = 0
  private next = 0

  add(serverTime: number, receivedAt: number): void {
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
export const SNAP_S = 0.005
/** How much of a small error each message corrects. */
export const SOFT_GAIN = 0.1

export interface BeatSample {
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

  receive(beat: Beat, offset: number | null): void {
    const counted = beat.bar !== null
    // When the message's beat was true, on this client's clock.
    const measuredAt = beat.serverTime !== null && offset !== null ? beat.serverTime + offset : beat.receivedAt
    let target = (beat.bar !== null ? (beat.bar - 1) * 4 : 0) + beat.barPhase * 4
    if (beat.playing) target += ((beat.receivedAt - measuredAt) * beat.bpm) / 60
    if (!beat.playing || !this.running || counted !== this.counted) {
      this.anchor(target, beat.receivedAt, beat.bpm, beat.playing, counted)
      return
    }
    const predicted = this.positionAt(beat.receivedAt)
    const error = counted ? target - predicted : nearWay(target - predicted)
    const errorS = (Math.abs(error) * 60) / beat.bpm
    const corrected = predicted + (errorS < SNAP_S ? error * SOFT_GAIN : error)
    this.anchor(corrected, beat.receivedAt, beat.bpm, true, counted)
  }

  sample(now: number): BeatSample {
    const position = this.positionAt(now)
    const beats = withinBar(position)
    return {
      beatPhase: beats % 1,
      barPhase: beats / 4,
      beatInBar: Math.floor(beats) + 1,
      bar: this.counted ? Math.floor(position / 4) + 1 : null,
      bpm: this.bpm,
      running: this.running,
    }
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
