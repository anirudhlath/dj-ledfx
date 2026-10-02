import { act, render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { resizeObserved } from '@/test/resize'
import { useElementSize } from './use-element-size'

function Measured() {
  const [ref, size] = useElementSize<HTMLDivElement>()
  return <div ref={ref}>{`${size.width} × ${size.height}`}</div>
}

it('measures an element, 0 × 0 until it has been laid out, and stops when it goes', () => {
  const { unmount } = render(<Measured />)
  expect(screen.getByText('0 × 0')).toBeInTheDocument()
  act(() => resizeObserved(300, 200))
  expect(screen.getByText('300 × 200')).toBeInTheDocument()
  unmount()
  // Nothing is observed any more, so a later layout reaches no one.
  act(() => resizeObserved(10, 10))
})
