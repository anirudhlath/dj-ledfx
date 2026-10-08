import { QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { queryClient } from '@/api/queries'
import { LIVE_RENDER, LIVE_SPEC } from '@/design/live-numbers'
import { seedRest } from '@/test/rest'
import { LookThumb } from './look-thumb'

describe('LookThumb (§6.4)', () => {
  // F4 ruling 7: the scene with no motif until F5 ports them, keyed by the look's thumbnail.
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
})
