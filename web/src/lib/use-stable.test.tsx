import { renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { sameEntries, useStable } from './use-stable'

describe('useStable', () => {
  it("keeps the last value while the test says it's the same, and takes a different one", () => {
    const sameLength = (a: string[], b: string[]) => a.length === b.length
    const first = ['a']
    const { result, rerender } = renderHook(({ value }) => useStable(value, sameLength), { initialProps: { value: first } })
    expect(result.current).toBe(first)
    rerender({ value: ['b'] })
    expect(result.current).toBe(first)
    const longer = ['a', 'b']
    rerender({ value: longer })
    expect(result.current).toBe(longer)
    rerender({ value: ['c', 'd'] })
    expect(result.current).toBe(longer)
  })

  it('compares maps key by key', () => {
    expect(sameEntries(new Map([['a', 1]]), new Map([['a', 1]]))).toBe(true)
    expect(sameEntries(new Map([['a', 1]]), new Map([['a', 2]]))).toBe(false)
    expect(sameEntries(new Map([['a', 1]]), new Map([['b', 1]]))).toBe(false)
    expect(sameEntries(new Map([['a', 1]]), new Map([['a', 1], ['b', 2]]))).toBe(false)
  })
})
