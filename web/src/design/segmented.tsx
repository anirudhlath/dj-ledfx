import { Toggle } from '@base-ui/react/toggle'
import { ToggleGroup } from '@base-ui/react/toggle-group'
import { cx } from './cx'
import { Icon } from './icon'
import type { IconName } from './icons'

export interface SegmentedOption<T extends string> {
  value: T
  label: string
  icon?: IconName
}

export interface SegmentedProps<T extends string> {
  /** Names the group for assistive tech. */
  label: string
  value: T
  options: readonly SegmentedOption<T>[]
  onValueChange: (value: T) => void
  className?: string
}

/** §6.1 Segmented: exactly one option is always selected. */
export function Segmented<T extends string>({ label, value, options, onValueChange, className }: SegmentedProps<T>) {
  return (
    <ToggleGroup
      aria-label={label}
      value={[value]}
      onValueChange={(next) => {
        // Base UI deselects on a second click; a segmented control never ends up empty.
        const picked = next[0] as T | undefined
        if (picked !== undefined) onValueChange(picked)
      }}
      className={cx('inline-flex gap-0.5 rounded-control border border-line bg-raised p-0.5', className)}
    >
      {options.map((option) => (
        <Toggle
          key={option.value}
          value={option.value}
          className="inline-flex h-6.5 items-center gap-1.5 rounded-chip px-2.75 text-data font-semibold text-text-3 transition-colors duration-(--duration-fast) ease-out hover:text-text-2 data-[pressed]:bg-control-hover data-[pressed]:text-text"
        >
          {option.icon && <Icon name={option.icon} size={15} />}
          {option.label}
        </Toggle>
      ))}
    </ToggleGroup>
  )
}
