import { screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { STAGE_LABEL } from '@/stage/stage-pending'
import { renderApp } from '@/test/app'

// The stage's code never arrives, so Live shows only the stage's place.
vi.mock('@/stage/stage', () => new Promise(() => {}))

// E7: the stage's REST reads would otherwise start only once its lazy chunk has loaded and committed.
it("asks for the home, the lights and the zones while the stage's code is still loading", async () => {
  const fetch = vi.fn<(input: RequestInfo | URL) => Promise<Response>>(() => new Promise(() => {}))
  vi.stubGlobal('fetch', fetch)
  renderApp('/next/live')
  expect(screen.getByRole('region', { name: STAGE_LABEL })).toHaveAttribute('aria-busy', 'true')
  await vi.waitFor(() =>
    expect(fetch.mock.calls.map(([input]) => String(input))).toEqual(
      expect.arrayContaining([expect.stringMatching(/\/api\/home$/), expect.stringMatching(/\/api\/lights$/), expect.stringMatching(/\/api\/zones$/)]),
    ),
  )
})
