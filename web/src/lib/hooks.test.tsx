import { act, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { setViewportWidth } from '@/test/viewport'
import { formatTime } from './format'
import { useIsPhone } from './use-media-query'
import { useNow } from './use-now'

function Layout() {
  return <p>{useIsPhone() ? 'phone' : 'desktop'}</p>
}

function Clock() {
  return <p>{formatTime(useNow())}</p>
}

describe('useIsPhone', () => {
  it('follows the 768 px breakpoint as the viewport changes', () => {
    render(<Layout />)
    expect(screen.getByText('desktop')).toBeInTheDocument()
    act(() => setViewportWidth(767))
    expect(screen.getByText('phone')).toBeInTheDocument()
    act(() => setViewportWidth(768))
    expect(screen.getByText('desktop')).toBeInTheDocument()
  })
})

describe('useNow', () => {
  it('ticks over on the minute', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 8, 23, 19, 14, 30))
    render(<Clock />)
    expect(screen.getByText('19:14')).toBeInTheDocument()
    act(() => vi.advanceTimersByTime(30_000))
    expect(screen.getByText('19:15')).toBeInTheDocument()
    act(() => vi.advanceTimersByTime(60_000))
    expect(screen.getByText('19:16')).toBeInTheDocument()
  })
})
