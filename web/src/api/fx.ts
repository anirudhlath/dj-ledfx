// "Effects in space" (§7.4, §12.4): what each zone draws in the room, beside its lights. Each fx message is
// the whole picture, so the store keeps the latest one, by zone, for each stream; it never grows past one
// message. React never watches it: the stage draws it on its own cadence (cadence.ts), and `version` moves
// with every picture stored, as the frame store's does with every frame, so the stage knows to draw.
import type { FrameStream, Id } from './contract'
import type { FxMessage, ZoneFx } from './ws-messages'

export interface FxStoreOptions {
  /**
   * Whether the preview stream's frames are held (FrameStore.previewHeld): while the server may be playing a
   * look that was chosen over, its fx are held as its frames are, so the stage shows one look on the zone.
   */
  previewHeld?: () => boolean
}

export class FxStore {
  readonly live = new Map<Id, ZoneFx>()
  readonly preview = new Map<Id, ZoneFx>()
  /** Moves with every picture stored or cleared: redraw when it has moved. */
  version = 0
  private readonly waiting = new Set<() => void>()
  private readonly previewHeld: () => boolean

  constructor({ previewHeld = () => false }: FxStoreOptions = {}) {
    this.previewHeld = previewHeld
  }

  get(zoneId: Id, stream: FrameStream = 'live'): ZoneFx | undefined {
    return (stream === 'live' ? this.live : this.preview).get(zoneId)
  }

  /** Whether there's nothing to draw. */
  get empty(): boolean {
    return this.live.size === 0 && this.preview.size === 0
  }

  /** The message's picture replaces the last one; a zone it leaves out has nothing to draw. Of a zone sent twice, the last wins. */
  apply(message: FxMessage): void {
    const held = this.previewHeld()
    this.live.clear()
    if (!held) this.preview.clear()
    for (const zone of message.zones) {
      if (zone.stream === 'live') this.live.set(zone.zoneId, zone)
      else if (!held) this.preview.set(zone.zoneId, zone)
    }
    this.bump()
  }

  /** Nothing to draw: the link dropped, or the stage stopped asking. */
  clear(): void {
    if (this.empty) return
    this.live.clear()
    this.preview.clear()
    this.bump()
  }

  /** Calls `wake` once, when the version next moves; returns what stops it waiting. */
  onNextChange(wake: () => void): () => void {
    this.waiting.add(wake)
    return () => void this.waiting.delete(wake)
  }

  private bump(): void {
    this.version += 1
    if (this.waiting.size === 0) return
    const woken = [...this.waiting]
    this.waiting.clear()
    for (const wake of woken) wake()
  }
}
