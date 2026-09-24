import { Link, NavLink } from 'react-router'
import type { AttentionCounts } from '@/chrome/state'
import { Icon } from '@/design/icon'
import { Logo } from './logo'
import { RAIL_ITEMS, hasDot } from './nav'

export interface RailProps {
  attention: AttentionCounts
  server: string
}

/** §4.1 rail (Main.png). */
export function Rail({ attention, server }: RailProps) {
  return (
    <nav
      aria-label="Main"
      className="flex h-full w-(--rail-w) flex-col items-center gap-1.5 border-r border-line-soft bg-bg pt-3.5"
    >
      <Link to="/live" aria-label="dj-ledfx home" className="mb-3.5 flex size-11 items-center justify-center text-text">
        <Logo />
      </Link>
      {RAIL_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          className="relative flex size-14 flex-col items-center justify-center gap-1.25 rounded-tile text-[10.5px] font-semibold tracking-[0.02em] text-text-3 transition-colors duration-(--duration-fast) ease-out hover:text-text-2 aria-[current=page]:bg-control aria-[current=page]:text-text"
        >
          <Icon name={item.icon} size={20} />
          <span>{item.label}</span>
          {hasDot(item, attention) && (
            <>
              <span aria-hidden="true" className="absolute top-1.5 right-3 size-1.75 rounded-full bg-signal shadow-[0_0_0_2px_var(--color-bg)]" />
              <span className="sr-only">, needs attention</span>
            </>
          )}
        </NavLink>
      ))}
      <div className="flex-1" />
      <p className="num rotate-180 pb-4 text-[9.5px] tracking-[0.08em] text-text-3 [writing-mode:vertical-rl]">
        dj-ledfx · {server}
      </p>
    </nav>
  )
}
