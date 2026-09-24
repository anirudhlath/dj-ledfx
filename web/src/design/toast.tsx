import { useEffect, type ReactNode } from 'react'
import { useAnnounce } from './announce'
import { Icon } from './icon'
import type { IconName } from './icons'

export interface ToastProps {
  title: string
  detail?: string
  /** A short mono value on the right, e.g. "1.8 s". */
  readout?: string
  icon?: IconName
  /**
   * The colour of the light the moment is about (the doorbell uses the ring's gold). It tints the
   * border and the readout; the UI adds no colour of its own (spec §5.1).
   */
  tint?: string
  action?: ReactNode
}

/**
 * §6.1 Toast: a 44 px pill for moments, not errors. It isn't a live region of its own (a region
 * that arrives with its text often goes unannounced): it says its title and detail through the
 * page's lasting status region, the Announcer around it.
 */
export function Toast({ title, detail, readout, icon, tint, action }: ToastProps) {
  const announce = useAnnounce()
  useEffect(() => {
    announce(detail ? `${title}, ${detail}` : title)
  }, [announce, title, detail])
  return (
    <div
      className="inline-flex h-11 items-center gap-3 rounded-pill border border-line-strong bg-raised/95 pr-2 pl-3.5 whitespace-nowrap shadow-tip"
      // Live-Doorbell.png: the border is the tint mixed about a third into bg.
      style={tint ? { borderColor: `color-mix(in srgb, ${tint} 32%, var(--color-bg))` } : undefined}
    >
      {icon && <Icon name={icon} size={16} />}
      <span className="text-size-control font-semibold">{title}</span>
      {detail && <span className="text-data text-text-2">{detail}</span>}
      {readout && (
        <span className="num text-meta" style={tint ? { color: tint } : undefined}>
          {readout}
        </span>
      )}
      {action}
    </div>
  )
}
