import { describe, expect, it } from 'vitest'
import { routerBasename } from './router'

describe('routerBasename', () => {
  // Review focus: React Router won't match a bare /next against "/next/", and FastAPI serves it.
  it("drops the trailing slash from Vite's base", () => {
    expect(routerBasename('/next/')).toBe('/next')
  })

  it('keeps a root base a root, for when F11 serves the app at /', () => {
    expect(routerBasename('/')).toBe('/')
  })
})
