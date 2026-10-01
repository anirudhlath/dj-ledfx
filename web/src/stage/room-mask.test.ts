import { describe, expect, it } from 'vitest'
import type { Vec2 } from '@/api/contract'
import { homeFixture } from '@/api/mocks/fixtures'
import { roomMask, type RoomMask } from './room-mask'

/** The room index (1-based; 0 for none) the mask holds under a plan point, as the pool shader reads it. */
function maskAt(mask: RoomMask, [x, y]: Vec2): number {
  const col = Math.floor((x - mask.origin[0]) / mask.cellM)
  const row = Math.floor((y - mask.origin[1]) / mask.cellM)
  if (col < 0 || row < 0 || col >= mask.width || row >= mask.height) return 0
  return mask.data[row * mask.width + col]
}

describe("the pools' room mask (§7.3)", () => {
  const mask = roomMask(homeFixture.rooms)

  it("holds each room's index across its floor", () => {
    homeFixture.rooms.forEach((room, index) => expect(maskAt(mask, room.labelAt)).toBe(index + 1))
  })

  it('holds no room outside the floors, or past the grid', () => {
    const [x, y] = homeFixture.outdoor!.courtyard![0]
    expect(maskAt(mask, [x + 0.01, y + 0.5])).toBe(0)
    expect(maskAt(mask, [-50, -50])).toBe(0)
    expect(maskAt(mask, [500, 500])).toBe(0)
  })

  it('stops at the wall between two rooms', () => {
    // The bedroom's second and third points make the wall it shares with its neighbour: a step either
    // side of that wall's midpoint lands in different rooms.
    const bedroom = homeFixture.rooms.findIndex((room) => room.id === 'bedroom') + 1
    const [a, b] = [homeFixture.rooms[bedroom - 1].polygon[1], homeFixture.rooms[bedroom - 1].polygon[2]]
    const middle = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2] as const
    expect(maskAt(mask, [middle[0] - 0.2, middle[1]])).toBe(bedroom)
    expect(maskAt(mask, [middle[0] + 0.2, middle[1]])).not.toBe(bedroom)
  })

  it('makes a one-cell mask for a home with no rooms', () => {
    expect(roomMask([])).toMatchObject({ width: 1, height: 1 })
  })
})
