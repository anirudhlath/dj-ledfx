import { describe, expect, it } from 'vitest'
import type { Room, Vec2 } from '@/api/contract'
import { homeFixture } from '@/api/mocks/fixtures'
import { bounds, contains } from './plan'
import { MASK_CELL_M, roomMask, type RoomMask } from './room-mask'

/** The room index (1-based; 0 for none) the mask holds under a plan point, as the pool shader reads it. */
function maskAt(mask: RoomMask, [x, y]: Vec2): number {
  const col = Math.floor((x - mask.origin[0]) / mask.cellM)
  const row = Math.floor((y - mask.origin[1]) / mask.cellM)
  if (col < 0 || row < 0 || col >= mask.width || row >= mask.height) return 0
  return mask.data[row * mask.width + col]
}

/** The mask as first written, each cell's centre tested against each room: what the scanline fill must reproduce. */
function cellByCell(rooms: readonly Pick<Room, 'polygon'>[]): RoomMask {
  const cellM = MASK_CELL_M
  const points = rooms.flatMap((room) => room.polygon)
  if (points.length === 0) return { data: new Uint8Array(1), width: 1, height: 1, origin: [0, 0], cellM }
  const { min, max } = bounds(points)
  const width = Math.max(1, Math.ceil((max[0] - min[0]) / cellM))
  const height = Math.max(1, Math.ceil((max[1] - min[1]) / cellM))
  const data = new Uint8Array(width * height)
  rooms.forEach((room, index) => {
    const box = bounds(room.polygon)
    const [c0, c1] = [Math.floor((box.min[0] - min[0]) / cellM), Math.ceil((box.max[0] - min[0]) / cellM)]
    const [r0, r1] = [Math.floor((box.min[1] - min[1]) / cellM), Math.ceil((box.max[1] - min[1]) / cellM)]
    for (let row = Math.max(0, r0); row < Math.min(height, r1); row++) {
      for (let col = Math.max(0, c0); col < Math.min(width, c1); col++) {
        const centre: Vec2 = [min[0] + (col + 0.5) * cellM, min[1] + (row + 0.5) * cellM]
        if (data[row * width + col] === 0 && contains(room.polygon, centre)) data[row * width + col] = index + 1
      }
    }
  })
  return { data, width, height, origin: min, cellM }
}

/** The mask's shape, and how many of its cells differ from the other's. */
function compared(mask: RoomMask, other: RoomMask) {
  const differing = mask.data.reduce((count, room, cell) => count + (room === other.data[cell] ? 0 : 1), 0)
  return { width: mask.width, height: mask.height, origin: mask.origin, cellM: mask.cellM, differing }
}

// Edges through cell centres and along them, where the floating-point estimate of a crossing's column
// is one off (x = 0.375, 0.675 and 2.825 on a grid from 0.3), a concave room, diagonals, and rooms that
// overlap (the first one listed keeps a cell both hold).
const AWKWARD: Pick<Room, 'polygon'>[] = [
  { polygon: [[0.3, 0.3], [1.3, 0.3], [1.3, 1.3], [0.3, 1.3]] },
  { polygon: [[1.3, 0.3], [2.825, 0.3], [2.825, 0.825], [1.8, 0.825], [1.8, 1.325], [1.3, 1.325]] },
  { polygon: [[0.3, 1.3], [2.325, 1.3125], [0.325, 2.825]] },
  { polygon: [[0.675, 0.8], [1.825, 0.8], [1.825, 1.875], [0.675, 1.875]] },
  { polygon: [[0.375, 2.9], [0.675, 2.9], [0.675, 3.2], [0.375, 3.2]] },
]

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

  it('fills the same cells as testing each cell centre against each room', () => {
    for (const rooms of [homeFixture.rooms, AWKWARD]) {
      const oracle = cellByCell(rooms)
      expect(compared(roomMask(rooms), oracle)).toEqual({ ...compared(oracle, oracle), differing: 0 })
    }
  })

  it('makes a one-cell mask for a home with no rooms', () => {
    expect(roomMask([])).toMatchObject({ width: 1, height: 1 })
  })
})
