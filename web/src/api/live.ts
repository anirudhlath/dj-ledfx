// The app's one data layer: a frame store, an fx store, a beat clock, and the live client that fills them
// and the live store. main.tsx starts it once; F3's "Try now" and TAP (actions.ts), F4's preview, F10's
// effects in space (wantFx()) and F6/F8's signal subscriptions reach the client through liveClient().
import { BeatClock } from './beat'
import { FrameStore } from './frames'
import { FxStore } from './fx'
import { LiveClient, liveSocketUrl, type OpenSocket } from './live-client'
import { liveStore, resetLiveStore } from './live-store'
import { PreviewSession } from './preview'
import { queryClient, refetchOnNews, resync } from './queries'

export const frames = new FrameStore()
export const beatClock = new BeatClock()
/** "Effects in space" (F10): held with the preview's frames, so the stage shows one look on the composer's zone. */
export const fx = new FxStore({ previewHeld: () => frames.previewHeld })

let client: LiveClient | null = null
let stopRefetching: (() => void) | null = null
/** How many stages want the fx channel now (wantFx()), counted since the last reset. */
let fxWants = 0
let fxGeneration = 0

/** The composer's preview (F4): one at a time, on the stage only. */
export const previewSession = new PreviewSession({ frames, fx, client: () => client })

/**
 * Starts the live client, stopping any this started before: there is one socket at a time. What the
 * socket names and REST doesn't know sends REST back for it (refetchOnNews).
 */
export function startDataLayer(options: { openSocket?: OpenSocket; url?: string } = {}): LiveClient {
  client?.stop()
  // The stopped link's picture is of a moment that's gone, as on a drop: the new one's server sends its own.
  fx.clear()
  stopRefetching?.()
  stopRefetching = refetchOnNews(liveStore, queryClient)
  client = new LiveClient({
    url: options.url ?? liveSocketUrl(),
    store: liveStore,
    frames,
    beatClock,
    fx,
    openSocket: options.openSocket,
    onResync: () => void resync(queryClient),
    // The server forgets a preview with the link, and a deep link can open the composer before the link is up.
    onLive: () => previewSession.resume(),
  })
  client.subscribeFx(fxWants > 0)
  client.start()
  return client
}

/**
 * The stage wants its effects in space (§7.4): the `fx` channel is on while anything wants it, and off once
 * nothing does. Returns what lets go, once; letting go twice does nothing.
 */
export function wantFx(): () => void {
  fxWants += 1
  client?.subscribeFx(true)
  const generation = fxGeneration
  let held = true
  return () => {
    // A want from before a reset was let go by it.
    if (!held || generation !== fxGeneration) return
    held = false
    fxWants -= 1
    if (fxWants === 0) client?.subscribeFx(false)
  }
}

export function liveClient(): LiveClient | null {
  return client
}

/** Back to a page just opened: no client or preview, and the live store, frames, beat clock and REST cache empty. */
export function resetDataLayer(): void {
  client?.stop()
  client = null
  previewSession.reset()
  stopRefetching?.()
  stopRefetching = null
  fxWants = 0
  fxGeneration += 1
  resetLiveStore()
  frames.clear()
  fx.reset()
  beatClock.reset()
  queryClient.clear()
}
