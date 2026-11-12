import { QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { describe, expect, it } from 'vitest'
import type { Look } from '@/api/contract'
import { queries, queryClient } from '@/api/queries'
import { LIVE_RENDER, LIVE_SPEC } from '@/design/live-numbers'
import { seedRest } from '@/test/rest'
import { LookThumb, type ThumbSize } from './look-thumb'
import { MOTIFS } from './looks-render'

const wrap = (ui: ReactElement) => <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
const renderThumb = (lookId: string, size: ThumbSize) => render(wrap(<LookThumb lookId={lookId} size={size} />))
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

  // Review Focus 4.
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
})
