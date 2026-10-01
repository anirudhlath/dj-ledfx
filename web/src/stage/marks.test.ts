import { describe, expect, it } from 'vitest'
import type { Light } from '@/api/contract'
import { homeFixture } from '@/api/mocks/fixtures'
import { buildScenario } from '@/api/mocks/scenarios'
import { HERO_NOW } from '@/test/live'
import { lightBodies, stageBodies } from './bodies'
import { FIT_VIEW, fitPose, projectPoint } from './camera'
import { RENDER } from './design-numbers'
import { anchorOf, lightMarks } from './marks'

const POSE = fitPose(homeFixture.outline, { width: RENDER.stage.widthPx, height: RENDER.stage.heightPx }, FIT_VIEW)!
const statesOf = (lights: Light[]) => new Map(lights.map((light) => [light.id, light.status]))

describe('the marks on the stage (§7.3, §9.1)', () => {
  it("drops a line from every raised compact light to the floor, and none from a strip", () => {
    const hero = buildScenario('hero', HERO_NOW)
    const bodies = stageBodies(hero.lights)
    const drops = lightMarks(POSE, bodies, statesOf(hero.lights)).filter((mark) => mark.kind === 'drop')
    const raised = bodies.filter((body) => body.form === 'compact' && body.samples[0][2] > 0)
    expect(drops).toHaveLength(raised.length)
    expect(raised.length).toBeGreaterThan(0)
    const [first] = raised
    expect(drops[0]).toMatchObject({ from: projectPoint(POSE, first.samples[0]), to: projectPoint(POSE, [first.samples[0][0], first.samples[0][1], 0]) })
  })

  it("marks the hero's offline strip along its samples, and its switched-off candle with a ring", () => {
    const hero = buildScenario('hero', HERO_NOW)
    const marks = lightMarks(POSE, stageBodies(hero.lights), statesOf(hero.lights))
    const rope = lightBodies(hero.lights.find((light) => light.id === 'rope')!)[0]
    const candle = lightBodies(hero.lights.find((light) => light.id === 'candle2')!)[0]
    expect(marks).toContainEqual({ kind: 'offline-strip', key: expect.stringMatching(/^rope:/), points: rope.samples.map((s) => projectPoint(POSE, s)) })
    expect(marks).toContainEqual({ kind: 'switched-off', key: expect.stringMatching(/^candle2:/), at: projectPoint(POSE, anchorOf(candle)) })
  })

  it('rings every own effect and marks every streamed copy in the firmware scenario', () => {
    const firmware = buildScenario('firmware', HERO_NOW)
    const marks = lightMarks(POSE, stageBodies(firmware.lights), statesOf(firmware.lights))
    const placed = firmware.lights.filter((light) => light.shape != null)
    const own = placed.filter((light) => light.status === 'own-effect').length
    expect(marks.filter((mark) => mark.kind === 'own-effect')).toHaveLength(own)
    expect(marks.filter((mark) => mark.kind === 'streamed-copy')).toHaveLength(placed.length - own)
    const copy = stageBodies(firmware.lights).find((body) => firmware.lights.find((light) => light.id === body.lightId)?.status === 'streamed-copy')!
    expect(marks).toContainEqual({ kind: 'streamed-copy', key: expect.stringMatching(new RegExp(`^${copy.lightId}:`)), at: projectPoint(POSE, copy.samples.at(-1)!) })
  })
})
