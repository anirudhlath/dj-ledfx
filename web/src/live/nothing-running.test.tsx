import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { queries, queryClient } from '@/api/queries'
import { LIVE_RENDER } from '@/design/live-numbers'
import { MOTIFS } from '@/looks/looks-render'
import { seedRest } from '@/test/rest'
import { NothingRunning } from './nothing-running'

function renderNothingRunning(variant: 'desktop' | 'phone') {
  const state = seedRest('nothing-running')
  render(
    <QueryClientProvider client={queryClient}>
      <NothingRunning on={9} total={19} variant={variant} />
    </QueryClientProvider>,
  )
  return { state, rows: within(screen.getByRole('list')).getAllByRole('listitem') }
}

describe('NothingRunning (§9.4)', () => {
  // State-Nothing-Running and Phone-State-Nothing-Running draw each recent look's motif in a box with no border.
  it.each([
    ['desktop', ['h-11.5', 'w-18']],
    ['phone', ['h-10.5', 'w-16']],
  ] as const)("draws each recent look's motif, in the %s's box and the render's ground", (variant, size) => {
    const { state, rows } = renderNothingRunning(variant)
    expect(rows).toHaveLength(state.recent.length)
    rows.forEach((row, at) => {
      const recent = state.recent[at]
      const thumb = row.querySelector<HTMLElement>('[data-thumb]')!
      const look = state.looks.find((each) => each.id === recent.lookId)!
      expect(thumb).toHaveAttribute('data-thumb', look.thumbnail)
      expect(thumb).toHaveClass('shrink-0', 'rounded-control', ...size)
      expect(thumb).not.toHaveClass('border')
      expect(thumb).toHaveStyle({ background: LIVE_RENDER.lookThumb.background })
      const svg = thumb.querySelector('svg.tb')!
      expect(svg).toHaveAttribute('data-paused')
      expect(svg.hasAttribute('data-beat')).toBe(MOTIFS[look.thumbnail].beat)
    })
  })

  it('draws the bare scene for a recent look the library no longer has', () => {
    const state = seedRest('nothing-running')
    queryClient.setQueryData(queries.looks().queryKey, state.looks.filter((look) => look.id !== state.recent[0].lookId))
    render(
      <QueryClientProvider client={queryClient}>
        <NothingRunning on={9} total={19} />
      </QueryClientProvider>,
    )
    const thumb = screen.getAllByRole('listitem')[0].querySelector<HTMLElement>('[data-thumb]')!
    expect(thumb.querySelector('svg')).toBeNull()
    expect(thumb).toHaveStyle({ background: LIVE_RENDER.lookThumb.background })
  })
})
