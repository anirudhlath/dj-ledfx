// The composer's preview (spec §8.2, §12.3): the look on the stage only, while the lights stay as they
// are. The server holds one preview at a time and a new one replaces it, so the session asks for one
// at a time: a choice made while a request is on its way is asked for when that one is answered, and
// the server's last preview is always the last one chosen. The preview stream is watched while one is
// open (engine M2 ends a preview nobody watches, its Spec Ruling 9), and asked for again when the link
// comes back. Components read it through usePreview() (use-preview.ts).
import type { Id, PreviewLight } from './contract'
import type { FrameStore } from './frames'
import type { LiveClient } from './live-client'
import { api } from './rest'

export type PreviewStatus = 'idle' | 'starting' | 'on' | 'failed'

export interface PreviewState {
  readonly status: PreviewStatus
  /** The zone and the look chosen: null while idle. */
  readonly zoneId: Id | null
  readonly lookId: Id | null
  /** What each of the zone's lights would do if the look started (F4 ruling 1): the server's answer, while on. */
  readonly lights: readonly PreviewLight[] | null
  /** Why the server refused it, while failed. */
  readonly error: unknown
  /**
   * The zone whose lights the stage draws from the preview stream: its preview is on, or the next look
   * on it is on its way (the last one's frames flow until the server replaces it). Null otherwise.
   */
  readonly showing: Id | null
}

export const PREVIEW_IDLE: PreviewState = { status: 'idle', zoneId: null, lookId: null, lights: null, error: null, showing: null }

interface Choice {
  zoneId: Id
  lookId: Id
}

const same = (a: Choice | null, b: Choice | null) => a !== null && b !== null && a.zoneId === b.zoneId && a.lookId === b.lookId

export class PreviewSession {
  private state: PreviewState = PREVIEW_IDLE
  private readonly listeners = new Set<() => void>()
  private readonly frames: FrameStore
  private readonly client: () => LiveClient | null
  /** What the composer wants previewed now; null for nothing. */
  private wanted: Choice | null = null
  /** The last choice sent, answered or on its way; null after a stop. */
  private asked: Choice | null = null
  private asking = false
  /** The preview the server holds for this page. */
  private previewId: Id | null = null
  private watching = false
  /** Moves on at reset(): an answer to a request from before it is dropped. */
  private generation = 0

  constructor(options: { frames: FrameStore; client: () => LiveClient | null }) {
    this.frames = options.frames
    this.client = options.client
  }

  /** For useSyncExternalStore. */
  readonly subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener)
    return () => void this.listeners.delete(listener)
  }

  readonly snapshot = (): PreviewState => this.state

  /** Previews `lookId` on `zoneId`, replacing whatever this session previewed before. */
  show(zoneId: Id, lookId: Id): void {
    const choice = { zoneId, lookId }
    if (same(this.wanted, choice)) return
    this.wanted = choice
    if (this.state.showing !== null && this.state.showing !== zoneId) this.frames.clearPreview()
    this.watch(true)
    this.set({ ...PREVIEW_IDLE, status: 'starting', zoneId, lookId, showing: this.state.showing === zoneId ? zoneId : null })
    if (!this.asking) void this.ask()
  }

  /** No preview: the server's ends (one still on its way ends when it's answered), and the stage draws the live stream. */
  stop(): void {
    if (this.wanted === null && this.state.status === 'idle') return
    this.wanted = null
    if (!this.asking) this.drop()
    this.set(PREVIEW_IDLE)
  }

  /**
   * After a reconnect (the live client's resync): the server may have ended the preview while nobody
   * watched it, or restarted, so the one wanted is asked for again, and its stream watched again (a
   * refusal in the meantime stopped that). The answer replaces whatever the server still holds, as
   * every new preview does.
   */
  resume(): void {
    if (this.wanted === null) return
    this.watch(true)
    this.asked = null
    if (!this.asking) void this.ask()
  }

  /** Back to a page just opened, with no request: for resetDataLayer(). */
  reset(): void {
    this.generation += 1
    this.wanted = null
    this.asked = null
    this.asking = false
    this.previewId = null
    this.watching = false
    this.set(PREVIEW_IDLE)
  }

  private async ask(): Promise<void> {
    const generation = this.generation
    this.asking = true
    while (this.wanted !== null && !same(this.wanted, this.asked)) {
      const choice = this.wanted
      this.asked = choice
      try {
        const started = await api.startPreview(choice)
        if (generation !== this.generation) return
        this.previewId = started.previewId
        if (same(this.wanted, choice)) this.set({ ...PREVIEW_IDLE, status: 'on', ...choice, lights: started.lights, showing: choice.zoneId })
      } catch (error) {
        if (generation !== this.generation) return
        // The server may still hold the last preview: it ends too, so the stage never shows a look not chosen.
        if (same(this.wanted, choice)) {
          this.drop()
          this.asked = choice // asked once: a refusal isn't asked again until another choice comes between
          this.set({ ...PREVIEW_IDLE, status: 'failed', ...choice, error })
        }
      }
    }
    this.asking = false
    if (this.wanted === null) this.drop()
  }

  /** Ends the server's preview, if it holds one, and stops watching the preview stream. */
  private drop(): void {
    const id = this.previewId
    this.previewId = null
    this.asked = null
    // A preview already gone (it ended unwatched, or the server restarted) has nothing left to end.
    if (id !== null) void api.stopPreview(id).catch(() => undefined)
    this.frames.clearPreview()
    this.watch(false)
  }

  private watch(on: boolean): void {
    if (this.watching === on) return
    this.watching = on
    this.client()?.subscribeFrames(on ? ['live', 'preview'] : ['live'])
  }

  private set(state: PreviewState): void {
    this.state = state
    for (const listener of this.listeners) listener()
  }
}
