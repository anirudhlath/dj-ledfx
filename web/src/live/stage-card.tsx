// A card centred on the stage, the stage's own news: Reconnecting (State-Reconnecting), and Task 16's
// no lights placed (State-No-Lights-Placed) and first run. Both renders draw the same box; what's in it,
// and its width, gap and padding, are each card's.
import type { ReactNode } from 'react'
import { cx } from '@/design/cx'

export interface StageCardProps {
  /** The id of the card's title, which names it. */
  labelledBy: string
  /** Its width, gap and padding: the renders' boxes are content-box, so the width is the content's. */
  className: string
  children: ReactNode
}

export function StageCard({ labelledBy, className, children }: StageCardProps) {
  return (
    <section
      aria-labelledby={labelledBy}
      className={cx(
        'absolute top-1/2 left-1/2 z-10 box-content flex -translate-1/2 flex-col rounded-[16px] border border-line-strong bg-raised/96 shadow-pop',
        className,
      )}
    >
      {children}
    </section>
  )
}
