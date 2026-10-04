// A ZoneCard's "More" (§6.3): Edit look, Change look, Restart, Show lights on the map. Edit look opens the
// look's editor (F8's), Change look the composer on this zone, and Show lights the map (F7's; F3
// decision 25). The face is Main.html's: 28 px, chip radius, text-3, grown to the touch minimum.
import type { Id } from '@/api/contract'
import { Icon } from '@/design/icon'
import { Menu, MenuItem, MenuLinkItem } from '@/design/menu'

export interface ZoneMenuProps {
  zoneId: Id
  zoneName: string
  lookId: Id
  onRestart: () => void
}

export function ZoneMenu({ zoneId, zoneName, lookId, onRestart }: ZoneMenuProps) {
  const label = `More for ${zoneName}`
  return (
    <Menu
      label={label}
      trigger={
        <button
          type="button"
          aria-label={label}
          className="inline-flex size-7 shrink-0 items-center justify-center rounded-chip text-text-3 touch-target hover:text-text"
        >
          <Icon name="more" />
        </button>
      }
    >
      <MenuLinkItem to={`/looks/${encodeURIComponent(lookId)}`}>Edit look</MenuLinkItem>
      <MenuLinkItem to={`/live/put?zone=${encodeURIComponent(zoneId)}`}>Change look</MenuLinkItem>
      <MenuItem onClick={onRestart}>Restart</MenuItem>
      <MenuLinkItem to={`/map/${encodeURIComponent(zoneId)}`}>Show lights on the map</MenuLinkItem>
    </Menu>
  )
}
