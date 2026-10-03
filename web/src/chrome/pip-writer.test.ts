import { describe, expect, it, vi } from 'vitest'
import { LIVE_RENDER } from '@/design/live-numbers'
import { seedLive } from '@/test/live'
import { pipLevel, registerPips, type PipRow } from './pip-writer'

/** A pip row as the tempo module draws one: four pips in a named row, and its "bar N". */
function pipRow(still = false): PipRow & { barElement: HTMLElement } {
  const label = document.createElement('span')
  const pips = [0, 1, 2, 3].map(() => label.appendChild(document.createElement('span')))
  const barElement = document.createElement('span')
  return { label, pips, bar: () => barElement, still, barElement }
}

const levels = (row: PipRow) => row.pips.map((pip) => pip.style.getPropertyValue('--pip'))

describe('the pip writer', () => {
  it("follows the render's curve: up, held, and down by the end of its beat", () => {
    const { riseBeats, holdBeats, endBeats } = LIVE_RENDER.pip
    expect(pipLevel(0)).toBe(0)
    expect(pipLevel(riseBeats)).toBe(1)
    expect(pipLevel(holdBeats)).toBe(1)
    expect(pipLevel((holdBeats + endBeats) / 2)).toBeCloseTo(0.5, 2)
    expect(pipLevel(endBeats)).toBe(0)
    expect(pipLevel(endBeats + 1)).toBe(0)
  })

  it('lights the pip of the beat, names the beat and the bar, and moves with the clock', () => {
    vi.useFakeTimers()
    seedLive() // the hero: bar 42, a quarter into beat 2, at 121.8 BPM
    const row = pipRow()
    const stop = registerPips(row)
    expect(row.label.getAttribute('aria-label')).toBe('Beat 2 of 4')
    expect(row.barElement.textContent).toBe('bar 42')
    expect(levels(row)).toEqual(['0', String(pipLevel(0.25)), '0', '0'])
    vi.advanceTimersByTime(500) // a beat, and a bit
    expect(row.label.getAttribute('aria-label')).toBe('Beat 3 of 4')
    expect(levels(row)[1]).toBe('0')
    expect(Number(levels(row)[2])).toBeGreaterThan(0)
    stop()
    expect(vi.getTimerCount()).toBe(0)
  })

  // F3 decision 4: §5.4 "prefers-reduced-motion stops beat pulses". The name and the bar still follow the beat.
  it('keeps every pip at rest in a still row, and still names the beat', () => {
    vi.useFakeTimers()
    seedLive()
    const row = pipRow(true)
    const stop = registerPips(row)
    vi.advanceTimersByTime(500)
    expect(levels(row)).toEqual(['0', '0', '0', '0'])
    expect(row.label.getAttribute('aria-label')).toBe('Beat 3 of 4')
    stop()
  })
})
