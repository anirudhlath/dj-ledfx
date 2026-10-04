import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/api/rest'
import { SEND_EVERY_MS, useThrottledValue, type ThrottleOptions } from './use-throttled-value'

function throttled({ send = vi.fn(async () => {}), ...rest }: Partial<ThrottleOptions> = {}) {
  const options: ThrottleOptions = { server: 0.7, send, onFail: vi.fn(), enabled: true, ...rest }
  const hook = renderHook((props: ThrottleOptions) => useThrottledValue(props), { initialProps: options })
  return { ...hook, options, sent: () => vi.mocked(options.send).mock.calls.map(([value]) => value) }
}

describe('useThrottledValue', () => {
  // F3 decision 9.
  it('sends the first value at once, then at most one each SEND_EVERY_MS, and always the last', async () => {
    vi.useFakeTimers()
    const { result, rerender, options, sent } = throttled()
    act(() => result.current.change(0.6))
    act(() => result.current.change(0.5))
    act(() => result.current.change(0.4))
    expect(sent()).toEqual([0.6])
    expect(result.current.value).toBe(0.4)
    await act(() => vi.advanceTimersByTimeAsync(SEND_EVERY_MS))
    expect(sent()).toEqual([0.6, 0.4])
    // The server's answer comes back; once a window passes with nothing new, the control shows it.
    rerender({ ...options, server: 0.4 })
    await act(() => vi.advanceTimersByTimeAsync(SEND_EVERY_MS))
    expect(sent()).toEqual([0.6, 0.4])
    rerender({ ...options, server: 0.9 })
    expect(result.current.value).toBe(0.9)
  })

  it("drops what's queued, and takes nothing, while it's disabled", async () => {
    vi.useFakeTimers()
    const { result, rerender, options, sent } = throttled()
    act(() => result.current.change(0.6))
    act(() => result.current.change(0.3))
    rerender({ ...options, enabled: false })
    await act(() => vi.advanceTimersByTimeAsync(SEND_EVERY_MS * 3))
    expect(sent()).toEqual([0.6])
    expect(result.current.value).toBe(0.7)
    act(() => result.current.change(0.2))
    expect(sent()).toEqual([0.6])
    rerender({ ...options, enabled: true })
    expect(result.current.value).toBe(0.7)
  })

  it("drops what's queued, shows the server's value, and hands on the failure when a send fails", async () => {
    vi.useFakeTimers()
    const refused = new ApiError(409, 'The zone is busy.', '/api/zones/living/brightness')
    const { result, options, sent } = throttled({ send: vi.fn((value: number) => (value === 0.6 ? Promise.reject(refused) : Promise.resolve())) })
    act(() => result.current.change(0.6))
    act(() => result.current.change(0.5))
    await act(() => vi.advanceTimersByTimeAsync(SEND_EVERY_MS * 2))
    expect(sent()).toEqual([0.6])
    expect(options.onFail).toHaveBeenCalledWith(refused)
    expect(result.current.value).toBe(0.7)
  })
})
