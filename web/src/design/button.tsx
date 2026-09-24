import type { ComponentPropsWithoutRef, ReactNode } from 'react'
import { Link, type LinkProps } from 'react-router'
import { cx } from './cx'
import { Icon } from './icon'
import type { IconName } from './icons'

export type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger'
export type ButtonSize = 'sm' | 'md' | 'lg' | 'cta'

interface ButtonLook {
  variant?: ButtonVariant
  size?: ButtonSize
  icon?: IconName
  trailingIcon?: IconName
  className?: string
  children: ReactNode
}

export type ButtonProps = ButtonLook & Omit<ComponentPropsWithoutRef<'button'>, keyof ButtonLook>
export type ButtonLinkProps = ButtonLook & Omit<LinkProps, keyof ButtonLook>

// §6.1 Button; sizes from System.png. On phone, sm and md grow to the 44 px touch minimum.
const VARIANT: Record<ButtonVariant, string> = {
  primary: 'border-text bg-text text-on-text',
  secondary: 'border-line bg-control text-text hover:bg-control-hover',
  outline: 'border-line-strong bg-transparent text-text hover:bg-control',
  ghost: 'border-transparent bg-transparent text-text-2 hover:bg-control hover:text-text',
  danger: 'border-signal-line bg-transparent text-signal hover:bg-signal-bg',
}

const SIZE: Record<ButtonSize, string> = {
  sm: 'h-7.5 px-2.5 text-data max-md:h-(--touch-min) max-md:rounded-tile max-md:px-3.5 max-md:text-size-control',
  md: 'h-9 px-3.5 text-body max-md:h-(--touch-min) max-md:rounded-tile max-md:text-size-control',
  lg: 'h-12 px-5 text-section',
  cta: 'h-13 w-full px-5 text-section',
}

const ICON_SIZE: Record<ButtonSize, number> = { sm: 16, md: 16, lg: 18, cta: 18 }

function buttonClass(variant: ButtonVariant, size: ButtonSize, className?: string) {
  return cx(
    'inline-flex shrink-0 items-center justify-center gap-2 rounded-control border font-semibold tracking-[0.005em] whitespace-nowrap',
    'transition-colors duration-(--duration-fast) ease-out disabled:pointer-events-none disabled:opacity-45',
    VARIANT[variant],
    SIZE[size],
    className,
  )
}

function Content({ size, icon, trailingIcon, children }: Pick<ButtonLook, 'icon' | 'trailingIcon' | 'children'> & { size: ButtonSize }) {
  return (
    <>
      {icon && <Icon name={icon} size={ICON_SIZE[size]} />}
      {children}
      {trailingIcon && <Icon name={trailingIcon} size={ICON_SIZE[size]} />}
    </>
  )
}

export function Button({ variant = 'secondary', size = 'md', icon, trailingIcon, className, children, type = 'button', ...rest }: ButtonProps) {
  return (
    <button type={type} className={buttonClass(variant, size, className)} {...rest}>
      <Content size={size} icon={icon} trailingIcon={trailingIcon}>{children}</Content>
    </button>
  )
}

/** §6.1: a Button that navigates renders as a link. */
export function ButtonLink({ variant = 'secondary', size = 'md', icon, trailingIcon, className, children, ...rest }: ButtonLinkProps) {
  return (
    <Link className={buttonClass(variant, size, className)} {...rest}>
      <Content size={size} icon={icon} trailingIcon={trailingIcon}>{children}</Content>
    </Link>
  )
}

export interface IconButtonProps extends Omit<ComponentPropsWithoutRef<'button'>, 'children' | 'aria-label' | 'aria-pressed'> {
  icon: IconName
  /** The accessible name. Icon-only buttons always get one (spec §5.5). */
  label: string
  /** §6.1: an active IconButton inverts to the text fill; it's exposed as aria-pressed. */
  active?: boolean
}

export function IconButton({ icon, label, active, className, type = 'button', ...rest }: IconButtonProps) {
  return (
    <button
      type={type}
      aria-label={label}
      aria-pressed={active}
      className={cx(
        'inline-flex size-8 shrink-0 items-center justify-center rounded-control border transition-colors duration-(--duration-fast) ease-out',
        'disabled:pointer-events-none disabled:opacity-45 max-md:size-(--touch-min) max-md:rounded-tile',
        active ? 'border-text bg-text text-on-text' : 'border-line bg-control text-text-2 hover:bg-control-hover hover:text-text max-md:text-text',
        className,
      )}
      {...rest}
    >
      <Icon name={icon} size={16} className="max-md:size-4.5" />
    </button>
  )
}
