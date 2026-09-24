import { NavLink } from 'react-router'
import type { AttentionCounts } from '@/chrome/state'
import { Icon } from '@/design/icon'
import { TAB_ITEMS, hasDot } from './nav'

/** §4.2 tab bar (Phone-Live.png). The OS home indicator gets env(safe-area-inset-bottom). */
export function TabBar({ attention }: { attention: AttentionCounts }) {
  return (
    <nav
      aria-label="Main"
      className="flex h-[calc(var(--tabbar-h)+env(safe-area-inset-bottom))] shrink-0 border-t border-line-soft bg-bg px-2 pt-1 pb-[env(safe-area-inset-bottom)]"
    >
      {TAB_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          className="relative flex h-14 flex-1 basis-0 flex-col items-center justify-center gap-1 text-[10.5px] font-semibold text-text-3 aria-[current=page]:text-text"
        >
          <Icon name={item.icon} size={22} />
          <span>{item.label}</span>
          {hasDot(item, attention) && (
            <>
              <span aria-hidden="true" className="absolute top-1.5 left-1/2 ml-2 size-1.75 rounded-full bg-signal" />
              <span className="sr-only">, needs attention</span>
            </>
          )}
        </NavLink>
      ))}
    </nav>
  )
}
