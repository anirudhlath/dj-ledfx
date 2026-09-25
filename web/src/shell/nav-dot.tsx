import { useAttentionCounts } from '@/chrome/hooks'
import { cx } from '@/design/cx'
import type { NavItem } from './nav'

export interface NavDotProps {
  item: NavItem
  /** Where the dot sits on its item. */
  className: string
}

/**
 * The signal dot on a place that needs attention (spec §9.5), and its words for screen readers.
 * None before the server's first attention snapshot.
 */
export function NavDot({ item, className }: NavDotProps) {
  const counts = useAttentionCounts()
  if (item.dot === undefined || counts === null || counts[item.dot] === 0) return null
  return (
    <>
      <span aria-hidden="true" className={cx('absolute size-1.75 rounded-full bg-signal', className)} />
      <span className="sr-only">, needs attention</span>
    </>
  )
}
