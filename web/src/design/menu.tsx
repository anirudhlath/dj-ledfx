// A menu on Base UI's Menu (docs: node_modules/@base-ui/react/docs/react/components/menu.md): a ZoneCard's
// More (§6.3). Its list opens inside the dialog or the <main> around its trigger, as Select's does, so it
// is part of the page around it (axe's region rule; CLAUDE.md, Gotchas). A link item is a router Link.
import { Menu as BaseMenu } from '@base-ui/react/menu'
import { useCallback, useRef, type ReactElement, type ReactNode } from 'react'
import { Link } from 'react-router'
import { Icon } from './icon'
import type { IconName } from './icons'

/** Where the list opens: inside the dialog or the <main> around the trigger, else <body>. */
const HOSTS = '[role="dialog"], [role="alertdialog"], main'

const ITEM =
  'flex h-8 cursor-pointer items-center gap-2.5 px-3 text-size-control text-text-2 outline-none select-none data-[highlighted]:bg-control data-[highlighted]:text-text max-md:h-(--touch-min)'

export interface MenuProps {
  trigger: ReactElement
  /** The menu's accessible name. */
  label: string
  children: ReactNode
  align?: 'start' | 'center' | 'end'
}

export function Menu({ trigger, label, children, align = 'end' }: MenuProps) {
  // Base UI reads the ref when the list opens; while it's empty (no host found) the list goes to <body>.
  const host = useRef<HTMLElement | null>(null)
  const findHost = useCallback((element: HTMLElement | null) => {
    host.current = element?.closest<HTMLElement>(HOSTS) ?? null
  }, [])
  return (
    <BaseMenu.Root>
      <BaseMenu.Trigger ref={findHost} render={trigger} />
      <BaseMenu.Portal container={host}>
        <BaseMenu.Positioner sideOffset={4} align={align} className="z-50">
          <BaseMenu.Popup aria-label={label} className="min-w-44 rounded-card border border-line-strong bg-raised py-1 shadow-pop outline-none">
            {children}
          </BaseMenu.Popup>
        </BaseMenu.Positioner>
      </BaseMenu.Portal>
    </BaseMenu.Root>
  )
}

export function MenuItem({ icon, onClick, children }: { icon?: IconName; onClick: () => void; children: ReactNode }) {
  return (
    <BaseMenu.Item onClick={onClick} className={ITEM}>
      {icon && <Icon name={icon} size={15} />}
      {children}
    </BaseMenu.Item>
  )
}

/** An item that goes to `to` in the app. The menu closes on the way (`closeOnClick`; LinkItem's default is false). */
export function MenuLinkItem({ icon, to, children }: { icon?: IconName; to: string; children: ReactNode }) {
  return (
    <BaseMenu.LinkItem closeOnClick render={<Link to={to} />} className={ITEM}>
      {icon && <Icon name={icon} size={15} />}
      {children}
    </BaseMenu.LinkItem>
  )
}
