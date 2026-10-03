import { describe, expect, it } from 'vitest'
import { HERO_NOW } from '@/test/live'
import {
  formatBpm,
  formatDayDateTime,
  formatDayTime,
  formatDayWord,
  formatDuration,
  formatLatency,
  formatList,
  formatPitch,
  formatSecondsLeft,
  formatSpan,
  formatTime,
  formatTimeWithSeconds,
  formatTrackBpm,
} from './format'

describe('format', () => {
  const hero = HERO_NOW

  it("writes a deck's BPM to two decimals and its pitch with a sign (§10)", () => {
    expect(formatTrackBpm(124)).toBe('124.00')
    expect(formatPitch(1.2)).toBe('+1.2%')
    expect(formatPitch(0)).toBe('+0.0%')
    expect(formatPitch(-0.5)).toBe('-0.5%')
  })

  it('writes the clocks the chrome shows', () => {
    expect(formatDayDateTime(hero)).toBe('Wed 23 Sep · 19:14')
    expect(formatDayTime(hero)).toBe('Wed 19:14')
    expect(formatDayDateTime(new Date(2025, 8, 20, 23, 40))).toBe('Sat 20 Sep · 23:40')
  })

  it('uses a 24 h clock with padded minutes', () => {
    expect(formatTime(new Date(2026, 0, 5, 0, 5))).toBe('00:05')
    expect(formatDayDateTime(new Date(2026, 0, 5, 9, 7))).toBe('Mon 5 Jan · 09:07')
  })

  it('writes BPM with one decimal', () => {
    expect(formatBpm(121.8)).toBe('121.8')
    expect(formatBpm(124)).toBe('124.0')
    expect(formatBpm(125.46)).toBe('125.5')
  })

  it('writes a latency in whole ms, an estimate with a tilde', () => {
    expect(formatLatency(38.4)).toBe('38 ms')
    expect(formatLatency(40, true)).toBe('~40 ms')
  })

  // §10: "Durations: 1 h 10 m, 9 m, 42 s". §14 Unit: "formatters (durations)".
  it('writes durations as §10 does, floored and never negative', () => {
    expect(formatDuration(42_000)).toBe('42 s')
    expect(formatDuration(9 * 60_000 + 59_000)).toBe('9 m')
    expect(formatDuration(70 * 60_000)).toBe('1 h 10 m')
    expect(formatDuration(120 * 60_000)).toBe('2 h')
    // State-Problems: "38 of 60 fps for 2 min".
    expect(formatDuration(2 * 60_000 + 30_000, 'min')).toBe('2 min')
    expect(formatDuration(-5_000)).toBe('0 s')
  })

  it("writes an overlay's time left, never below zero, and a clock with seconds", () => {
    expect(formatSecondsLeft(2_400)).toBe('2.4 s left')
    expect(formatSecondsLeft(-300)).toBe('0.0 s left')
    expect(formatTimeWithSeconds(new Date(2026, 8, 23, 19, 14, 5))).toBe('19:14:05')
  })

  // State-Nothing-Running's Start again lines; F3 decision 35.
  it('says a day as Start again does, and a span across days', () => {
    const now = new Date(2026, 8, 23, 19, 14)
    expect(formatDayWord(new Date(2026, 8, 23, 7, 0), now)).toBe('')
    expect(formatDayWord(new Date(2026, 8, 22, 23, 31), now)).toBe('yesterday')
    expect(formatDayWord(new Date(2026, 8, 18, 12, 0), now)).toBe('Fri')
    expect(formatDayWord(new Date(2026, 8, 16, 12, 0), now)).toBe('16 Sep')
    expect(formatSpan(new Date(2026, 8, 22, 18, 2), new Date(2026, 8, 22, 23, 31), now)).toBe('yesterday 18:02 – 23:31')
    expect(formatSpan(new Date(2026, 8, 22, 23, 31), new Date(2026, 8, 23, 7, 0), now)).toBe('yesterday 23:31 – today 07:00')
    expect(formatSpan(new Date(2026, 8, 23, 18, 2), new Date(2026, 8, 23, 19, 0), now)).toBe('18:02 – 19:00')
  })

  // "Doorbell ripple and Goodnight can't trigger" (§9.3).
  it('lists names with "and" before the last', () => {
    expect(formatList([])).toBe('')
    expect(formatList(['LIFX'])).toBe('LIFX')
    expect(formatList(['LIFX', 'Govee'])).toBe('LIFX and Govee')
    expect(formatList(['OpenRGB', 'LIFX', 'Govee'])).toBe('OpenRGB, LIFX and Govee')
  })
})
