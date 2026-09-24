import { Icon } from '@/design/icon'

export interface AttentionButtonProps {
  /** How many things need attention (spec §9.5). */
  count: number
  /** "bar": the desktop top bar. "header": the phone header, which hides it at zero. */
  variant: 'bar' | 'header'
  onOpen?: () => void
}

const name = (count: number) => `${count} ${count === 1 ? 'needs' : 'need'} attention`

/** §6.2 AttentionButton. F3 adds AttentionPopover (desktop) and AttentionSheet (phone). */
export function AttentionButton({ count, variant, onOpen }: AttentionButtonProps) {
  if (variant === 'header') {
    if (count === 0) return null
    return (
      <button
        type="button"
        aria-haspopup="dialog"
        aria-label={name(count)}
        onClick={onOpen}
        className="num inline-flex h-(--touch-min) items-center gap-1.5 rounded-pill border border-signal-line bg-signal-bg px-3.5 text-size-control font-bold text-signal"
      >
        <Icon name="alert" size={16} />
        {count}
      </button>
    )
  }

  if (count === 0) {
    return (
      <button
        type="button"
        aria-haspopup="dialog"
        onClick={onOpen}
        className="inline-flex h-9 items-center gap-1.75 rounded-control border border-line px-3 text-data font-semibold text-text-3"
      >
        <Icon name="check" size={15} />
        <span className="tablet:sr-only">All good</span>
      </button>
    )
  }

  return (
    <button
      type="button"
      aria-haspopup="dialog"
      aria-label={name(count)}
      onClick={onOpen}
      className="inline-flex h-9 items-center gap-2 rounded-control border border-signal-line bg-signal-bg pr-3 pl-2.5 text-data font-semibold whitespace-nowrap text-signal"
    >
      <Icon name="alert" size={15} />
      <span className="tablet:hidden">Needs attention</span>
      <span className="num inline-flex h-4.5 min-w-4.5 items-center justify-center rounded-pill bg-signal px-1.25 text-label font-bold text-signal-ink">
        {count}
      </span>
    </button>
  )
}
