import { act } from '@testing-library/react'
import { Profiler } from 'react'
import { beforeEach, expect, it, vi } from 'vitest'
import { frames } from '@/api/live'
import { liveStore } from '@/api/live-store'
import { renderApp } from '@/test/app'
import { HERO_NOW, startMockDataLayer } from '@/test/live'

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(HERO_NOW)
})

// Done when (spec §13.1 M1): "Stores update from the mock at 60 fps without React re-renders (React
// profiler)". The hero's beat is held (?still), so for this second the only news is the frames and
// the devices' stats. The app, whole, must commit nothing for either.
it('fills the stores from the mock at 60 fps, and React commits nothing', async () => {
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
  // in-memory socket delivers in microtasks between the timers.
  await act(() => vi.advanceTimersByTimeAsync(3000))
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
