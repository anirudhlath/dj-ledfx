import { act, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { liveClient } from '@/api/live'
import { boot } from './boot'

vi.mock('@/api/mocks/browser', () => ({
  startMocks: vi.fn(async () => {
    throw new DOMException('Failed to register a ServiceWorker: the document is insecure.', 'SecurityError')
  }),
}))

const container = document.createElement('div')
document.body.append(container)

afterEach(() => window.history.replaceState(null, '', '/'))

// M15: the mock build opened over plain http from a phone can't register MSW's worker.
it("says the mocks didn't start, rather than leave the page blank", async () => {
  window.history.replaceState(null, '', '/next/live?scenario=hero')
  const root = await act(() => boot(container))
  expect(screen.getByRole('heading', { level: 1, name: "The mocks didn't start" })).toBeInTheDocument()
  expect(screen.getByRole('main')).toHaveTextContent('the document is insecure')
  expect(screen.getByRole('button', { name: 'Reload' })).toBeInTheDocument()
  expect(liveClient()).toBeNull()
  act(() => root.unmount())
})
