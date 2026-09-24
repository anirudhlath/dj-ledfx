export interface PlaceholderProps {
  /** What this page becomes. */
  name: string
  /** The milestone that builds it (engine spec §10). */
  milestone: string
}

/** F0 stands in for every page with a calm empty state (spec §4.3 routes). */
export function Placeholder({ name, milestone }: PlaceholderProps) {
  return (
    <div className="grid h-full place-items-center p-6">
      <div className="flex max-w-sm flex-col items-center gap-2 text-center">
        <p className="font-serif text-display-lg">{name}</p>
        <p className="text-body text-text-2">Built in {milestone}.</p>
      </div>
    </div>
  )
}
