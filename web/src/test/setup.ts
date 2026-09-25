import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach, vi } from 'vitest'
import { installMatchMedia, setViewportWidth } from './viewport'

// A test that runs in Node (`// @vitest-environment node`) has no window to give one to.
if (typeof window !== 'undefined') installMatchMedia()

beforeEach(() => {
  setViewportWidth(1440)
})

afterEach(() => {
  cleanup()
  // A test that fakes the clock gets the real one back, whether or not it remembers to.
  vi.useRealTimers()
})
