import { describe, expect, it } from 'vitest'
import { parseMessage } from './ws-messages'

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
  ])('returns null for %s', (_, text) => {
    expect(parseMessage(text)).toBeNull()
  })

  it('passes a channel it does not know, for the caller to ignore', () => {
    expect(parseMessage('{"channel":"later","x":1}')).toEqual({ channel: 'later', x: 1 })
  })
})
