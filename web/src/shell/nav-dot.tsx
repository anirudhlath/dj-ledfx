import type { AttentionCounts } from '@/chrome/state'
import { cx } from '@/design/cx'
import type { NavItem } from './nav'

export interface NavDotProps {
  item: NavItem
  attention: AttentionCounts
  /** Where the dot sits on its item. */
  className: string
}

/** The signal dot on a place that needs attention (spec §9.5), and its words for screen readers. */
export function NavDot({ item, attention, className }: NavDotProps) {
  if (item.dot === undefined || attention[item.dot] === 0) return null
  return (
    <>
      <span aria-hidden="true" className={cx('absolute size-1.75 rounded-full bg-signal', className)} />
      <span className="sr-only">, needs attention</span>
    </>
  )
}
