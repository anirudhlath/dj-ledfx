// §6.4 LookThumb, a look's motion portrait: a 16:10 scene keyed by looks.json's `thumbnail`. F5 ports the
// 29 motifs from reference/Looks.html; until then a thumb is the scene with no motif on it, the ground
// every render draws one on (F4 ruling 7), so F5 swaps the motif in without touching a caller. It takes
// §6.4's `live` with the motifs, which are what moves.
import { useQuery } from '@tanstack/react-query'
import type { CSSProperties, ReactNode } from 'react'
import type { Id } from '@/api/contract'
import { queries } from '@/api/queries'
import { cx } from '@/design/cx'
import { LIVE_RENDER, LIVE_SPEC } from '@/design/live-numbers'

/** The composer's tile (§6.4 LookTile: its width, at 16:10) or the phone's look row (§8.10). */
export type ThumbSize = 'tile' | 'row'

const { width, height, background } = LIVE_RENDER.lookThumb
const BOX: Record<ThumbSize, { className: string; style: CSSProperties }> = {
  tile: { className: 'w-full rounded-tile border', style: { aspectRatio: `${width} / ${height}` } },
  row: { className: 'shrink-0 rounded-control', style: { ...LIVE_SPEC.phoneComposer.thumb } },
}

export interface LookThumbProps {
  lookId: Id
  size: ThumbSize
  /** The frame's border, which a tile's state sets. */
  className?: string
  /** What's drawn over the scene: a tile's tag. */
  children?: ReactNode
}

export function LookThumb({ lookId, size, className, children }: LookThumbProps) {
  const thumbnail = useQuery(queries.looks()).data?.find((look) => look.id === lookId)?.thumbnail
  const box = BOX[size]
  return (
    <span
      aria-hidden="true"
      data-thumb={thumbnail}
      className={cx('relative block overflow-hidden', box.className, className)}
      style={{ ...box.style, background }}
    >
      {children}
    </span>
  )
}
