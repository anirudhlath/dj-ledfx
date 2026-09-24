import { cx } from '@/design/cx'
import { Icon } from '@/design/icon'
import { Switch } from '@/design/switch'

export interface PreviewOnlySwitchProps {
  on: boolean
  onChange?: (on: boolean) => void
  /** "bar": labelled tape switch (desktop). "header": 44 px eye button (phone). */
  variant: 'bar' | 'header'
}

/** §6.2 PreviewOnlySwitch; §5.6 tape. */
export function PreviewOnlySwitch({ on, onChange, variant }: PreviewOnlySwitchProps) {
  if (variant === 'bar') {
    return <Switch checked={on} onCheckedChange={onChange} label="Preview only" tape />
  }
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label="Preview only"
      onClick={() => onChange?.(!on)}
      className={cx('inline-flex size-(--touch-min) items-center justify-center rounded-pill border', on ? 'tape border-text' : 'border-line bg-control')}
    >
      <span className={cx('inline-flex size-7 items-center justify-center rounded-pill', on ? 'bg-bg text-text' : 'text-text-2')}>
        <Icon name="eye" size={18} />
      </span>
    </button>
  )
}
