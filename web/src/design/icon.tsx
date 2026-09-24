import { ICONS, type IconName } from './icons'

export interface IconProps {
  name: IconName
  /** Pixel size of the 24 px grid (spec §5.5). */
  size?: number
  strokeWidth?: number
  className?: string
}

/** One of the handoff's 65 icons, drawn as icons.ts says: stroke currentColor, round caps and joins. */
export function Icon({ name, size = 16, strokeWidth = 1.6, className }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      className={className ? `block shrink-0 ${className}` : 'block shrink-0'}
      dangerouslySetInnerHTML={{ __html: ICONS[name] }}
    />
  )
}
