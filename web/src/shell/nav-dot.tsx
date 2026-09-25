import { useAttentionCount } from '@/chrome/hooks'
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
  // Only an item that can have a dot reads the store.
  return item.dot === undefined ? null : <Dot kind={item.dot} className={className} />
}

function Dot({ kind, className }: { kind: NonNullable<NavItem['dot']>; className: string }) {
  const count = useAttentionCount(kind)
  if (count === null || count === 0) return null
  return (
    <>
      <span aria-hidden="true" className={cx('absolute size-1.75 rounded-full bg-signal', className)} />
      <span className="sr-only">, needs attention</span>
    </>
  )
}
