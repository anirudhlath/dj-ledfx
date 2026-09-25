import { describe, expect, it } from 'vitest'
import { mockChoice } from './choice'

describe('mockChoice', () => {
  it('leaves dev on the real server unless a scenario is asked for', () => {
    expect(mockChoice('', { mockBuild: false })).toBeNull()
    expect(mockChoice('?zone=living', { mockBuild: false })).toBeNull()
  })

  it('plays the scenario asked for', () => {
    expect(mockChoice('?scenario=problems', { mockBuild: false })).toEqual({ scenario: 'problems', still: false, protocol: 2 })
  })

  it('holds the beat with ?still', () => {
    expect(mockChoice('?scenario=hero&still', { mockBuild: false })?.still).toBe(true)
  })

  it('always mocks in the mock build, the hero by default', () => {
    expect(mockChoice('', { mockBuild: true })).toEqual({ scenario: 'hero', still: false, protocol: 2 })
  })

  it('plays the hero for a scenario it does not know', () => {
    expect(mockChoice('?scenario=nope', { mockBuild: false })?.scenario).toBe('hero')
  })

  it("speaks today's M1 protocol with ?protocol=1", () => {
    expect(mockChoice('?scenario=hero&protocol=1', { mockBuild: false })?.protocol).toBe(1)
  })
})
