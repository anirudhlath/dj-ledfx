// §7.3: "Clip each pool to its own room's floor (stencil or a room-id mask texture) so light doesn't
// bleed through walls." The mask: a grid over the plan, each cell holding the 1-based index of the
// room whose polygon holds its centre (0 for none). The pool shader reads it under each fragment and
// draws only where the cell's room is the pool's own.
import type { Room, Vec2 } from '@/api/contract'
import { bounds, contains } from './plan'

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

/** Rasterises the rooms; rooms[i] is written as i + 1. */
export function roomMask(rooms: readonly Pick<Room, 'polygon'>[], cellM = MASK_CELL_M): RoomMask {
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
