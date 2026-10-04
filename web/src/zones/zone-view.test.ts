import { describe, expect, it } from 'vitest'
import type { Id } from '@/api/contract'
import { buildScenario, type ScenarioName, type ScenarioState } from '@/api/mocks/scenarios'
import { formatSecondsLeft } from '@/lib/format'
import { HERO_NOW } from '@/test/live'
import { runningIn, scenarioWorld } from '@/test/zones'
import { overlayLeftMs, overlayProgress, shortLightsNote, transitionProgress, zoneView, zoneWorld } from './zone-view'

function viewOf(name: ScenarioName, zoneId: Id, { compact = false, change }: { compact?: boolean; change?: (state: ScenarioState) => void } = {}) {
  const { state, world } = scenarioWorld(name, change)
  return zoneView(runningIn(state, zoneId), world, HERO_NOW, compact)
}

describe('zoneView', () => {
  // Main.png's three cards, and F3 decisions 10–13.
  it("says what the hero's cards say", () => {
    expect(viewOf('hero', 'home')).toMatchObject({
      name: 'Whole home',
      lookName: 'Home sunset',
      context: 'Kitchen · Bedroom · Entrance',
      inputs: [{ kind: 'sun', label: 'Sun', icon: 'sun', waiting: false }],
      modifiers: ['Evening'],
      since: 'since 18:04 · 1 h 10 m',
      notes: [],
      transition: null,
    })
    expect(viewOf('hero', 'living')).toMatchObject({
      context: '11 lights',
      inputs: [],
      modifiers: [],
      since: 'since 19:05 · 9 m',
      notes: [
        {
          tone: 'quiet',
          parts: [
            { text: 'Rope offline', strong: true },
            { text: ' since 17:02' },
            { text: ' · ' },
            { text: "Candle 2 was switched off elsewhere and rejoins when it's back on" },
          ],
        },
      ],
    })
    expect(viewOf('hero', 'office')).toMatchObject({
      context: "on the music's beat",
      inputs: [{ kind: 'tempo', label: 'Tempo', icon: 'tempo', waiting: false }],
      since: 'since 19:10 · 4 m',
    })
    expect(viewOf('inputs-down', 'office').context).toBe('on the beat')
    expect(viewOf('dj-playing', 'office').context).toBe("on the DJ's beat")
  })

  it('says "all N lights" when the whole home runs on every light', () => {
    const { state, world } = scenarioWorld('firmware')
    expect(zoneView(runningIn(state, 'home'), world, HERO_NOW).context).toBe(`all ${state.lights.length} lights`)
  })

  // State-Problems' two cards, which are compact.
  it('says what a crashed and a slow zone say', () => {
    expect(viewOf('problems', 'kitchen', { compact: true })).toMatchObject({
      context: '2 lights',
      since: 'stopped at 19:12',
      notes: [{ tone: 'signal', parts: [{ text: 'Layer “Plasma” raised an error at 19:12. The Kitchen lights are holding the last frame.' }] }],
    })
    expect(viewOf('problems', 'living', { compact: true })).toMatchObject({
      since: 'since 18:50',
      notes: [{ tone: 'signal', parts: [{ text: '38', mono: true }, { text: ' of 60 fps for 2 min. The other zones are fine.' }] }],
    })
    // Another zone running slow: the note no longer says the others are fine.
    const both = viewOf('problems', 'living', {
      compact: true,
      change: (state) => Object.assign(runningIn(state, 'office'), { state: 'slow', fps: { actual: 50, target: 60 } }),
    })
    expect(both.notes[0].parts[1].text).toBe(' of 60 fps for 2 min.')
    // A crash with no layer, in a zone whose name ends in "lights".
    const plain = viewOf('problems', 'kitchen', {
      change: (state) => {
        state.zones.find((zone) => zone.id === 'kitchen')!.name = 'Kitchen lights'
        runningIn(state, 'kitchen').error = { at: runningIn(state, 'kitchen').error!.at, layer: '', message: 'raised an error' }
      },
    })
    expect(plain.notes[0].parts[0].text).toBe('The look raised an error at 19:12. Kitchen lights are holding the last frame.')
  })

  // §6.3 "waiting for an input", State-Sheet.
  it("says a waiting zone waits, and turns the missing input's chip signal", () => {
    const waiting = viewOf('waiting', 'living')
    expect(waiting).toMatchObject({
      inputs: [{ kind: 'music', label: 'Music', icon: 'music', waiting: true }],
      since: 'since 19:12 · 2 m',
    })
    // The state's note first; the hero's lights' note (Rope offline …) follows it (F3 decision 13).
    expect(waiting.notes[0]).toEqual({
      tone: 'quiet',
      parts: [{ text: 'Nothing playing on Music Assistant. The look waits dark and starts with the music.' }],
    })
    const forHome = viewOf('waiting', 'living', { change: (state) => (runningIn(state, 'living').waitingFor = ['home-assistant']) })
    expect(forHome.inputs).toEqual([
      { kind: 'music', label: 'Music', icon: 'music', waiting: false },
      { kind: 'home-assistant', label: 'Home Assistant', icon: 'ha', waiting: true },
    ])
    expect(forHome.notes[0].parts[0].text).toBe("Waiting for Home Assistant. The look waits dark and starts when it's there.")
  })

  // State-Sheet's transition card: "Dissolve · 3 s 62%". F3 decision 16.
  it("shows a transition's kind, its duration when the server sends one, and its progress", () => {
    expect(viewOf('transition', 'living').transition).toEqual({ from: 'Fireflies', label: 'Dissolve · 3 s', progress: 0.62, durationS: 3 })
    const unsaid = viewOf('transition', 'living', {
      change: (state) => (runningIn(state, 'living').transition = { from: 'Fireflies', kind: 'fade', progress: 0.25, durationS: 0 }),
    })
    expect(unsaid.transition).toEqual({ from: 'Fireflies', label: 'Fade', progress: 0.25, durationS: null })
  })

  // State-Firmware: "Every light runs its own built-in effect. The Govee lamp has none, so it gets a streamed copy of Flame."
  it('says every light runs its own effect, and which get a streamed copy of what', () => {
    const copy = buildScenario('firmware', HERO_NOW).lights.find((light) => light.status === 'streamed-copy')!
    expect(viewOf('firmware', 'home').notes).toEqual([
      { tone: 'quiet', parts: [{ text: `Every light runs its own built-in effect. ${copy.name} has none, so it gets a streamed copy of Flame.` }] },
    ])
    // A compact card drops it, as it drops the lights' note (F3 decision 2).
    expect(viewOf('firmware', 'home', { compact: true }).notes).toEqual([])

    const two = viewOf('firmware', 'home', {
      change: (state) => Object.assign(state.lights.find((light) => light.name === 'TV Lamp')!, { status: 'streamed-copy', ownEffect: 'LIFX Flame' }),
    })
    const names = two.lights.filter(({ state }) => state.status === 'streamed-copy').map(({ light }) => light.name)
    expect(two.notes[0].parts[0].text).toBe(
      `Every light runs its own built-in effect. ${names[0]} and ${names[1]} have none, so they get streamed copies of Flame.`,
    )

    // A light that streams the look: not every light runs its own effect, so the note says nothing.
    const mixed = viewOf('firmware', 'home', {
      change: (state) => Object.assign(state.lights.find((light) => light.name === 'TV Lamp')!, { status: 'streaming', ownEffect: null }),
    })
    expect(mixed.notes).toEqual([])
  })

  // F3 decision 2: a compact card says "since HH:MM" and drops the lights' note.
  it('keeps a compact card short', () => {
    expect(viewOf('hero', 'living', { compact: true })).toMatchObject({ since: 'since 19:05', notes: [] })
  })

  // Review Focus 4: the socket can name a zone, a look or a light before REST has it.
  it("falls back, without crashing, when REST doesn't know the zone, the look or a light", () => {
    const state = buildScenario('hero', HERO_NOW)
    const living = runningIn(state, 'living')
    const world = zoneWorld({
      zones: undefined,
      looks: [],
      lights: state.lights.filter((light) => light.id !== 'rope'),
      updates: null,
      beatSource: null,
      running: state.running,
      attention: null,
    })
    const view = zoneView({ ...living, lights: [...living.lights, 'a-new-light'] }, world, HERO_NOW)
    expect(view).toMatchObject({ name: 'living', lookName: 'Fireflies', inputs: null, modifiers: [], context: `${living.lights.length + 1} lights` })
    expect(view.lights.map(({ light }) => light.id)).toEqual(living.lights.filter((id) => id !== 'rope'))
    expect(zoneView(runningIn(state, 'office'), world, HERO_NOW).context).toBe('3 lights')
  })

  // Review Focus 5: time runs past what the server said.
  it('never counts below zero or past full', () => {
    const [overlay] = buildScenario('doorbell', HERO_NOW).overlays
    const end = Date.parse(overlay.endsAt)
    expect(overlayLeftMs(overlay, end - 2_400)).toBe(2_400)
    expect(overlayLeftMs(overlay, end + 5_000)).toBe(0)
    expect(formatSecondsLeft(overlayLeftMs(overlay, end + 5_000))).toBe('0.0 s left')
    expect(overlayProgress(0.4, 2_400, 2_400)).toBeCloseTo(0.4)
    expect(overlayProgress(0.4, 2_400, 1_200)).toBeCloseTo(0.7)
    expect(overlayProgress(0.4, 2_400, 0)).toBe(1)
    expect(overlayProgress(0.4, 0, 0)).toBe(1)
    const { state, world } = scenarioWorld('transition')
    const living = runningIn(state, 'living')
    for (const [progress, shown] of [[-0.2, 0], [1.4, 1]] as const) {
      expect(zoneView({ ...living, transition: { ...living.transition!, progress } }, world, HERO_NOW).transition?.progress).toBe(shown)
    }
    // F3 decision 16: on from the served progress at its duration, never past full; held without a duration.
    expect(transitionProgress(0.62, 3, 600)).toBeCloseTo(0.82)
    expect(transitionProgress(0.62, 3, 60_000)).toBe(1)
    expect(transitionProgress(0.62, 3, -600)).toBeCloseTo(0.62)
    expect(transitionProgress(0.62, null, 600)).toBeCloseTo(0.62)
    expect(zoneView({ ...living, lights: [] }, world, HERO_NOW)).toMatchObject({ context: '0 lights', lights: [] })
  })

  // Phone-Live: "Rope offline · Candle 2 switched off elsewhere".
  it("says the lights' news shorter for the phone", () => {
    expect(shortLightsNote(viewOf('hero', 'living').lights)).toEqual({
      tone: 'quiet',
      parts: [{ text: 'Rope offline', strong: true }, { text: ' · ' }, { text: 'Candle 2 switched off elsewhere' }],
    })
    expect(shortLightsNote(viewOf('hero', 'office').lights)).toBeNull()
  })
})
