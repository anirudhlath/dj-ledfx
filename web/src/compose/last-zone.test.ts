import { describe, expect, it } from 'vitest'
import { lastZone, rememberZone } from './last-zone'

describe('the last zone used', () => {
  it('is remembered in this browser', () => {
    rememberZone('kitchen', localStorage)
    expect(lastZone(localStorage)).toBe('kitchen')
    localStorage.clear()
    expect(lastZone(localStorage)).toBeNull()
  })

  it('is quietly forgotten where storage refuses', () => {
    const refusing = {
      getItem: () => {
        throw new Error('blocked')
      },
      setItem: () => {
        throw new Error('full')
      },
    } as unknown as Storage
    expect(() => rememberZone('kitchen', refusing)).not.toThrow()
    expect(lastZone(refusing)).toBeNull()
    expect(lastZone(null)).toBeNull()
  })
})
