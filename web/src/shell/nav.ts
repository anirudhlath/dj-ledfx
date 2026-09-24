import type { AttentionCounts } from '@/chrome/state'
import type { IconName } from '@/design/icons'

export interface NavItem {
  to: string
  label: string
  icon: IconName
  /** The attention count that puts a signal dot on this item (spec §9.5). */
  dot?: keyof Omit<AttentionCounts, 'total'>
}

/** §4.1: the desktop rail. */
export const RAIL_ITEMS: readonly NavItem[] = [
  { to: '/live', label: 'Live', icon: 'live' },
  { to: '/looks', label: 'Looks', icon: 'looks' },
  { to: '/map', label: 'Map', icon: 'map' },
  { to: '/devices', label: 'Devices', icon: 'devices', dot: 'lights' },
  { to: '/inputs', label: 'Inputs', icon: 'inputs', dot: 'inputs' },
  { to: '/settings', label: 'Settings', icon: 'settings' },
]

/** §4.2: the phone tab bar. The map is reached from Devices; Tempo is the phone's /inputs. */
export const TAB_ITEMS: readonly NavItem[] = [
  { to: '/live', label: 'Live', icon: 'live' },
  { to: '/looks', label: 'Looks', icon: 'looks' },
  { to: '/devices', label: 'Devices', icon: 'devices', dot: 'lights' },
  { to: '/inputs', label: 'Tempo', icon: 'tempo', dot: 'inputs' },
  { to: '/settings', label: 'Settings', icon: 'settings' },
]
