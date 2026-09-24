import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { Segmented } from './segmented'
import { Slider } from './slider'
import { Switch } from './switch'

describe('Switch', () => {
  it('is a switch that reports the flipped value', async () => {
    const onCheckedChange = vi.fn()
    render(<Switch checked={false} onCheckedChange={onCheckedChange} label="Preview only" tape />)
    const control = screen.getByRole('switch', { name: 'Preview only' })
    expect(control).toHaveAttribute('aria-checked', 'false')
    await userEvent.click(control)
    expect(onCheckedChange).toHaveBeenCalledWith(true)
  })

  it('draws tape on the track only when on', () => {
    const { container, rerender } = render(<Switch checked={false} label="Preview only" tape />)
    expect(container.querySelector('.tape')).toBeNull()
    rerender(<Switch checked label="Preview only" tape />)
    expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'true')
    expect(container.querySelector('.tape')).not.toBeNull()
  })
})

describe('Slider', () => {
  it('is a labelled range input whose value reads as its readout', () => {
    const onValueChange = vi.fn()
    render(<Slider label="Brightness" value={70} onValueChange={onValueChange} format={(v) => `${v}%`} />)
    const slider = screen.getByRole('slider', { name: 'Brightness' })
    expect(slider).toHaveAttribute('aria-valuetext', '70%')
    expect(slider).toHaveStyle({ '--v': '70%' })
    fireEvent.change(slider, { target: { value: '40' } })
    expect(onValueChange).toHaveBeenCalledWith(40)
  })

  it('fills the share of its own range', () => {
    render(<Slider label="Height" value={1.5} min={1} max={3} step={0.1} onValueChange={() => {}} />)
    expect(screen.getByRole('slider', { name: 'Height' })).toHaveStyle({ '--v': '25%' })
  })
})

function View() {
  const [view, setView] = useState<'3d' | 'plan'>('3d')
  return (
    <>
      <Segmented
        label="View"
        value={view}
        options={[
          { value: '3d', label: '3D', icon: 'cube' },
          { value: 'plan', label: 'Plan', icon: 'plan' },
        ]}
        onValueChange={setView}
      />
      <output>{view}</output>
    </>
  )
}

describe('Segmented', () => {
  it('selects the clicked option', async () => {
    render(<View />)
    expect(screen.getByRole('button', { name: '3D' })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByRole('button', { name: 'Plan' }))
    expect(screen.getByRole('button', { name: 'Plan' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: '3D' })).toHaveAttribute('aria-pressed', 'false')
  })

  // Review focus: clicking the selected option again must not leave nothing selected.
  it('keeps the selection when the selected option is clicked again', async () => {
    render(<View />)
    await userEvent.click(screen.getByRole('button', { name: '3D' }))
    expect(screen.getByRole('button', { name: '3D' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('status')).toHaveTextContent('3d')
  })
})
