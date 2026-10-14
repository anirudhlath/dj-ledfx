// The composer's state (§8.2, F4 rulings 9–13). The zone and the look are the URL's (?zone=, ?look=,
// spec §4.3), changed in place, so Back leaves the composer whole; the zone falls back to the last one
// used, then the whole home, and a home look locks it to the whole home. useComposeChoice() is what the
// stage needs too; useComposer() is the panel's and the phone's sheet's, and holds the preview while
// either is mounted. Start, Cancel and Close go back to Live (use-close-composer.ts), which ends the preview.
import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router'
import { failureText, startLook } from '@/api/actions'
import type { Id, Inputs, Light, Look, RunningZone, Transition, Zone } from '@/api/contract'
import { useLive, useLiveBy } from '@/api/live-store'
import type { PreviewState } from '@/api/preview'
import { queries } from '@/api/queries'
import { usePreview, usePreviewState } from '@/api/use-preview'
import { useConnectionStatus } from '@/chrome/hooks'
import { useAnnounce } from '@/design/announce'
import type { StageCompose } from '@/stage/stage-view'
import { consequence, type Consequence } from './consequence'
import { lastZone, rememberZone } from './last-zone'
import { chosenZone, composerPath, locksToHome, missingInputs, type MissingInput } from './model'
import { useCloseComposer } from './use-close-composer'

export interface ComposeChoice {
  zones: readonly Zone[] | undefined
  looks: readonly Look[] | undefined
  /** The zone the look goes on: undefined until the zones load. */
  zone: Zone | undefined
  look: Look | undefined
  /** A home look is chosen, so the zone is the whole home. */
  locked: boolean
  /** Chooses a zone, keeping the look; the zone already chosen changes nothing, and adds no entry. */
  choose: (zoneId: Id) => void
  /** Chooses a look, keeping the zone asked for. */
  pick: (lookId: Id) => void
}

/**
 * The last zone started on (F4 ruling 9) as this session of the composer opened. Start writes it, and Live's own
 * instance of useComposeChoice() (the stage's) outlives a session: it reads the zone again each time `composing`
 * turns on, or the stage would outline the zone from before the last Start while the panel chose the new one.
 */
function useRememberedZone(composing: boolean): Id | null {
  const [remembered, setRemembered] = useState(lastZone)
  const [wasComposing, setWasComposing] = useState(composing)
  if (composing !== wasComposing) {
    // React's way to adjust state to a prop.
    setWasComposing(composing)
    if (composing) setRemembered(lastZone())
  }
  return remembered
}

/** The id a choice made in place carries into the next URL: one the server has, and any before it has answered. A stale link's is dropped. */
const carried = (id: Id | null, known: readonly { id: Id }[] | undefined): Id | null =>
  known === undefined || known.some((each) => each.id === id) ? id : null

/** `composing` is false for an instance that Live keeps while the composer is shut; the panel's and Where's exist only while it's open. */
export function useComposeChoice(composing = true): ComposeChoice {
  const zones = useQuery(queries.zones()).data
  const looks = useQuery(queries.looks()).data
  const [params] = useSearchParams()
  const navigate = useNavigate()
  // A choice made in place replaces the entry and keeps its state (COMPOSER_ENTRY, if it has it).
  const { state } = useLocation()
  const remembered = useRememberedZone(composing)
  const asked = params.get('zone')
  const lookId = params.get('look')
  const look = lookId === null ? undefined : looks?.find((each) => each.id === lookId)
  const zone = zones === undefined ? undefined : chosenZone(zones, asked, remembered, look)
  const locked = locksToHome(look)
  const keptZone = carried(asked, zones)
  const keptLook = carried(lookId, looks)
  return {
    zones,
    looks,
    zone,
    look,
    locked,
    choose: (zoneId) => {
      // The chips are disabled under a home look, which locks the zone to the whole home, and a room on the stage isn't: it changes nothing.
      if (locked || zoneId === zone?.id) return
      navigate(composerPath(zoneId, keptLook), { replace: true, state })
    },
    pick: (next) => navigate(composerPath(keptZone, next), { replace: true, state }),
  }
}

/**
 * The look chosen last, by name, while the stage draws the composer's zone from the preview stream: what the stage says it previews. That's
 * the choice, not the frames: until the server plays it the zone still shows the look before, or once one was chosen over, the last frame
 * it drew (PreviewSession.show).
 */
function previewing(preview: PreviewState, zone: Zone, looks: readonly Look[] | undefined): string | null {
  if (preview.showing !== zone.id) return null
  return looks?.find((look) => look.id === preview.lookId)?.name ?? null
}

/** What the stage shows of the composer (§7.6 compose), while it's open. */
export function useStageCompose(composing: boolean): StageCompose | null {
  const { zone, looks, choose } = useComposeChoice(composing)
  const preview = usePreviewState()
  if (!composing || zone === undefined) return null
  return { zoneId: zone.id, previewing: previewing(preview, zone, looks), choose }
}

type InputsRead = Pick<Inputs, 'music' | 'homeAssistant'> | null
/** The heartbeat sends the inputs every second as an equal copy: the same, for what the composer reads. */
const sameInputs = (a: InputsRead, b: InputsRead) => JSON.stringify(a) === JSON.stringify(b)
const NOTHING_RUNS: readonly RunningZone[] = []

/** What runs now, from the live store. */
export const useRunning = (): readonly RunningZone[] => useLive((state) => state.running?.zones ?? NOTHING_RUNS)

export interface Composer extends ComposeChoice {
  running: readonly RunningZone[]
  preview: PreviewState
  /** The inputs a look would wait for (F4 ruling 8). */
  missing: (look: Look) => MissingInput[]
  /** What Start would do (§8.2); null until the zones load. */
  consequence: Consequence | null
  /**
   * The stage shows the look chosen, or is about to: it is chosen on a zone with lights, and the server hasn't refused it. A tile's tag and a
   * row's note claim a preview only then (tileTag()). Built from the expressions the consequence line reads, so they never disagree; not
   * `preview.showing`, which is null while a first choice is starting, so the tag would blink off on every new choice.
   */
  previewed: boolean
  /** Start is on its way. */
  starting: boolean
  /**
   * The link is down (§9.4 Reconnecting: "Controls come back when the link does"): Start waits for it, and the Reconnecting card says why.
   * The choices don't wait, and the preview of the last one is asked for again once the link is back (PreviewSession.resume()).
   */
  frozen: boolean
  /**
   * Starts the look on the zone with `transition` (F4 ruling 13); a failure is said aloud and where the consequence goes, until the next
   * choice, and the composer stays.
   */
  start: (transition: Transition) => void
  /** A choice made in the composer itself (a transition, a category, a search) puts the consequence back in a refused Start's place. */
  forgetStart: () => void
  /** Cancel and Close: back to Live, the lights as they were. */
  close: () => void
}

export function useComposer(): Composer {
  const choice = useComposeChoice()
  const { zone, look } = choice
  const lights = useQuery(queries.lights()).data
  const running = useRunning()
  const inputs = useLiveBy(
    (state): InputsRead => (state.inputs === null ? null : { music: state.inputs.music, homeAssistant: state.inputs.homeAssistant }),
    sameInputs,
  )
  // A zone with no lights has nothing to preview: the engine would refuse it.
  const preview = usePreview(zone !== undefined && zone.lights.length > 0 ? zone.id : null, look?.id ?? null)
  const close = useCloseComposer()
  const announce = useAnnounce()
  const [starting, setStarting] = useState(false)
  const frozen = useConnectionStatus() === 'reconnecting'
  // What a refused Start said, for the choice it was refused on. Another zone or look, from wherever it's chosen (a chip, a tile, a room on
  // the stage, the arrows), is the next choice, and the line goes back to the consequence.
  const [startRefused, setStartRefused] = useState<{ zoneId: Id; lookId: Id; text: string } | null>(null)
  if (startRefused !== null && (startRefused.zoneId !== zone?.id || startRefused.lookId !== look?.id)) {
    // React's way to adjust state to a prop.
    setStartRefused(null)
  }
  // Whether this composer is still on the page: a Start's answer can come after it was left.
  const mounted = useRef(false)
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])
  const names = useMemo(() => new Map<Id, Light>((lights ?? []).map((light) => [light.id, light])), [lights])

  const missing = (each: Look) => missingInputs(each, inputs)
  // The preview state is for the choice made now, from the moment it was asked for: its status says how that went.
  const forThisChoice = preview.zoneId === zone?.id && preview.lookId === look?.id
  const refused = forThisChoice && preview.status === 'failed'
  const previewed = look !== undefined && zone !== undefined && zone.lights.length > 0 && !refused
  const said =
    zone === undefined
      ? null
      : consequence({
          zone,
          look,
          running,
          lights: names,
          plan: forThisChoice && preview.status === 'on' ? preview.lights : null,
          missing: look === undefined ? [] : missing(look),
          // A refused Start is newer than its choice's preview, and says the failure that matters now.
          refused: startRefused?.text ?? (refused && look !== undefined ? failureText(`preview ${look.name}`, preview.error) : null),
        })
  const start = (transition: Transition) => {
    if (zone === undefined || look === undefined || starting || frozen) return
    setStarting(true)
    startLook(zone.id, look.id, transition).then(
      () => {
        rememberZone(zone.id)
        announce(`Started ${look.name} on ${zone.name}.`)
        // The look started wherever the user is by now, and that is said; only a composer still here goes back to Live. Closing one that is
        // gone would step back from the page the user went to, or shut the composer opened since.
        if (mounted.current) close()
      },
      (error: unknown) => {
        setStarting(false)
        const text = failureText(`start ${look.name}`, error)
        setStartRefused({ zoneId: zone.id, lookId: look.id, text })
        announce(text)
      },
    )
  }
  return { ...choice, running, preview, missing, consequence: said, previewed, starting, frozen, start, forgetStart: () => setStartRefused(null), close }
}
