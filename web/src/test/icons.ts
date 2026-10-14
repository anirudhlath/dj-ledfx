import { ICONS, type IconName } from '@/design/icons'

/** What an icon draws, as the markup a browser serialises: what an <Icon>'s svg holds once it is in the DOM. */
export function payload(name: IconName): string {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
  svg.innerHTML = ICONS[name]
  return svg.innerHTML
}
