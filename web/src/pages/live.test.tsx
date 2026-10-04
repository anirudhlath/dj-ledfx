import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { STAGE_LABEL } from '@/stage/stage-pending'
import { renderApp } from '@/test/app'
import { seedLive } from '@/test/live'
import { seedRest } from '@/test/rest'
import { setViewportWidth } from '@/test/viewport'

// The stage's code never arrives, so Live shows only the stage's place.
vi.mock('@/stage/stage', () => new Promise(() => {}))

// E7: the stage's REST reads would otherwise start only once its lazy chunk has loaded and committed.
it("asks for the home, the lights, the zones and the looks while the stage's code is still loading", async () => {
  const fetch = vi.fn<(input: RequestInfo | URL) => Promise<Response>>(() => new Promise(() => {}))
  vi.stubGlobal('fetch', fetch)
  renderApp('/next/live')
  expect(screen.getByRole('region', { name: STAGE_LABEL })).toHaveAttribute('aria-busy', 'true')
  await vi.waitFor(() =>
    expect(fetch.mock.calls.map(([input]) => String(input))).toEqual(
      expect.arrayContaining([
        expect.stringMatching(/\/api\/home$/),
        expect.stringMatching(/\/api\/lights$/),
        expect.stringMatching(/\/api\/zones$/),
        expect.stringMatching(/\/api\/looks$/),
      ]),
    ),
  )
})

// F3 decision 23: the stage stays where it is, and the panel outlines the zone the path names.
it('draws the Running panel beside the stage, outlining the zone /live/zones/:zoneId names', () => {
  seedRest('hero')
  seedLive('hero')
  renderApp('/next/live/zones/living')
  const panel = screen.getByRole('complementary', { name: 'Running' })
  expect(within(panel).getByRole('article', { name: 'Living room — Fireflies' })).toHaveClass('outline-2')
  expect(within(panel).getByRole('article', { name: 'Office desk — Twin comets' })).not.toHaveClass('outline-2')
  expect(screen.getByRole('region', { name: STAGE_LABEL })).toBeInTheDocument()
  expect(document.title).toBe('Live · dj-ledfx')
})

// F3 decision 22: §4.4's "collapsible right panel (overlays the stage)".
it('between 768 and 1199 px, lays the panel over the stage, and hides it and brings it back', async () => {
  setViewportWidth(1000)
  seedRest('hero')
  seedLive('hero')
  const router = renderApp('/next/live')
  await userEvent.click(screen.getByRole('button', { name: 'Hide Running' }))
  expect(screen.queryByRole('complementary', { name: 'Running' })).toBeNull()
  const show = screen.getByRole('button', { name: 'Running' })
  expect(show).toHaveFocus()
  await userEvent.click(show)
  expect(screen.getByRole('complementary', { name: 'Running' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Hide Running' })).toHaveFocus()
  // A zone named while the panel is hidden brings it back (decision 23).
  await userEvent.click(screen.getByRole('button', { name: 'Hide Running' }))
  await act(() => router.navigate('/live/zones/office'))
  expect(screen.getByRole('article', { name: 'Office desk — Twin comets' })).toHaveClass('outline-2')
})
