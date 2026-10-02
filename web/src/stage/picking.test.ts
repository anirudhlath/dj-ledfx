import { describe, expect, it } from 'vitest'
import { homeFixture, lightFixtures } from '@/api/mocks/fixtures'
import { HERO_SINCE } from '@/test/live'
import { heroPose } from '@/test/stage'
import { stageBodies } from './bodies'
import { projectPoint } from './camera'
import { pickLight, pickRoom, screenPoints } from './picking'

const POSE = heroPose()
const LIGHTS = lightFixtures(HERO_SINCE)
const POINTS = screenPoints(POSE, stageBodies(LIGHTS))

describe('what is under the pointer (§8.1)', () => {
  it('finds a light at any of its samples, and none in the empty floor', () => {
    const lamp = LIGHTS.find((light) => light.shape?.kind === 'point')!
    const shape = lamp.shape as { position: [number, number, number] }
    const [x, y] = projectPoint(POSE, shape.position)
    expect(pickLight(POINTS, x + 2, y - 2)).toBe(lamp.id)
    const rope = LIGHTS.find((light) => light.shape?.kind === 'bent-line')!
    const end = POINTS.filter((point) => point.lightId === rope.id).at(-1)!
    expect(pickLight(POINTS, end.at[0], end.at[1])).toBe(rope.id)
    expect(pickLight(POINTS, -100, -100)).toBeNull()
  })

  it('picks the nearer of two lights in reach', () => {
    const points = [
      { lightId: 'a', at: [10, 10] as [number, number], reach: 20 },
      { lightId: 'b', at: [16, 10] as [number, number], reach: 20 },
    ]
    expect(pickLight(points, 14, 10)).toBe('b')
  })

  it('finds the room whose floor is under the pointer', () => {
    for (const room of homeFixture.rooms) {
      const [x, y] = projectPoint(POSE, [room.labelAt[0], room.labelAt[1], 0])
      expect(pickRoom(homeFixture, POSE, x, y)?.id).toBe(room.id)
    }
    expect(pickRoom(homeFixture, POSE, 2, 2)).toBeNull()
  })
})
