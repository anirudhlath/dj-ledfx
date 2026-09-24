import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { Field } from './field'
import { Select } from './select'

const TRANSITIONS = { cut: 'Cut', fade: 'Fade · 1 s', dissolve: 'Dissolve · 3 s' }

function Transition() {
  const [value, setValue] = useState<keyof typeof TRANSITIONS>('dissolve')
  return (
    <>
      <Select label="Transition" value={value} items={TRANSITIONS} onValueChange={setValue} />
      <output>{value}</output>
    </>
  )
}

describe('Select', () => {
  it('shows the label of the current value and picks another', async () => {
    render(<Transition />)
    const trigger = screen.getByRole('combobox', { name: 'Transition' })
    expect(trigger).toHaveTextContent('Dissolve · 3 s')
    await userEvent.click(trigger)
    await userEvent.click(await screen.findByRole('option', { name: 'Cut' }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('cut'))
    expect(trigger).toHaveTextContent('Cut')
  })
})

describe('Field', () => {
  it('labels its input and shows the unit', async () => {
    const onChange = vi.fn()
    render(<Field label="Height" unit="m" defaultValue="1.20" onChange={onChange} />)
    const input = screen.getByLabelText('Height')
    expect(input).toHaveValue('1.20')
    expect(screen.getByText('m')).toBeInTheDocument()
    await userEvent.type(input, '5')
    expect(onChange).toHaveBeenCalled()
  })
})
