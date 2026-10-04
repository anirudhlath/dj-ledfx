import { render, screen } from '@testing-library/react'
import { createRef } from 'react'
import { describe, expect, it } from 'vitest'
import { writeProgress } from './progress'
import { ProgressBar } from './progress-bar'

describe('ProgressBar', () => {
  it('says how far along it is, clamped, and moves from an animation frame without React', () => {
    const ref = createRef<HTMLSpanElement>()
    render(<ProgressBar label="Dissolving" value={1.4} ref={ref} />)
    const bar = screen.getByRole('progressbar', { name: 'Dissolving' })
    expect(bar).toHaveAttribute('aria-valuenow', '100')
    writeProgress(ref.current!, 0.25)
    expect(bar).toHaveAttribute('aria-valuenow', '25')
    expect((bar.firstElementChild as HTMLElement).style.width).toBe('25%')
  })
})
