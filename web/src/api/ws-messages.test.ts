import { describe, expect, it } from 'vitest'
import { parseMessage, type FxMessage } from './ws-messages'

/** A well-formed fx message's zone: a particle, a shell, a level ring, a plane and a half plane. */
const ZONE = {
  zoneId: 'living',
  stream: 'live',
  particles: [[1, 2, 1.5, 0.5, 0.4, 0.1, 0.2]],
  rings: [
    { center: [3, 4, 1], radius: 2, width: 0.3, rgb: [1, 0.5, 0], form: 'sphere' },
    { center: [3, 4, 0], radius: 1, width: 0.2, rgb: [0, 0.5, 1], form: 'circle' },
  ],
  planes: [
    { point: [3, 4, 1], normal: [0, 0, 1], width: 0.3, rgb: [1, 1, 1] },
    { point: [3, 4, 1], normal: [1, 0, 0], width: 0.3, rgb: [1, 1, 1], ray: [0, 1, 0] },
  ],
}
const fx = (...zones: unknown[]) => parseMessage(JSON.stringify({ channel: 'fx', zones })) as FxMessage

describe('parseMessage', () => {
  it('reads a channel message', () => {
    expect(parseMessage('{"channel":"transport","state":"simulating"}')).toEqual({ channel: 'transport', state: 'simulating' })
  })

  it.each([
    ['bad JSON', '{"channel":'],
    ['a message with no channel', '{"state":"playing"}'],
    ['a channel that is not a string', '{"channel":7}'],
    ['JSON that is not an object', '[1,2]'],
    ['a running snapshot without its zones', '{"channel":"running","overlays":[]}'],
    ['a lights snapshot whose lights are not a list', '{"channel":"lights","lights":{}}'],
    ['an attention snapshot without its items', '{"channel":"attention"}'],
    ['stats without devices', '{"channel":"stats"}'],
    ['a beat without a bpm', '{"channel":"beat","beat_phase":0.5}'],
    // M10: a snapshot without its payload would store undefined, or preview only as off.
    ['inputs without their inputs', '{"channel":"inputs"}'],
    ['inputs that are a list', '{"channel":"inputs","inputs":[]}'],
    ['signals without their values', '{"channel":"signals"}'],
    ['transport without its state', '{"channel":"transport"}'],
    ["stats whose lights aren't a list", '{"channel":"stats","devices":[],"lights":{}}'],
  ])('returns null for %s', (_, text) => {
    expect(parseMessage(text)).toBeNull()
  })

  it('returns null for fx without its zones', () => {
    expect(parseMessage('{"channel":"fx"}')).toBeNull()
    expect(parseMessage('{"channel":"fx","zones":{}}')).toBeNull()
  })

  // §12.4's fx block (F10 decision 1).
  describe('fx', () => {
    it('reads a well-formed picture as it is', () => {
      expect(fx(ZONE)).toEqual({ channel: 'fx', zones: [ZONE] })
      expect(fx()).toEqual({ channel: 'fx', zones: [] })
    })

    it('drops a zone without its id or its stream, and keeps the others', () => {
      const zones = fx({ ...ZONE, zoneId: 7 }, { ...ZONE, stream: 'later' }, { stream: 'live' }, 'living', { ...ZONE, stream: 'preview' }).zones
      expect(zones).toEqual([{ ...ZONE, stream: 'preview' }])
    })

    it.each([
      ['too short', [1, 2, 3, 1, 1, 1]],
      ['a number missing', [1, 2, null, 1, 1, 1, 0.2]],
      ['text for a number', [1, 2, '3', 1, 1, 1, 0.2]],
      ['no size', [1, 2, 3, 1, 1, 1, 0]],
      ['not a list', { x: 1 }],
    ])('drops a particle that is %s, not the zone', (_, particle) => {
      expect(fx({ ...ZONE, particles: [particle, ...ZONE.particles] }).zones[0].particles).toEqual(ZONE.particles)
    })

    it.each([
      ['a centre that is not three numbers', { center: [3, 4], radius: 2, width: 0.3, rgb: [1, 1, 1], form: 'sphere' }],
      ['a radius below 0', { center: [3, 4, 1], radius: -1, width: 0.3, rgb: [1, 1, 1], form: 'sphere' }],
      ['no width', { center: [3, 4, 1], radius: 2, width: 0, rgb: [1, 1, 1], form: 'sphere' }],
      ['a form it does not know', { center: [3, 4, 1], radius: 2, width: 0.3, rgb: [1, 1, 1], form: 'cube' }],
      ['no colour', { center: [3, 4, 1], radius: 2, width: 0.3, form: 'sphere' }],
    ])('drops a ring with %s', (_, ring) => {
      expect(fx({ ...ZONE, rings: [ring, ...ZONE.rings] }).zones[0].rings).toEqual(ZONE.rings)
    })

    it.each([
      ['no normal', { point: [3, 4, 1], normal: [0, 0, 0], width: 0.3, rgb: [1, 1, 1] }],
      ['a ray of no length', { point: [3, 4, 1], normal: [1, 0, 0], width: 0.3, rgb: [1, 1, 1], ray: [0, 0, 0] }],
      ['a ray that is not three numbers', { point: [3, 4, 1], normal: [1, 0, 0], width: 0.3, rgb: [1, 1, 1], ray: 'north' }],
      ['no width', { point: [3, 4, 1], normal: [0, 0, 1], width: -1, rgb: [1, 1, 1] }],
    ])('drops a plane with %s, rather than draw it whole', (_, plane) => {
      expect(fx({ ...ZONE, planes: [plane, ...ZONE.planes] }).zones[0].planes).toEqual(ZONE.planes)
    })

    it("reads a list that isn't one as none", () => {
      expect(fx({ ...ZONE, particles: 'many', rings: {}, planes: null }).zones[0]).toEqual({ zoneId: 'living', stream: 'live' })
    })

    // §12.4, "Extending it": a later kind is a new optional key, a later field a new optional one on an item.
    it('ignores what it does not know: a key of the message, a kind of the zone, a field of an item', () => {
      const later = {
        ...ZONE,
        shafts: [{ from: [0, 0, 0] }],
        particles: [[...ZONE.particles[0], 0.5]],
        rings: [{ ...ZONE.rings[0], fade: 0.5 }],
      }
      const message = parseMessage(JSON.stringify({ channel: 'fx', zones: [later], at: 12 })) as FxMessage
      expect(message.zones[0]).not.toHaveProperty('shafts')
      expect(message.zones[0].particles).toEqual(later.particles)
      expect(message.zones[0].rings).toEqual(later.rings)
    })
  })

  it('passes a channel it does not know, for the caller to ignore', () => {
    expect(parseMessage('{"channel":"later","x":1}')).toEqual({ channel: 'later', x: 1 })
  })
})
