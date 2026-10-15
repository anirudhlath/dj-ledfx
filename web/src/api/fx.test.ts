import { describe, expect, it, vi } from 'vitest'
import { FxStore } from './fx'
import type { ZoneFx } from './ws-messages'

const zone = (zoneId: string, stream: ZoneFx['stream'] = 'live', size = 0.2): ZoneFx => ({ zoneId, stream, particles: [[1, 2, 1, 1, 1, 1, size]] })

describe('the fx store (§12.4)', () => {
  it('keeps each zone of the latest picture, by stream', () => {
    const fx = new FxStore()
    fx.apply({ channel: 'fx', zones: [zone('living'), zone('office'), zone('living', 'preview')] })
    expect([...fx.live.keys()]).toEqual(['living', 'office'])
    expect(fx.get('living', 'preview')).toEqual(zone('living', 'preview'))
  })

  // "the whole picture: each message replaces the last"; "a message with no zones clears the stage".
  it('replaces the picture with each message, and clears it with an empty one', () => {
    const fx = new FxStore()
    fx.apply({ channel: 'fx', zones: [zone('living'), zone('office', 'preview')] })
    fx.apply({ channel: 'fx', zones: [zone('kitchen')] })
    expect([...fx.live.keys()]).toEqual(['kitchen'])
    expect(fx.preview.size).toBe(0)
    fx.apply({ channel: 'fx', zones: [] })
    expect(fx.empty).toBe(true)
  })

  it('takes the last of a zone sent twice', () => {
    const fx = new FxStore()
    fx.apply({ channel: 'fx', zones: [zone('living', 'live', 0.2), zone('living', 'live', 0.4)] })
    expect(fx.get('living')).toEqual(zone('living', 'live', 0.4))
  })

  // F4's preview session holds the preview's frames while the server may be playing a look chosen over.
  it("holds the preview's picture while its frames are held", () => {
    let held = false
    const fx = new FxStore({ previewHeld: () => held })
    fx.apply({ channel: 'fx', zones: [zone('living', 'preview', 0.2)] })
    held = true
    fx.apply({ channel: 'fx', zones: [zone('office'), zone('living', 'preview', 0.4)] })
    expect(fx.get('living', 'preview')).toEqual(zone('living', 'preview', 0.2))
    expect(fx.get('office')).toEqual(zone('office'))
    held = false
    fx.apply({ channel: 'fx', zones: [zone('living', 'preview', 0.4)] })
    expect(fx.get('living', 'preview')).toEqual(zone('living', 'preview', 0.4))
  })

  it('moves its version with every picture, and wakes whoever waits once', () => {
    const fx = new FxStore()
    const wake = vi.fn()
    fx.onNextChange(wake)
    fx.apply({ channel: 'fx', zones: [] })
    fx.apply({ channel: 'fx', zones: [zone('living')] })
    expect(fx.version).toBe(2)
    expect(wake).toHaveBeenCalledOnce()
    const stop = fx.onNextChange(wake)
    stop()
    fx.clear()
    expect(wake).toHaveBeenCalledOnce()
  })

  it('clears, moving its version only when it held something', () => {
    const fx = new FxStore()
    fx.clear()
    expect(fx.version).toBe(0)
    fx.apply({ channel: 'fx', zones: [zone('living')] })
    fx.clear()
    expect(fx.empty).toBe(true)
    expect(fx.version).toBe(2)
  })
})
