// "Effects in space" (§7.4, §12.4): what each zone draws in the room, beside its lights. Each fx message is
// the whole picture, so the store keeps the latest one, by zone, for each stream; it never grows past one
// message. React never watches it: the stage draws it on its own cadence (cadence.ts), and `version` moves
// with every picture stored, as the frame store's does with every frame, so the stage knows to draw. A zone
// a picture sends as it was is kept as the object stored before, so the stage's writer (fx-writer.ts) tells
// a zone that changed by its object, and draws nothing new for a picture that changed only zones it leaves out.
import type { FrameStream, Id } from './contract'
import type { FxMessage, FxPlane, FxRing, ZoneFx } from './ws-messages'

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
  /** The zones a message stores, reused from message to message. */
  private readonly kept: ZoneFx[] = []

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
    const kept = this.kept
    kept.length = 0
    for (const zone of message.zones) {
      if (zone.stream === 'preview' && held) continue
      const before = this.get(zone.zoneId, zone.stream)
      kept.push(before !== undefined && sameZoneFx(before, zone) ? before : zone)
    }
    this.live.clear()
    if (!held) this.preview.clear()
    for (const zone of kept) (zone.stream === 'live' ? this.live : this.preview).set(zone.zoneId, zone)
    kept.length = 0
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

const sameNumbers = (a: readonly number[], b: readonly number[]): boolean => a.length === b.length && a.every((value, i) => value === b[i])

function sameList<T>(a: readonly T[] | undefined, b: readonly T[] | undefined, same: (a: T, b: T) => boolean): boolean {
  if (a === undefined || b === undefined) return a === b
  return a.length === b.length && a.every((item, i) => same(item, b[i]))
}

const sameRing = (a: FxRing, b: FxRing) =>
  a.radius === b.radius && a.width === b.width && a.form === b.form && sameNumbers(a.center, b.center) && sameNumbers(a.rgb, b.rgb)

const samePlane = (a: FxPlane, b: FxPlane) =>
  a.width === b.width &&
  sameNumbers(a.point, b.point) &&
  sameNumbers(a.normal, b.normal) &&
  sameNumbers(a.rgb, b.rgb) &&
  (a.ray === undefined || b.ray === undefined ? a.ray === b.ray : sameNumbers(a.ray, b.ray))

/** Whether two pictures of a zone draw the same: every item the client reads, in order. */
function sameZoneFx(a: ZoneFx, b: ZoneFx): boolean {
  return sameList(a.particles, b.particles, sameNumbers) && sameList(a.rings, b.rings, sameRing) && sameList(a.planes, b.planes, samePlane)
}
