import { describe, expect, it, vi } from 'vitest'

/** hasWebGL2 as a new page loads it, with nothing asked yet. */
async function newPage() {
  vi.resetModules()
  return (await import('./webgl')).hasWebGL2
}

describe('the WebGL check', () => {
  it('says no in a browser without WebGL 2', async () => {
    const hasWebGL2 = await newPage()
    expect(hasWebGL2()).toBe(false)
  })

  it('says yes when a canvas gives a WebGL 2 context, and lets the context go', async () => {
    const loseContext = vi.fn()
    vi.stubGlobal('WebGL2RenderingContext', class {})
    // `as never`: getContext's overloads each want their own context type.
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({ getExtension: () => ({ loseContext }) } as never)
    const hasWebGL2 = await newPage()
    expect(hasWebGL2()).toBe(true)
    expect(loseContext).toHaveBeenCalled()
  })

  it('says no when the canvas refuses, or throws', async () => {
    vi.stubGlobal('WebGL2RenderingContext', class {})
    const getContext = vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null)
    expect((await newPage())()).toBe(false)
    getContext.mockImplementation(() => {
      throw new Error('blocked')
    })
    expect((await newPage())()).toBe(false)
  })

  // E4: each ask makes a WebGL context and drops it, so a page asks once, however often Live opens.
  it('asks the browser once per page', async () => {
    vi.stubGlobal('WebGL2RenderingContext', class {})
    const getContext = vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({ getExtension: () => null } as never)
    const hasWebGL2 = await newPage()
    expect([hasWebGL2(), hasWebGL2(), hasWebGL2()]).toEqual([true, true, true])
    expect(getContext).toHaveBeenCalledOnce()
  })
})
