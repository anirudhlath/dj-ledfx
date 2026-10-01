// §7.3: "Clip each pool to its own room's floor (stencil or a room-id mask texture) so light doesn't
// bleed through walls." The mask: a grid over the plan, each cell holding the 1-based index of the
// room whose polygon holds its centre (0 for none). The pool shader reads it under each fragment and
// draws only where the cell's room is the pool's own.
import type { Room, Vec2 } from '@/api/contract'
import { bounds, crossings } from './plan'

/** The mask's cell, in metres: finer than any wall is thick. */
export const MASK_CELL_M = 0.05

export interface RoomMask {
  /** Row by row from the plan's north (y = origin[1]); one byte per cell. */
  data: Uint8Array
  width: number
  height: number
  /** The plan point at the grid's north-west corner. */
  origin: Vec2
  cellM: number
}

/**
 * Rasterises the rooms; rooms[i] is written as i + 1, and a cell two rooms hold keeps the first's. A
 * scanline fill: along each row of cell centres, a room holds the centres from its 1st edge crossing
 * up to its 2nd, from its 3rd up to its 4th, and so on — the cells contains() would say it holds.
 */
export function roomMask(rooms: readonly Pick<Room, 'polygon'>[]): RoomMask {
  const cellM = MASK_CELL_M
  const points = rooms.flatMap((room) => room.polygon)
  if (points.length === 0) return { data: new Uint8Array(1), width: 1, height: 1, origin: [0, 0], cellM }
  const { min, max } = bounds(points)
  const width = Math.max(1, Math.ceil((max[0] - min[0]) / cellM))
  const height = Math.max(1, Math.ceil((max[1] - min[1]) / cellM))
  const data = new Uint8Array(width * height)
  const centreX = (col: number) => min[0] + (col + 0.5) * cellM
  /** The first column whose centre is at or east of x: an estimate, then settled on the centres themselves. */
  const firstFrom = (x: number) => {
    let col = Math.min(width, Math.max(0, Math.ceil((x - min[0]) / cellM - 0.5)))
    while (col > 0 && centreX(col - 1) >= x) col--
    while (col < width && centreX(col) < x) col++
    return col
  }
  rooms.forEach((room, index) => {
    for (let row = 0; row < height; row++) {
      const xs = crossings(room.polygon, min[1] + (row + 0.5) * cellM).sort((a, b) => a - b)
      for (let k = 0; k + 1 < xs.length; k += 2) {
        for (let cell = row * width + firstFrom(xs[k]), end = row * width + firstFrom(xs[k + 1]); cell < end; cell++) {
          if (data[cell] === 0) data[cell] = index + 1
        }
      }
    }
  })
  return { data, width, height, origin: min, cellM }
}
