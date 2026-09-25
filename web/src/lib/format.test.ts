import { describe, expect, it } from 'vitest'
import { HERO_NOW } from '@/test/live'
import { formatBpm, formatDayDateTime, formatDayTime, formatTime } from './format'

describe('format', () => {
  const hero = HERO_NOW

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
})
