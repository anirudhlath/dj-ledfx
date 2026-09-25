// The app's one data layer: a frame store, a beat clock, and the live client that fills them and
// the live store. main.tsx starts it once; F3's "Try now" and F6/F8's signal subscriptions reach the
// client through liveClient().
import { BeatClock } from './beat'
import { FrameStore } from './frames'
import { LiveClient, liveSocketUrl, type OpenSocket } from './live-client'
import { liveStore, resetLiveStore } from './live-store'
import { queryClient, refetchOnNews, resync } from './queries'

export const frames = new FrameStore()
export const beatClock = new BeatClock()

let client: LiveClient | null = null
let stopRefetching: (() => void) | null = null

/**
 * Starts the live client, stopping any this started before: there is one socket at a time. What the
 * socket names and REST doesn't know sends REST back for it (refetchOnNews).
 */
export function startDataLayer(options: { openSocket?: OpenSocket; url?: string } = {}): LiveClient {
  client?.stop()
  stopRefetching?.()
  stopRefetching = refetchOnNews(liveStore, queryClient)
  client = new LiveClient({
    url: options.url ?? liveSocketUrl(),
    store: liveStore,
    frames,
    beatClock,
    openSocket: options.openSocket,
    onResync: () => void resync(queryClient),
  })
  client.start()
  return client
}

export function liveClient(): LiveClient | null {
  return client
}

/** Back to a page just opened: no client, and the live store, frames, beat clock and REST cache empty. */
export function resetDataLayer(): void {
  client?.stop()
  client = null
  stopRefetching?.()
  stopRefetching = null
  resetLiveStore()
  frames.clear()
  beatClock.reset()
  queryClient.clear()
}
