import { describe, expect, it } from 'vitest'
import { buildScenario } from '@/api/mocks/scenarios'
import { HERO_NOW } from '@/test/live'
import { attentionActions, attentionLook } from './attention'

const problems = buildScenario('problems', HERO_NOW)
const item = (id: string) => problems.attention.find((candidate) => candidate.id === id)!

describe('an attention item', () => {
  // F3 decision 32: State-Problems' icons, in signal for a look in trouble or an input that's down,
  // quiet for a quiet input or a light that rejoins by itself.
  it('takes its icon and tone from its kind, and an input its own icon', () => {
    expect(attentionLook(item('zone-crashed:kitchen'))).toEqual({ icon: 'alert', tone: 'signal' })
    expect(attentionLook(item('zone-slow:living'))).toEqual({ icon: 'clock', tone: 'signal' })
    expect(attentionLook(item('input-disconnected:home-assistant'))).toEqual({ icon: 'ha', tone: 'signal' })
    expect(attentionLook(item('input-stale:music'))).toEqual({ icon: 'music', tone: 'quiet' })
    expect(attentionLook(item('light-offline:rope'))).toEqual({ icon: 'devices', tone: 'quiet' })
    const dropping = { ...item('light-offline:rope'), kind: 'frames-dropping' as const }
    expect(attentionLook(dropping)).toEqual({ icon: 'devices', tone: 'signal' })
    const deck = { ...item('input-stale:music'), subject: { type: 'input' as const, id: 'somewhere-new' } }
    expect(attentionLook(deck).icon).toBe('inputs')
  })

  // F3 decisions 14 and 15.
  it("offers the server's actions in its order, each as F3 can do it", () => {
    const running = problems.running
    expect(attentionActions(item('zone-crashed:kitchen'), running)).toEqual([
      { kind: 'restart', label: 'Restart', zoneId: 'kitchen', lookName: 'Lava' },
      { kind: 'link', label: 'Details', to: '/looks/lava' },
    ])
    expect(attentionActions(item('zone-slow:living'), running)).toEqual([{ kind: 'link', label: 'Details', to: '/looks/embers' }])
    // No engine serves a retry yet: it draws nothing, and the item's other action stays.
    expect(attentionActions(item('input-disconnected:home-assistant'), running)).toEqual([
      { kind: 'link', label: 'Open Inputs', to: '/inputs' },
    ])
    expect(attentionActions(item('light-offline:rope'), running)).toEqual([{ kind: 'link', label: 'Details', to: '/devices/rope' }])
    const open = { ...item('zone-slow:living'), actions: ['open' as const] }
    expect(attentionActions(open, running)).toEqual([{ kind: 'link', label: 'Open Embers', to: '/looks/embers' }])
    // A zone that has stopped since: nothing to restart or open, and its details are the zone's.
    expect(attentionActions(item('zone-crashed:kitchen'), [])).toEqual([{ kind: 'link', label: 'Details', to: '/live/zones/kitchen' }])
    expect(attentionActions(open, [])).toEqual([])
  })
})
