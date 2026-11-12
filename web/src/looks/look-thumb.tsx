// §6.4 LookThumb, a look's motion portrait: a 16:10 scene keyed by looks.json's `thumbnail`, with that
// look's motif drawn on it, verbatim from Looks.html (F5 decision 2). A look with no motif is the scene
// alone, the ground every render draws one on (F4 ruling 7, F5 decision 7). A motif is drawn paused
// (`data-paused`, styles/app.css), at the moment its author drew it, and moves only while it's on screen
// (use-thumb-motion.ts): an ambient motif runs its loop, a tempo or audio one follows the beat clock
// (thumb-writer.ts). `live` is §6.4's interface: false keeps it at its authored moment.
import { useQuery } from '@tanstack/react-query'
import { type CSSProperties, type ReactNode, useId, useRef } from 'react'
import type { Id } from '@/api/contract'
import { queries } from '@/api/queries'
import { cx } from '@/design/cx'
import { LIVE_RENDER, LIVE_SPEC } from '@/design/live-numbers'
import './looks-render.css'
import { instanceMarkup, motifFor } from './motif'
import { useThumbMotion } from './use-thumb-motion'

/**
 * The composer's tile (§6.4 LookTile: its width, at 16:10), the phone's look row (§8.10), the library's card
 * (Looks.html's), or the box beside a recent look on Nothing running (§9.4), desktop's and the phone's.
 */
export type ThumbSize = 'tile' | 'row' | 'card' | 'recent' | 'recent-phone'

const { width, height, background } = LIVE_RENDER.lookThumb
const card = LIVE_RENDER.lookCard.thumb
const BOX: Record<ThumbSize, { className: string; style: CSSProperties }> = {
  tile: { className: 'w-full rounded-tile border', style: { aspectRatio: `${width} / ${height}` } },
  row: { className: 'shrink-0 rounded-control', style: { ...LIVE_SPEC.phoneComposer.thumb } },
  card: { className: 'w-full rounded-tile border border-line', style: { aspectRatio: `${card.width} / ${card.height}` } },
  // State-Nothing-Running's and Phone-State-Nothing-Running's boxes, drawn with no border.
  recent: { className: 'h-11.5 w-18 shrink-0 rounded-control', style: {} },
  'recent-phone': { className: 'h-10.5 w-16 shrink-0 rounded-control', style: {} },
}

export interface LookThumbProps {
  lookId: Id
  size: ThumbSize
  /** The frame's border, which a tile's state sets. */
  className?: string
  /** What's drawn over the scene: a tile's tag. */
  children?: ReactNode
  /** §6.4, F5 decision 8: false keeps the motif at its authored moment. Defaults to true. */
  live?: boolean
}

export function LookThumb({ lookId, size, className, children, live = true }: LookThumbProps) {
  const thumbnail = useQuery(queries.looks()).data?.find((look) => look.id === lookId)?.thumbnail
  const motif = motifFor(thumbnail)
  const svg = useRef<SVGSVGElement>(null)
  useThumbMotion(svg, motif?.beat, live)
  // Looks.html numbers its motifs' ids `lk<n>`; each thumb here has its own prefix (F5 decision 3).
  const prefix = `tb${useId().replace(/[^\w-]/g, '')}`
  const box = BOX[size]
  return (
    <span
      aria-hidden="true"
      // React drops a null attribute, and a look with no thumbnail is still the thumb to find.
      data-thumb={thumbnail ?? ''}
      className={cx('relative block overflow-hidden', box.className, className)}
      style={{ ...box.style, background }}
    >
      {motif && (
        <svg
          ref={svg}
          className="tb absolute inset-0 block size-full"
          data-paused=""
          data-beat={motif.beat ? '' : undefined}
          viewBox={`0 0 ${width} ${height}`}
          preserveAspectRatio="xMidYMid slice"
          aria-hidden="true"
          focusable="false"
          dangerouslySetInnerHTML={{ __html: instanceMarkup(motif, prefix) }}
        />
      )}
      {children}
    </span>
  )
}
