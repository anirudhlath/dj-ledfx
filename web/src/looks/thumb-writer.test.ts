import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { clientNow, type Beat } from '@/api/beat'
import { beatClock } from '@/api/live'
import { liveStore } from '@/api/live-store'
import { LIVE_SPEC } from '@/design/live-numbers'
import { stubAnimations } from '@/test/animations'
import { seedLive } from '@/test/live'
import { beatMs, registerThumb } from './thumb-writer'

/** The fake timers' animation frame. */
const FRAME_MS = 16

/** A thumb's svg as LookThumb draws it, paused, whose two animations are stubbed: jsdom has none. */
function thumbSvg(beat: boolean): SVGSVGElement {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
  svg.classList.add('tb')
  svg.setAttribute('data-paused', '')
  if (beat) svg.setAttribute('data-beat', '')
  stubAnimations(svg)
  return svg
}
const beatSvg = () => thumbSvg(true)
const ambientSvg = () => thumbSvg(false)

const times = (svg: SVGSVGElement) => svg.getAnimations({ subtree: true }).map((animation) => animation.currentTime as number | null)
const current = (svg: SVGSVGElement) => times(svg)[0] as number

/** A beat message as the live client hands it on: to the store and to the clock. */
function hear(beat: Beat): void {
  liveStore.setState({ beat })
  beatClock.receive(beat, null)
}
const heroBeat = () => liveStore.getState().beat!

/** The clock's place now, in beats from bar 1's downbeat. */
function position(): number {
  const { bar, barPhase } = beatClock.sample(clientNow())
  return ((bar ?? 1) - 1) * 4 + barPhase * 4
}

/** The hero's beat, heard now `beats` from bar 1's downbeat. */
function heardAt(beats: number): void {
  const bar = Math.floor(beats / 4) + 1
  const within = beats - (bar - 1) * 4
  hear({ ...heroBeat(), bar, barPhase: within / 4, beatPhase: within % 1, beatInBar: Math.floor(within) + 1, receivedAt: clientNow() })
}

const registered: (() => void)[] = []
const register = (...args: Parameters<typeof registerThumb>) => {
  const off = registerThumb(...args)
  registered.push(off)
  return off
}

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  // The writer's thumbs are the module's: a test leaves none behind for the next.
  registered.splice(0).forEach((off) => off())
})

describe('the thumb writer (§5.4, F5 decisions 4 to 6)', () => {
  it("seeks a beat thumb to the beat: the hero's, a quarter into beat 2, is 1.25 beats in", () => {
    seedLive('hero')
    const sample = vi.spyOn(beatClock, 'sample')
    const svg = beatSvg()
    register({ svg, beat: true })
    vi.advanceTimersByTime(20)
    // One frame so far, about a frame after the start: τ begins at the place in the bar that frame saw.
    expect(sample).toHaveBeenCalledTimes(1)
    const place = sample.mock.results[0].value.barPhase * 4
    expect(place).toBeGreaterThanOrEqual(1.25)
    expect(place - 1.25).toBeLessThan((20 * heroBeat().bpm) / 60_000)
    for (const animation of svg.getAnimations({ subtree: true })) expect(animation.currentTime).toBeCloseTo(beatMs(place), 6)
    expect(svg).toHaveAttribute('data-paused')
  })

  it("moves a beat thumb at the live tempo: 1000 ms at 60.9 BPM is 500 ms of the render's 121.8", () => {
    seedLive('hero')
    hear({ ...heroBeat(), bpm: LIVE_SPEC.mockBpm / 2, receivedAt: clientNow() })
    const svg = beatSvg()
    register({ svg, beat: true })
    vi.advanceTimersByTime(20)
    const before = svg.getAnimations({ subtree: true })[0].currentTime as number
    vi.advanceTimersByTime(1000)
    expect((svg.getAnimations({ subtree: true })[0].currentTime as number) - before).toBeCloseTo(500, -1)
  })

  // Review Focus 5.
  it('holds a beat thumb while the beat stops or goes stale, and goes on from there', () => {
    seedLive('hero')
    // A tempo that isn't the render's, so the motif's time is the clock's beats converted, not the clock's time.
    const tempo = LIVE_SPEC.mockBpm * 1.25
    hear({ ...heroBeat(), bpm: tempo, receivedAt: clientNow() })
    /** The motif's time over `ms` of the clock running: its beats, at Looks.html's one beat at mockBpm. */
    const moved = (ms: number) => (ms * tempo) / LIVE_SPEC.mockBpm
    const svg = beatSvg()
    register({ svg, beat: true })
    // On a frame from here: each advance below ends on one.
    vi.advanceTimersByTime(2 * FRAME_MS)

    // Stopped: a beat message with playing false.
    hear({ ...heroBeat(), playing: false, receivedAt: clientNow() })
    const stopped = current(svg)
    vi.advanceTimersByTime(63 * FRAME_MS)
    expect(current(svg)).toBe(stopped)
    // It plays again from beat 4, a beat and more from where it stopped: the thumb doesn't jump there.
    hear({ ...heroBeat(), barPhase: 0.75, beatPhase: 0, beatInBar: 4, playing: true, receivedAt: clientNow() })
    vi.advanceTimersByTime(FRAME_MS)
    expect(current(svg)).toBeCloseTo(stopped, 6)
    vi.advanceTimersByTime(63 * FRAME_MS)
    // A beat in the clock is a beat in the motif: it moved as many beats as the clock ran.
    expect(current(svg) - stopped).toBeCloseTo(moved(63 * FRAME_MS), 2)

    // Stale: the live store says so, whatever the clock does.
    liveStore.setState({ beat: { ...heroBeat(), stale: true } })
    const stale = current(svg)
    vi.advanceTimersByTime(63 * FRAME_MS)
    expect(current(svg)).toBe(stale)
    liveStore.setState({ beat: { ...heroBeat(), stale: false } })
    vi.advanceTimersByTime(FRAME_MS)
    expect(current(svg)).toBeCloseTo(stale, 6)
    vi.advanceTimersByTime(63 * FRAME_MS)
    expect(current(svg) - stale).toBeCloseTo(moved(63 * FRAME_MS), 2)
  })

  // Before 0, every keyframe of a motif is in its before phase, and the motif would draw blank.
  it('never seeks a beat thumb below 0 when the clock steps back early in a run, and goes on from 0', () => {
    seedLive('hero')
    // A twentieth of a beat into bar 42, so the run starts just past a downbeat.
    heardAt(41 * 4 + 0.05)
    const svg = beatSvg()
    register({ svg, beat: true })
    vi.advanceTimersByTime(FRAME_MS)
    expect(current(svg)).toBeGreaterThan(0)
    // Half a beat back, into bar 41: τ, under a tenth of a beat, would go below 0.
    heardAt(position() - 0.5)
    vi.advanceTimersByTime(FRAME_MS)
    expect(times(svg)).toEqual([0, 0])
    for (let frame = 0; frame < 25; frame++) {
      vi.advanceTimersByTime(FRAME_MS)
      expect(current(svg)).toBeGreaterThanOrEqual(0)
    }
    // 400 ms at the hero's 121.8 BPM is about 0.8 beats, past the 0.4 τ fell below 0.
    expect(current(svg)).toBeGreaterThan(0)
  })

  it('lets an ambient thumb run while it is registered, and pauses it again when it goes', () => {
    const svg = ambientSvg()
    const off = register({ svg, beat: false })
    expect(svg.hasAttribute('data-paused')).toBe(false)
    off()
    expect(svg.hasAttribute('data-paused')).toBe(true)
    // Its loop is CSS's (decision 5): the writer neither seeks it nor asks for frames for it.
    vi.advanceTimersByTime(100)
    expect(times(svg)).toEqual([null, null])
  })

  it('asks for no frames for ambient thumbs alone', () => {
    const frame = vi.spyOn(window, 'requestAnimationFrame')
    register({ svg: ambientSvg(), beat: false })
    vi.advanceTimersByTime(100)
    expect(frame).not.toHaveBeenCalled()
  })

  it('samples the clock once a frame for every thumb, and stops asking for frames when the last one goes', () => {
    const sample = vi.spyOn(beatClock, 'sample')
    const offs = [beatSvg(), beatSvg(), beatSvg()].map((svg) => register({ svg, beat: true }))
    vi.advanceTimersByTime(17)
    expect(sample).toHaveBeenCalledTimes(1)
    offs.forEach((off) => off())
    const frame = vi.spyOn(window, 'requestAnimationFrame')
    vi.advanceTimersByTime(100)
    expect(frame).not.toHaveBeenCalled()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('keeps every beat thumb on one beat, one that registers later included, while the beat runs or rests', () => {
    seedLive('hero')
    const first = beatSvg()
    register({ svg: first, beat: true })
    vi.advanceTimersByTime(20)
    const later = beatSvg()
    register({ svg: later, beat: true })
    vi.advanceTimersByTime(FRAME_MS)
    expect(current(later)).not.toBeNull()
    expect(times(later)).toEqual(times(first))
    // A thumb that comes while the beat rests still gets the beat where it rests.
    hear({ ...heroBeat(), playing: false, receivedAt: clientNow() })
    vi.advanceTimersByTime(FRAME_MS)
    const resting = beatSvg()
    register({ svg: resting, beat: true })
    vi.advanceTimersByTime(FRAME_MS)
    expect(times(resting)).toEqual(times(first))
  })

  it('leaves a beat thumb where it was when it goes', () => {
    seedLive('hero')
    const svg = beatSvg()
    const off = register({ svg, beat: true })
    vi.advanceTimersByTime(20)
    const left = current(svg)
    off()
    vi.advanceTimersByTime(100)
    expect(current(svg)).toBe(left)
    expect(svg).toHaveAttribute('data-paused')
  })

  it("takes a beat as the render's: one beat at 121.8 BPM", () => {
    expect(beatMs(1)).toBeCloseTo(60_000 / LIVE_SPEC.mockBpm)
    expect(beatMs(0)).toBe(0)
  })
})
