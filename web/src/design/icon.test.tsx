import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Icon } from './icon'
import { ICONS, type IconName } from './icons'

function payload(name: IconName): string {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
  svg.innerHTML = ICONS[name]
  return svg.innerHTML
}

describe('Icon', () => {
  it('draws the payload for its name, hidden from assistive tech', () => {
    const { container } = render(<Icon name="live" size={20} />)
    const svg = container.querySelector('svg')!
    expect(svg.innerHTML).toBe(payload('live'))
    expect(svg).toHaveAttribute('aria-hidden', 'true')
    expect(svg).toHaveAttribute('width', '20')
    expect(svg).toHaveAttribute('stroke', 'currentColor')
    expect(svg).toHaveAttribute('stroke-width', '1.6')
  })

  it('draws every icon in the handoff', () => {
    const names = Object.keys(ICONS) as IconName[]
    expect(names).toHaveLength(65)
    for (const name of names) {
      const { container, unmount } = render(<Icon name={name} />)
      expect(container.querySelector('svg')!.childElementCount, name).toBeGreaterThan(0)
      unmount()
    }
  })
})
