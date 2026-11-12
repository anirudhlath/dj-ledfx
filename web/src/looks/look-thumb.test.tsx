import { QueryClientProvider } from '@tanstack/react-query'
import { act, render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { describe, expect, it, vi } from 'vitest'
import type { Look } from '@/api/contract'
import { beatClock, resetDataLayer } from '@/api/live'
import { queries, queryClient } from '@/api/queries'
import { LIVE_RENDER, LIVE_SPEC } from '@/design/live-numbers'
import { stubAnimations } from '@/test/animations'
import { intersect } from '@/test/intersection'
import { seedLive } from '@/test/live'
import { seedRest } from '@/test/rest'
import { setReducedMotion } from '@/test/viewport'
import { LookThumb, type ThumbSize } from './look-thumb'
import { MOTIFS } from './looks-render'

const wrap = (ui: ReactElement) => <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
const renderThumb = (lookId: string, size: ThumbSize, live?: boolean) => render(wrap(<LookThumb lookId={lookId} size={size} live={live} />))

/** The fake timers' animation frame. */
const FRAME_MS = 16
const markupChildren = (markup: string) =>
  new DOMParser().parseFromString(`<svg xmlns="http://www.w3.org/2000/svg">${markup}</svg>`, 'image/svg+xml').documentElement.childElementCount

describe('LookThumb (§6.4)', () => {
  // F4 ruling 7: the scene, keyed by the look's thumbnail, and F5 draws its motif on it.
  it("draws a look's scene, keyed by its thumbnail, at 16:10 in a tile and at the row's size in a row", () => {
    const { looks } = seedRest('hero')
    const look = looks.find((each) => each.id === 'embers')!
    render(
      <QueryClientProvider client={queryClient}>
        <LookThumb lookId={look.id} size="tile" />
        <LookThumb lookId={look.id} size="row" />
      </QueryClientProvider>,
    )
    const [tile, row] = document.querySelectorAll<HTMLElement>('[data-thumb]')
    expect(tile).toHaveAttribute('data-thumb', look.thumbnail)
    expect(tile).toHaveAttribute('aria-hidden', 'true')
    expect(tile).toHaveStyle({ background: LIVE_RENDER.lookThumb.background })
    expect(tile.style.aspectRatio).toBe(`${LIVE_RENDER.lookThumb.width} / ${LIVE_RENDER.lookThumb.height}`)
    expect(row).toHaveStyle({ width: `${LIVE_SPEC.phoneComposer.thumb.width}px`, height: `${LIVE_SPEC.phoneComposer.thumb.height}px` })
  })

  it("draws each looks.json look's motif, paused, and says nothing to a screen reader", () => {
    for (const look of seedRest('hero').looks) {
      const motif = MOTIFS[look.thumbnail]
      const { container, unmount } = renderThumb(look.id, 'card')
      const svg = container.querySelector('svg.tb')!
      expect(svg).toHaveAttribute('data-paused')
      expect(svg.hasAttribute('data-beat')).toBe(motif.beat)
      expect(svg).toHaveAttribute('viewBox', `0 0 ${LIVE_RENDER.lookThumb.width} ${LIVE_RENDER.lookThumb.height}`)
      expect(svg).toHaveAttribute('preserveAspectRatio', 'xMidYMid slice')
      expect(svg.closest('[aria-hidden="true"]')).not.toBeNull()
      expect(svg.childElementCount).toBe(markupChildren(motif.markup))
      unmount()
    }
  })

  // F5 decision 7: a look with no motif is the bare scene.
  it("draws the bare scene for a look with no motif: a classic, a thumbnail the handoff doesn't have, or none", () => {
    // The schema's thumbnail is required, so a look with none is a server's slip, not a type: cast it once.
    const [first] = seedRest('hero').looks
    for (const thumbnail of ['classic-pulse', 'not-a-motif', null]) {
      queryClient.setQueryData(queries.looks().queryKey, [{ ...first, id: 'x', thumbnail } as unknown as Look])
      const { container, unmount } = renderThumb('x', 'tile')
      expect(container.querySelector('svg.tb')).toBeNull()
      expect(container.querySelector('[data-thumb]')).toHaveStyle({ background: LIVE_RENDER.lookThumb.background })
      unmount()
    }
  })

  it('keeps a look with no thumbnail findable, with data-thumb empty', () => {
    const [first] = seedRest('hero').looks
    queryClient.setQueryData(queries.looks().queryKey, [{ ...first, id: 'x', thumbnail: null } as unknown as Look])
    const { container } = renderThumb('x', 'tile')
    expect(container.querySelector('[data-thumb]')).toHaveAttribute('data-thumb', '')
  })

  it('gives each thumb its own ids, so two of one look share no gradient', () => {
    seedRest('hero')
    const { container } = render(
      wrap(
        <>
          <LookThumb lookId="aurora" size="card" />
          <LookThumb lookId="aurora" size="card" />
        </>,
      ),
    )
    const svgs = [...container.querySelectorAll('svg.tb')]
    expect(svgs).toHaveLength(2)
    const ids = svgs.flatMap((svg) => [...svg.querySelectorAll('[id]')].map((el) => el.id))
    expect(ids.length).toBeGreaterThan(0)
    expect(new Set(ids).size).toBe(ids.length)
    for (const svg of svgs) {
      for (const [, ref] of svg.innerHTML.matchAll(/url\(#([^)]+)\)/g)) expect(svg.querySelector(`[id="${ref}"]`)).not.toBeNull()
    }
  })

  it("draws a card's thumb at Looks.html's proportions, framed as a card", () => {
    seedRest('hero')
    const { container } = renderThumb('aurora', 'card')
    const { width, height } = LIVE_RENDER.lookCard.thumb
    const thumb = container.querySelector<HTMLElement>('[data-thumb]')!
    expect(thumb.style.aspectRatio).toBe(`${width} / ${height}`)
    expect(thumb).toHaveClass('w-full', 'rounded-tile', 'border', 'border-line')
  })

  it('draws the motif under what the thumb carries: a tile’s tag', () => {
    seedRest('hero')
    const { container } = render(
      wrap(
        <LookThumb lookId="aurora" size="tile">
          <b data-testid="tag">Tag</b>
        </LookThumb>,
      ),
    )
    const thumb = container.querySelector('[data-thumb]')!
    expect([...thumb.children].map((child) => child.tagName.toLowerCase())).toEqual(['svg', 'b'])
  })

  describe('motion (§5.4, F5 decisions 4 to 8)', () => {
    it('runs a thumb only while it is on screen', () => {
      seedRest('hero')
      const svg = renderThumb('aurora', 'card').container.querySelector('svg.tb')!
      expect(svg).toHaveAttribute('data-paused')
      act(() => intersect(svg, true))
      expect(svg).not.toHaveAttribute('data-paused')
      act(() => intersect(svg, false))
      expect(svg).toHaveAttribute('data-paused')
    })

    it('seeks a beat thumb on screen to the beat, and leaves it paused for CSS', () => {
      vi.useFakeTimers()
      seedRest('hero')
      seedLive('hero')
      const svg = renderThumb('shockwave', 'card').container.querySelector('svg.tb')!
      const animations = stubAnimations(svg)
      act(() => intersect(svg, true))
      vi.advanceTimersByTime(20)
      expect(svg).toHaveAttribute('data-paused')
      for (const animation of animations) expect(animation.currentTime).toBeGreaterThan(0)
    })

    it('stops when it unmounts', () => {
      seedRest('hero')
      const { container, unmount } = renderThumb('aurora', 'card')
      const svg = container.querySelector('svg.tb')!
      act(() => intersect(svg, true))
      unmount()
      expect(svg).toHaveAttribute('data-paused')
    })

    it('keeps every thumb still under reduced motion, with the beat held (?still), and with live={false}', () => {
      const still = [
        { why: 'reduced motion', set: () => setReducedMotion(true), live: true },
        { why: 'the beat held', set: () => beatClock.hold(), live: true },
        { why: 'live={false}', set: () => {}, live: false },
      ]
      for (const { why, set, live } of still) {
        vi.useFakeTimers()
        seedRest('hero')
        seedLive('hero')
        set()
        // An ambient motif, whose loop would run, and a beat one, which the writer would seek.
        for (const lookId of ['aurora', 'shockwave']) {
          const { container, unmount } = renderThumb(lookId, 'card', live)
          const svg = container.querySelector('svg.tb')!
          const animations = stubAnimations(svg)
          act(() => intersect(svg, true))
          vi.advanceTimersByTime(500)
          expect(svg, `${lookId}, ${why}`).toHaveAttribute('data-paused')
          expect(animations.map((animation) => animation.currentTime), `${lookId}, ${why}`).toEqual([null, null])
          unmount()
        }
        // Each condition alone: the page as a new one finds it, ?still's hold let go.
        setReducedMotion(false)
        resetDataLayer()
      }
    })

    // A thumb given another look of the same kind gets a new svg, which the writer seeks afresh.
    it('seeks the new motif when a mounted beat thumb is given another beat look', () => {
      vi.useFakeTimers()
      seedRest('hero')
      seedLive('hero')
      const { container, rerender } = render(wrap(<LookThumb lookId="shockwave" size="card" />))
      const before = container.querySelector('svg.tb')!
      const old = stubAnimations(before)
      act(() => intersect(before, true))
      vi.advanceTimersByTime(20)
      rerender(wrap(<LookThumb lookId="vortex" size="card" />))
      expect(container.querySelector('[data-thumb]')).toHaveAttribute('data-thumb', 'vortex')
      const after = container.querySelector('svg.tb')!
      const animations = stubAnimations(after)
      act(() => intersect(after, true))
      vi.advanceTimersByTime(FRAME_MS)
      for (const animation of animations) expect(animation.currentTime).toBeGreaterThan(0)
      // The old motif's animations are left where they were.
      const left = old.map((animation) => animation.currentTime)
      vi.advanceTimersByTime(FRAME_MS)
      expect(old.map((animation) => animation.currentTime)).toEqual(left)
    })

    // F5 decision 8, and the controller's ruling: `live` turning false shows the frame ?still shows, a motif that never moved.
    it('draws the frame ?still draws once live turns false on a mounted thumb', () => {
      vi.useFakeTimers()
      seedRest('hero')
      seedLive('hero')
      const thumbs = (live: boolean) =>
        wrap(
          <>
            <LookThumb lookId="aurora" size="card" live={live} />
            <LookThumb lookId="shockwave" size="card" live={live} />
          </>,
        )
      const { container, rerender } = render(thumbs(true))
      const moving = [...container.querySelectorAll('svg.tb')]
      const seeked = moving.map(stubAnimations)
      act(() => moving.forEach((svg) => intersect(svg, true)))
      vi.advanceTimersByTime(20)
      expect(moving[0]).not.toHaveAttribute('data-paused')
      expect(seeked[1][0].currentTime).toBeGreaterThan(0)

      rerender(thumbs(false))
      const resting = [...container.querySelectorAll('svg.tb')]
      // ?still's frame is a thumb drawn and never moved: a new svg, paused, that nothing runs or seeks.
      for (const [index, svg] of resting.entries()) {
        expect(svg).not.toBe(moving[index])
        expect(moving[index].isConnected).toBe(false)
        expect(svg).toHaveAttribute('data-paused')
        const animations = stubAnimations(svg)
        act(() => intersect(svg, true))
        vi.advanceTimersByTime(500)
        expect(svg).toHaveAttribute('data-paused')
        expect(animations.map((animation) => animation.currentTime)).toEqual([null, null])
      }
    })

    // F5 decision 7.
    it('registers nothing for a look with no motif', () => {
      const [first] = seedRest('hero').looks
      queryClient.setQueryData(queries.looks().queryKey, [{ ...first, id: 'x', thumbnail: 'classic-pulse' }])
      const observe = vi.spyOn(window.IntersectionObserver.prototype, 'observe')
      const { container } = renderThumb('x', 'card')
      expect(container.querySelector('svg.tb')).toBeNull()
      expect(observe).not.toHaveBeenCalled()
    })
  })
})
