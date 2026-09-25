import { NavLink } from 'react-router'
import { Icon } from '@/design/icon'
import { TAB_ITEMS } from './nav'
import { NavDot } from './nav-dot'

/** §4.2 tab bar (Phone-Live.png). AppShell keeps it above the OS home indicator. */
export function TabBar() {
  return (
    <nav
      aria-label="Main"
      className="flex h-(--tabbar-h) shrink-0 border-t border-line-soft bg-bg px-2 pt-1"
    >
      {TAB_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          className="relative flex h-14 flex-1 basis-0 flex-col items-center justify-center gap-1 text-[10.5px] font-semibold text-text-3 aria-[current=page]:text-text"
        >
          <Icon name={item.icon} size={22} />
          <span>{item.label}</span>
          <NavDot item={item} className="top-1.5 left-1/2 ml-2" />
        </NavLink>
      ))}
    </nav>
  )
}
