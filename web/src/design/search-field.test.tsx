import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { SearchField } from './search-field'

/** The field as a page holds it: the words in state, so a typed search is the whole word. The spy sees each change the field asks for. */
function renderField(start = '', className?: string) {
  const onValueChange = vi.fn<(value: string) => void>()
  function Page() {
    const [value, setValue] = useState(start)
    return (
      <SearchField
        label="Search things"
        value={value}
        placeholder="Find one"
        className={className}
        onValueChange={(next) => {
          onValueChange(next)
          setValue(next)
        }}
      />
    )
  }
  render(<Page />)
  return { onValueChange, box: screen.getByRole<HTMLInputElement>('searchbox', { name: 'Search things' }) }
}

describe('SearchField', () => {
  it("names the box for a screen reader and puts the placeholder in it, the icon drawing no text of its own", () => {
    const { box } = renderField()
    expect(box).toHaveAttribute('type', 'search')
    expect(box).toHaveAttribute('placeholder', 'Find one')
    expect(screen.getByText('Search things')).toHaveClass('sr-only')
  })

  it('makes the whole face the input\'s label, so a click on it focuses the input', async () => {
    const { box } = renderField()
    const face = box.closest('label')!
    expect(face).toContainElement(box)
    expect(box.labels).toContain(face)
    await userEvent.click(face.querySelector('svg')!)
    expect(box).toHaveFocus()
  })

  it('takes the face\'s size and place from the caller, and brings none of its own', () => {
    const bare = renderField().box.closest('label')!
    expect([...bare.classList].filter((name) => /^(h|w|size|relative|absolute|touch-target|max-md:|md:)/.test(name))).toEqual([])
    document.body.replaceChildren()
    const sized = renderField('', 'h-9 w-70 touch-target').box.closest('label')!
    expect(sized).toHaveClass('h-9', 'w-70', 'touch-target', 'flex', 'rounded-control', 'border-line', 'bg-control')
  })

  it('says what is typed', async () => {
    const { box, onValueChange } = renderField()
    await userEvent.type(box, 'fi')
    expect(onValueChange).toHaveBeenLastCalledWith('fi')
    expect(box).toHaveValue('fi')
  })

  // Base UI's lists stop Esc, so a page's own Esc listens for a key not yet handled: a search with words clears first and marks its key.
  it('clears a search with words on Esc and marks the key handled', () => {
    const { box, onValueChange } = renderField('fi')
    expect(fireEvent.keyDown(box, { key: 'Escape' })).toBe(false)
    expect(onValueChange).toHaveBeenLastCalledWith('')
    expect(box).toHaveValue('')
  })

  it("leaves Esc to the page where there is nothing to clear, a box of spaces included", () => {
    for (const start of ['', '   ']) {
      const { box, onValueChange } = renderField(start)
      expect(fireEvent.keyDown(box, { key: 'Escape' })).toBe(true)
      expect(onValueChange).not.toHaveBeenCalled()
      expect(box).toHaveValue(start)
      document.body.replaceChildren()
    }
  })

  it('reads no other key as a clear', () => {
    const { box, onValueChange } = renderField('fi')
    expect(fireEvent.keyDown(box, { key: 'Enter' })).toBe(true)
    expect(fireEvent.keyDown(box, { key: 'a' })).toBe(true)
    expect(onValueChange).not.toHaveBeenCalled()
  })
})
