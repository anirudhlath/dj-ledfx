import { act, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Light, LightStatus } from '@/api/contract'
import { lightFixtures } from '@/api/mocks/fixtures'
import { LIVE_RENDER, LIVE_SPEC } from '@/design/live-numbers'
import { swatchFill, swatchGlow } from '@/lib/light-colour'
import { lightState } from '@/stage/show'
import { HERO_SINCE, pushFrame } from '@/test/live'
import { setReducedMotion } from '@/test/viewport'
import { LightSwatch } from './light-swatch'

const light = (id: string): Light => lightFixtures(HERO_SINCE).find((each) => each.id === id)!
const swatchOf = (id: string, status: LightStatus, power = true) => {
  const target = light(id)
  return <LightSwatch light={target} state={lightState({ ...target, status, power }, undefined)} />
}
const { swatch } = LIVE_SPEC

describe('LightSwatch', () => {
  // §14 Components: "LightSwatch states". §6.6: "Always carries an accessible name".
  it('names each state and draws it as §6.6 says', () => {
    render(
      <>
        {swatchOf('bedl', 'streaming')}
        {swatchOf('candle1', 'own-effect')}
        {swatchOf('kcorner', 'streamed-copy')}
        {swatchOf('rope', 'offline', false)}
        {swatchOf('candle2', 'switched-off', false)}
      </>,
    )
    expect(screen.getByRole('img', { name: light('bedl').name }).style.width).toBe(`${swatch.px}px`)
    const own = screen.getByRole('img', { name: `${light('candle1').name}, running its own effect` })
    expect(own).toHaveStyle({ outlineStyle: 'dotted', outlineColor: 'var(--color-text-2)', outlineOffset: `${swatch.ownEffectOffsetPx}px` })
    const copy = screen.getByRole('img', { name: `${light('kcorner').name}, a streamed copy` })
    expect(copy).toHaveStyle({ outlineStyle: 'dashed', outlineColor: 'var(--color-text-3)', outlineOffset: `${swatch.streamedOffsetPx}px` })
    // Hollow states are circles whatever the light is, and nothing paints them. jsdom computes no border
    // shorthand, so their borders are read from the inline style.
    const offline = screen.getByRole('img', { name: `${light('rope').name}, offline` })
    expect(offline.style).toMatchObject({ borderStyle: 'dashed', borderColor: 'var(--color-signal)', width: `${swatch.px}px` })
    expect(offline.style.background).toBe('')
    const off = screen.getByRole('img', { name: 'Candle 2, switched off elsewhere' })
    expect(off.style).toMatchObject({ borderStyle: 'solid', borderColor: 'var(--color-text-3)' })
    expect(off.children).toHaveLength(1)
  })

  it("follows its light's frames without React, and under reduced motion repaints at most once per LIVE_SPEC.reducedMotionMs", () => {
    vi.useFakeTimers()
    render(swatchOf('bedl', 'streaming'))
    const bed = screen.getByRole('img', { name: light('bedl').name })
    pushFrame('bedl', 1, [255, 120, 0])
    act(() => vi.advanceTimersToNextFrame())
    expect(bed).toHaveStyle({ background: swatchFill([255, 120, 0]), boxShadow: swatchGlow([255, 120, 0], swatch.glowPx) })

    act(() => setReducedMotion(true))
    pushFrame('bedl', 2, [0, 0, 255])
    act(() => vi.advanceTimersToNextFrame())
    expect(bed).toHaveStyle({ background: swatchFill([255, 120, 0]) })
    act(() => vi.advanceTimersByTime(LIVE_SPEC.reducedMotionMs))
    expect(bed).toHaveStyle({ background: swatchFill([0, 0, 255]) })
  })

  it('draws a multizone or matrix light as a pill, its LEDs left to right, and a light at rest in its own colour', () => {
    vi.useFakeTimers()
    const rope = light('rope')
    render(
      <>
        {swatchOf('rope', 'streaming')}
        <LightSwatch light={light('kfloor')} state={lightState({ ...light('kfloor'), status: 'idle', power: true, colour: '#ffba5e' }, undefined)} size="phone" />
      </>,
    )
    const pill = screen.getByRole('img', { name: rope.name })
    expect(pill.style.width).toBe(`${Math.floor(swatch.px * swatch.pillRatio)}px`)
    expect(pill.style.height).toBe(`${swatch.px}px`)
    pushFrame('rope', 1, Array.from({ length: rope.leds * 3 }, (_, i) => (i % 3 === 0 ? 255 : 0)))
    act(() => vi.advanceTimersToNextFrame())
    expect(pill.style.background).toMatch(/^linear-gradient\(90deg, /)
    const lamp = screen.getByRole('img', { name: light('kfloor').name })
    expect(lamp).toHaveStyle({ width: `${swatch.phonePx}px`, background: swatchFill([0xff, 0xba, 0x5e]) })
  })

  // F3 decision 34: §6.3 gives a ZoneRow's "small swatches" no size; they take State-Problems' (LIVE_RENDER).
  it("draws a ZoneRow's swatch at the size State-Problems draws it", () => {
    render(<LightSwatch light={light('bedl')} state={lightState({ ...light('bedl'), status: 'streaming', power: true }, undefined)} size="row" />)
    expect(screen.getByRole('img', { name: light('bedl').name }).style.width).toBe(`${LIVE_RENDER.rowSwatchPx}px`)
  })

  // F3 decision 24: Phone-Zone's "glowing" and "waiting", written with the colour.
  it('writes "glowing" or "waiting" where it is asked to, as its light lights and darkens', () => {
    vi.useFakeTimers()
    const words = document.createElement('span')
    const target = light('bedl')
    render(<LightSwatch light={target} state={lightState({ ...target, status: 'streaming', power: true }, undefined)} words={words} />)
    expect(words).toHaveTextContent('waiting')
    pushFrame('bedl', 1, [255, 120, 0])
    act(() => vi.advanceTimersToNextFrame())
    expect(words).toHaveTextContent('glowing')
    pushFrame('bedl', 2, [0, 0, 0])
    act(() => vi.advanceTimersToNextFrame())
    expect(words).toHaveTextContent('waiting')
  })
})
