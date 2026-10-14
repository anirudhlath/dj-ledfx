// The composer's preview as React sees it: usePreview() asks for one while its component is mounted,
// and usePreviewState() reads it (the stage draws the chosen zone from the preview stream).
import { useEffect, useSyncExternalStore } from 'react'
import type { Id } from './contract'
import { previewSession } from './live'
import type { PreviewState } from './preview'

/** The preview's state, which every component reading it shares. */
export function usePreviewState(): PreviewState {
  return useSyncExternalStore(previewSession.subscribe, previewSession.snapshot)
}

/**
 * Previews `lookId` on `zoneId` while both are given, and nothing otherwise; the preview ends when the
 * component unmounts (Cancel, Close, Start, or leaving the page).
 */
export function usePreview(zoneId: Id | null, lookId: Id | null): PreviewState {
  useEffect(() => {
    if (zoneId === null || lookId === null) previewSession.stop()
    else previewSession.show(zoneId, lookId)
  }, [zoneId, lookId])
  useEffect(() => () => previewSession.stop(), [])
  return usePreviewState()
}
