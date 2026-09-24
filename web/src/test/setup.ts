import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach, vi } from 'vitest'
import { installMatchMedia, setViewportWidth } from './viewport'

installMatchMedia()

beforeEach(() => {
  setViewportWidth(1440)
})

afterEach(() => {
  cleanup()
  // A test that fakes the clock gets the real one back, whether or not it remembers to.
  vi.useRealTimers()
})
