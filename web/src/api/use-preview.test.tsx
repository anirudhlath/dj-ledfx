import { renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { previewSession } from './live'
import { usePreview } from './use-preview'

describe('usePreview', () => {
  it('previews while its component is mounted, and ends the preview after', () => {
    const show = vi.spyOn(previewSession, 'show').mockImplementation(() => {})
    const stop = vi.spyOn(previewSession, 'stop').mockImplementation(() => {})
    const props: { zone: string | null; look: string | null } = { zone: 'living', look: 'embers' }
    const { rerender, unmount } = renderHook(({ zone, look }) => usePreview(zone, look), { initialProps: props })
    expect(show).toHaveBeenLastCalledWith('living', 'embers')
    rerender({ zone: 'living', look: null })
    expect(stop).toHaveBeenCalledTimes(1)
    unmount()
    expect(stop).toHaveBeenCalledTimes(2)
  })
})
