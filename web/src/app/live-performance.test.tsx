import { act, screen } from '@testing-library/react'
import { Profiler } from 'react'
import { beforeEach, expect, it, vi } from 'vitest'
import { frames } from '@/api/live'
import { liveStore } from '@/api/live-store'
import { RENDER } from '@/stage/design-numbers'
import { STAGE_LABEL } from '@/stage/stage-pending'
import { renderApp } from '@/test/app'
import { HERO_NOW, startMockDataLayer } from '@/test/live'
import { resizeObserved } from '@/test/resize'
import { seedRest } from '@/test/rest'

// jsdom has no WebGL. The stage's canvas has its own no-commit check (stage-scene.test.tsx); here a
// stand-in takes its place, and the rest of the stage is real.
vi.mock('@/stage/webgl', () => ({ hasWebGL2: () => true }))
vi.mock('@/stage/stage-canvas', () => ({ StageCanvas: () => <div data-testid="stage-canvas" /> }))

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(HERO_NOW)
})

// Done when (spec §13.1 M1): "Stores update from the mock at 60 fps without React re-renders (React
// profiler)", and since F2 with the stage on screen (§7.5: "No React state per frame"). The hero's
// beat is held (?still), so for this second the only news is the frames and the devices' stats. The
// app, whole, must commit nothing for either.
it('fills the stores from the mock at 60 fps, and React commits nothing', async () => {
  seedRest()
  startMockDataLayer({ still: true })
  let commits = 0
  renderApp('/next/live', {
    wrapper: ({ children }) => (
      <Profiler id="app" onRender={() => void (commits += 1)}>
        {children}
      </Profiler>
    ),
  })

  // Connect, subscribe, and let the measured frame rate settle (decision 3). Async, because the
  // in-memory socket delivers in microtasks between the timers. The stage's lazy chunk loads
  // meanwhile; then it gets Main.png's size, and draws.
  await act(() => vi.advanceTimersByTimeAsync(3000))
  await vi.waitFor(() => expect(screen.getByRole('region', { name: STAGE_LABEL })).not.toHaveAttribute('aria-busy'), { timeout: 10_000 })
  act(() => resizeObserved(RENDER.stage.widthPx, RENDER.stage.heightPx))
  expect(screen.getByTestId('stage-canvas')).toBeInTheDocument()
  expect(liveStore.getState().connection).toEqual({ status: 'live', fps: 60 })
  const version = frames.version
  const stats = liveStore.getState().stats
  commits = 0

  await act(() => vi.advanceTimersByTimeAsync(1000))
  // The hero streams to 17 lights: every one of them, about 60 times.
  expect(frames.version - version).toBeGreaterThanOrEqual(59 * 17)
  // The store moved too: the stats arrive once a second.
  expect(liveStore.getState().stats).not.toBe(stats)
  expect(commits).toBe(0)
})
