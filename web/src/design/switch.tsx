import { cx } from './cx'

export interface SwitchProps {
  checked: boolean
  onCheckedChange?: (checked: boolean) => void
  label: string
  /** §5.6: the track turns to tape when on. Only Preview only uses it. */
  tape?: boolean
  className?: string
}

/** §6.1 Switch: a native button with role="switch". */
export function Switch({ checked, onCheckedChange, label, tape = false, className }: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onCheckedChange?.(!checked)}
      className={cx('inline-flex items-center gap-2.5', className)}
    >
      <span
        aria-hidden="true"
        className={cx(
          'relative inline-block h-5 w-8.5 shrink-0 rounded-pill border transition-colors duration-(--duration-fast) ease-out',
          !checked && 'border-line bg-control-hover',
          checked && (tape ? 'tape border-text' : 'border-text bg-text'),
        )}
      >
        <span
          className={cx(
            'absolute top-0.5 size-3.5 rounded-full shadow-[0_1px_2px_rgb(0_0_0/0.5)] transition-[left] duration-(--duration-fast) ease-out',
            checked ? 'left-4 bg-on-text' : 'left-0.5 bg-text-2',
          )}
        />
      </span>
      <span className={cx('text-size-control font-medium', checked ? 'text-text' : 'text-text-2')}>{label}</span>
    </button>
  )
}
