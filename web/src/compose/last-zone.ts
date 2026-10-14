// §8.2: the composer's zone is "preselected from the room clicked or the last zone used". The last zone
// is a per-viewer convenience in localStorage: a storage that's missing, full or blocked forgets it.
import type { Id } from '@/api/contract'
import { browserStorage } from '@/lib/storage'

const KEY = 'dj-ledfx:compose-zone'

/** The zone a look was last started on from this browser, if it remembers one. */
export function lastZone(storage: Storage | null = browserStorage()): Id | null {
  try {
    return storage?.getItem(KEY) ?? null
  } catch {
    return null
  }
}

/** Remembers the zone a look was started on. */
export function rememberZone(id: Id, storage: Storage | null = browserStorage()): void {
  try {
    storage?.setItem(KEY, id)
  } catch {
    // Full, or blocked: the zone just isn't remembered.
  }
}
