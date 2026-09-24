import type { ReactNode } from 'react'
import { cx } from './cx'
import { Icon } from './icon'
import type { IconName } from './icons'

export type ChipVariant = 'input' | 'mod' | 'quiet' | 'signal' | 'solid'
export type TagVariant = 'plain' | 'signal' | 'solid'

const CHIP: Record<ChipVariant, string> = {
  input: 'border-line bg-control text-text-2',
  mod: 'border-line-strong bg-transparent text-text-2',
  quiet: 'border-line bg-transparent text-text-3',
  signal: 'border-signal-line bg-signal-bg text-signal',
  solid: 'border-text bg-text text-on-text',
}

const TAG: Record<TagVariant, string> = {
  plain: 'border-line bg-bg/88 text-text',
  signal: 'border-signal-line bg-signal-ink/92 text-signal',
  solid: 'border-text bg-text text-on-text',
}

interface BadgeProps {
  icon?: IconName
  children: ReactNode
  className?: string
}

/** §6.1 Chip: inputs a look uses, modifiers, states. */
export function Chip({ variant = 'input', icon, children, className }: BadgeProps & { variant?: ChipVariant }) {
  return (
    <span
      className={cx(
        'inline-flex h-5.5 items-center gap-1.25 rounded-pill border px-2 text-[11.5px] font-semibold whitespace-nowrap',
        CHIP[variant],
        className,
      )}
    >
      {icon && <Icon name={icon} size={13} strokeWidth={1.8} />}
      {children}
    </span>
  )
}

/** §6.1 Tag: a pill drawn on the stage. */
export function Tag({ variant = 'plain', icon, children, className }: BadgeProps & { variant?: TagVariant }) {
  return (
    <span
      className={cx(
        'inline-flex h-6.5 items-center gap-1.5 rounded-pill border px-2.25 text-[11.5px] font-bold tracking-[0.03em] whitespace-nowrap',
        TAG[variant],
        className,
      )}
    >
      {icon && <Icon name={icon} size={13} strokeWidth={1.8} />}
      {children}
    </span>
  )
}

/** §6.1 Label: 11/600 caps (the label-caps utility from tokens.css). */
export function Label({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cx('label-caps', className)}>{children}</span>
}
