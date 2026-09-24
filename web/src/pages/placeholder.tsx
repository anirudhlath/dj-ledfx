import { EmptyState } from './empty-state'

export interface PlaceholderProps {
  /** What this page becomes. */
  name: string
  /** The milestone that builds it (engine spec §10). */
  milestone: string
}

/** F0 stands in for every page with a calm empty state (spec §4.3 routes). */
export function Placeholder({ name, milestone }: PlaceholderProps) {
  return <EmptyState title={name}>Built in {milestone}.</EmptyState>
}
