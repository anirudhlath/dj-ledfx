import type { ComponentProps, MouseEvent } from 'react'
import { cx } from '@/design/cx'
import { Icon } from '@/design/icon'

export interface AttentionButtonProps extends Omit<ComponentProps<'button'>, 'children'> {
  /** How many things need attention (spec §9.5). */
  count: number
  /** "bar": the desktop top bar. "header": the phone header, which hides it at zero. */
  variant: 'bar' | 'header'
  onOpen?: () => void
}

const name = (count: number) => `${count} ${count === 1 ? 'needs' : 'need'} attention`

/**
 * §6.2 AttentionButton. F3 adds AttentionPopover (desktop) and AttentionSheet (phone): the other
 * button props, `ref` included, reach the <button>, so it can be their trigger as it is.
 */
export function AttentionButton({ count, variant, onOpen, onClick, className, ...rest }: AttentionButtonProps) {
  if (variant === 'header' && count === 0) return null
  const button = {
    type: 'button' as const,
    'aria-haspopup': 'dialog' as const,
    ...rest,
    onClick: (event: MouseEvent<HTMLButtonElement>) => {
      onClick?.(event)
      onOpen?.()
    },
  }

  if (variant === 'header') {
    return (
      <button
        {...button}
        aria-label={name(count)}
        className={cx(
          'num inline-flex h-(--touch-min) items-center gap-1.5 rounded-pill border border-signal-line bg-signal-bg px-3.5 text-size-control font-bold text-signal',
          className,
        )}
      >
        <Icon name="alert" size={16} />
        {count}
      </button>
    )
  }

  if (count === 0) {
    return (
      <button
        {...button}
        className={cx('inline-flex h-9 items-center gap-1.75 rounded-control border border-line px-3 text-data font-semibold text-text-3', className)}
      >
        <Icon name="check" size={15} />
        <span className="tablet:sr-only">All good</span>
      </button>
    )
  }

  return (
    <button
      {...button}
      aria-label={name(count)}
      className={cx(
        'inline-flex h-9 items-center gap-2 rounded-control border border-signal-line bg-signal-bg pr-3 pl-2.5 text-data font-semibold whitespace-nowrap text-signal',
        className,
      )}
    >
      <Icon name="alert" size={15} />
      <span className="tablet:hidden">Needs attention</span>
      <span className="num inline-flex h-4.5 min-w-4.5 items-center justify-center rounded-pill bg-signal px-1.25 text-label font-bold text-signal-ink">
        {count}
      </span>
    </button>
  )
}
