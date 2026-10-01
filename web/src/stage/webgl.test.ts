import { afterEach, describe, expect, it, vi } from 'vitest'
import { hasWebGL2 } from './webgl'

describe('the WebGL check', () => {
  afterEach(() => vi.restoreAllMocks())

  it('says no in a browser without WebGL 2', () => {
    expect(hasWebGL2()).toBe(false)
  })

  it('says yes when a canvas gives a WebGL 2 context, and lets the context go', () => {
    const loseContext = vi.fn()
    vi.stubGlobal('WebGL2RenderingContext', class {})
    // `as never`: getContext's overloads each want their own context type.
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({ getExtension: () => ({ loseContext }) } as never)
    expect(hasWebGL2()).toBe(true)
    expect(loseContext).toHaveBeenCalled()
  })

  it('says no when the canvas refuses, or throws', () => {
    vi.stubGlobal('WebGL2RenderingContext', class {})
    const getContext = vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null)
    expect(hasWebGL2()).toBe(false)
    getContext.mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(hasWebGL2()).toBe(false)
  })
})
