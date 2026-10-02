import { describe, expect, it } from 'vitest'
import type { Vec2 } from '@/api/contract'
import { bounds, centroid, contains, doubleArea, toWorld } from './plan'

const SQUARE: Vec2[] = [
  [0, 0],
  [4, 0],
  [4, 2],
  [0, 2],
]

describe('plan geometry', () => {
  it("maps plan (x, y, z) to three's (x, z, y), as §7.1 says", () => {
    expect(toWorld([1, 2, 3])).toEqual([1, 3, 2])
  })

  it('measures area with its winding, and finds the centre of an L', () => {
    expect(doubleArea(SQUARE)).toBe(16)
    expect(doubleArea([...SQUARE].reverse())).toBe(-16)
    const ell: Vec2[] = [
      [0, 0],
      [2, 0],
      [2, 1],
      [1, 1],
      [1, 2],
      [0, 2],
    ]
    const [x, y] = centroid(ell)
    expect(x).toBeCloseTo(5 / 6)
    expect(y).toBeCloseTo(5 / 6)
  })

  it('falls back to the mean for a polygon with no area', () => {
    expect(
      centroid([
        [0, 0],
        [2, 0],
        [4, 0],
      ]),
    ).toEqual([2, 0])
  })

  it('tells inside from outside', () => {
    expect(contains(SQUARE, [1, 1])).toBe(true)
    expect(contains(SQUARE, [5, 1])).toBe(false)
    expect(contains(SQUARE, [1, -0.1])).toBe(false)
  })

  it('bounds points', () => {
    expect(bounds(SQUARE)).toEqual({ min: [0, 0], max: [4, 2] })
  })
})
