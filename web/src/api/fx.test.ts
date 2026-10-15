import { describe, expect, it, vi } from 'vitest'
import { FxStore } from './fx'
import type { FxPlane, FxRing, ZoneFx } from './ws-messages'

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

  // FxWriter tells a zone that changed by its object (final review 2): a picture that sends a zone as it was keeps the stored one.
  it('keeps the stored zone for one sent again unchanged, and takes a changed one', () => {
    const fx = new FxStore()
    const ring = (): FxRing => ({ center: [1, 2, 0], radius: 1, width: 0.2, rgb: [1, 0, 0], form: 'circle' })
    const plane = (): FxPlane => ({ point: [1, 2, 3], normal: [0, 0, 1], width: 0.1, rgb: [0, 1, 0] })
    const office = (): ZoneFx => ({ zoneId: 'office', stream: 'live', rings: [ring()], planes: [plane()] })
    fx.apply({ channel: 'fx', zones: [zone('living'), office(), zone('living', 'preview')] })
    const [living, offices, preview] = [fx.get('living'), fx.get('office'), fx.get('living', 'preview')]
    fx.apply({ channel: 'fx', zones: [zone('living'), office(), zone('living', 'preview')] })
    expect([fx.get('living'), fx.get('office'), fx.get('living', 'preview')]).toEqual([living, offices, preview])
    expect(fx.get('living')).toBe(living)
    expect(fx.get('office')).toBe(offices)
    expect(fx.get('living', 'preview')).toBe(preview)
    const changes: ZoneFx[] = [
      zone('office', 'live', 0.3),
      { ...office(), rings: [{ ...ring(), radius: 2 }] },
      { ...office(), rings: [{ ...ring(), form: 'sphere' }] },
      { ...office(), rings: [] },
      { ...office(), planes: [{ ...plane(), ray: [1, 0, 0] }] },
      { ...office(), planes: [{ ...plane(), rgb: [0, 1, 0.5] }] },
      { zoneId: 'office', stream: 'live', rings: office().rings },
    ]
    for (const changed of changes) {
      fx.apply({ channel: 'fx', zones: [office()] })
      const before = fx.get('office')
      fx.apply({ channel: 'fx', zones: [changed] })
      expect(fx.get('office')).not.toBe(before)
      expect(fx.get('office')).toBe(changed)
    }
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
