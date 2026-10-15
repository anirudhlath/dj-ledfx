// The stage (§7) in its `live`, `compose`, `focus` and `frozen` modes: the canvas, the SVG layer over it
// and the HTML overlays, all placed from one camera pose (camera.ts). What each mode does is decided once
// (behaviour.ts), and the stage is two parts: the picture (the canvas and the SVG layer, greyed while
// frozen) and the interactive layer (the pointer's tooltip, the overlays, the rooms' links), which only
// `live` has. A click on a room is `live`'s and `compose`'s. React renders this when the data, the view
// or the hovered light changes; frames go from the frame store to the canvas without it (§7.5).
import { useMemo, useState, type MouseEvent, type PointerEvent } from 'react'
import { useNavigate } from 'react-router'
import type { Id, Room } from '@/api/contract'
import { useElementSize } from '@/lib/use-element-size'
import { sameEntries, useStable } from '@/lib/use-stable'
import { useReducedMotion } from '@/lib/use-media-query'
import { stageBehaviour, type StageVariant } from './behaviour'
import { stageBodies } from './bodies'
import { FIT_VIEW, fitPose, projectPoint } from './camera'
import { SPEC } from './design-numbers'
import { FrameWriter, sameLayout, writerEntries } from './frame-writer'
import { looksOn, stageLabels } from './labels'
import { anchorOf, lightMarks, statusesOf } from './marks'
import { Legend } from './overlays/legend'
import { LightTooltip } from './overlays/light-tooltip'
import { NoWebGL } from './overlays/no-webgl'
import { PreviewCard, PreviewTag } from './overlays/preview-tag'
import { RoomLinks } from './overlays/room-links'
import { StageSvg, type ComposeShape } from './overlays/stage-svg'
import { StageTools } from './overlays/stage-tools'
import { ZoneTags } from './overlays/zone-tags'
import { SunReadout } from './overlays/sun-readout'
import { ViewControls } from './overlays/view-controls'
import { pickLight, pickRoom, screenPoints } from './picking'
import { roomMask } from './room-mask'
import { StageCanvas } from './stage-canvas'
import { STAGE_LABEL } from './stage-pending'
import { sunScene } from './sun'
import { zoneTags } from './tags'
import { tooltipText } from './tooltip'
import type { StageData } from './use-stage-data'
import { useStageView } from './view-memory'
import { hasWebGL2 } from './webgl'
import { boxOf, subZonesIn, zonePolygons, zoneRooms } from './zone-shape'

/** §7.6 frozen: the last frame, greyed as SPEC.frozen says. */
const GREYED = `grayscale(${SPEC.frozen.grayscale}) brightness(${SPEC.frozen.brightness})`

/**
 * §7.6 focus's "soft vignette" (F3 decision 37): clear over the middle, darkening toward `bg` at the
 * edges, where §7.2 shows the neighbours dimmed.
 */
const FOCUS_VIGNETTE = 'radial-gradient(closest-side, transparent 60%, color-mix(in srgb, var(--color-bg) 70%, transparent) 100%)'

export type { StageVariant } from './behaviour'

/** §7.6 compose: what the composer (§8.2) shows on the stage. */
export interface StageCompose {
  /** The zone it puts the look on: outlined, with the rooms outside it dimmed. */
  zoneId: Id
  /** The look the preview stream draws on the zone, by name; null while it draws none. */
  previewing: string | null
  /** A click on a room (§6.3: "selects the same zone"): the composer chooses its zone as it does a zone chip's. */
  choose: (zoneId: Id) => void
  /** The composer lies over the stage's right side, `--live-panel-w` wide (§4.4's narrow layout): the preview's card keeps out from under it. */
  covered: boolean
}

export interface StageViewProps {
  data: StageData
  /** The phone's stage has no labels and no overlays (§8.10). */
  variant: StageVariant
  /** Where the view is remembered (view-memory.ts). */
  route: string
  /** Where a click on a room goes on Live: its zone's composer (§8.1). In the composer a room is chosen as a zone instead (`compose`). */
  roomTo: (room: Room) => string
  /** The history state a click or a link on a room carries to that page. */
  roomState?: unknown
  /** The zone to outline: the card under the pointer, or the one /live/zones/:zoneId names (F3 decision 23). */
  outlined?: Id | null
  /** §7.6 focus: framed on this zone, the other zones' lights hidden, a soft vignette (Zone detail). */
  focus?: Id | null
  /** §7.6 compose: the composer's zone and preview (Put a look on). */
  compose?: StageCompose | null
}

export function StageView({ data, variant, route, roomTo, roomState, outlined = null, focus = null, compose = null }: StageViewProps) {
  const { home, lights, states, running, zoneNames, zones, sun, frozen } = data
  const [ref, size] = useElementSize<HTMLElement>()
  const [stored, store] = useStageView(route)
  const reducedMotion = useReducedMotion()
  // The zone in focus, once the zones load. A drop keeps its frame and its lights (§7.6 frozen).
  const focusZone = focus === null ? undefined : zones.find((zone) => zone.id === focus)
  // The composer's zone, once the zones load; a drop keeps it, greyed (§7.6 frozen).
  const composeZone = compose === null ? undefined : zones.find((zone) => zone.id === compose.zoneId)
  const previewing = composeZone === undefined ? null : (compose?.previewing ?? null)
  // The composer's stage is the composer's before its zone is known too: not Live's, for a moment, while the zones load.
  const mode = frozen ? 'frozen' : focusZone !== undefined ? 'focus' : compose !== null ? 'compose' : 'live'
  const behaviour = stageBehaviour({ mode, variant, reducedMotion, labels: stored.labels })
  // The phone's stage has no view controls, so it shows the fitted view (§8.10).
  const view = behaviour.overlays ? stored.view : FIT_VIEW
  const [webgl] = useState(hasWebGL2)
  const [hovered, setHovered] = useState<Id | null>(null)
  const [overRoom, setOverRoom] = useState(false)
  // Out of the interactive layer the pointer picks no light, and with no room click no room; the link's
  // return finds nothing picked.
  if (!behaviour.interactive && hovered !== null) setHovered(null)
  if (behaviour.roomClick === null && overRoom) setOverRoom(false)
  const navigate = useNavigate()

  // §7.2: "fit the zone's polygon, tilt …°": focus's zone, or the phone composer's (Phone-PutLookOn).
  // §7.6 focus: "other zones' lights hidden".
  const framedZone = focusZone ?? (behaviour.framesComposeZone ? composeZone : undefined)
  const framing = useMemo(() => {
    const polygons = framedZone === undefined ? [] : zonePolygons(home, framedZone, lights)
    return polygons.length === 0 ? null : polygons.flat()
  }, [framedZone, home, lights])
  const shown = useMemo(() => {
    if (focusZone === undefined) return lights
    const ids = new Set(focusZone.lights)
    return lights.filter((light) => ids.has(light.id))
  }, [focusZone, lights])
  const pose = useMemo(
    () => (framing === null ? fitPose(home.outline, size, view) : fitPose(framing, size, view, SPEC.focus.tiltDeg)),
    [framing, home.outline, size, view],
  )
  const bodies = useMemo(() => stageBodies(shown), [shown])
  // §7.6 compose: "the chosen zone renders the preview stream instead of live", while it draws a look there.
  const previewedLights = previewing === null || composeZone === undefined ? null : composeZone.lights
  const previewed = useMemo(() => (previewedLights === null ? null : new Set(previewedLights)), [previewedLights])
  // The engine pushes `lights` every few seconds while a look plays. The writer's arrays (and the
  // meshes over them) are made from which bodies are drawn alone, and take each push's colours (and
  // a preview's stream) in place; the marks, from each light's status alone (I1).
  const entries = useMemo(() => writerEntries(bodies, shown, states, home.rooms, previewed), [bodies, shown, states, home.rooms, previewed])
  const layout = useStable(entries, sameLayout)
  const writer = useMemo(() => new FrameWriter(layout), [layout])
  const mask = useMemo(() => roomMask(home.rooms), [home.rooms])
  const statuses = useStable(useMemo(() => statusesOf(states), [states]), sameEntries)
  const marks = useMemo(() => (pose === null ? [] : lightMarks(pose, bodies, statuses)), [pose, bodies, statuses])
  const previewedLook = useMemo(
    () => (previewing === null || composeZone === undefined ? null : { zoneId: composeZone.id, lookName: previewing, lights: composeZone.lights }),
    [previewing, composeZone],
  )
  const labels = useMemo(
    () => (behaviour.labels ? stageLabels(home, running, lights, previewedLook) : null),
    [behaviour.labels, home, running, lights, previewedLook],
  )
  const sunDrawn = useMemo(() => sunScene(home, sun, behaviour.sunLabel), [home, sun, behaviour.sunLabel])
  const points = useMemo(() => (pose === null ? [] : screenPoints(pose, bodies)), [pose, bodies])
  // §7.6 compose outlines its zone; §8.1 "Hover a card → its zone outlines on the stage", drawn alike.
  const outlineZone = composeZone ?? (outlined === null ? undefined : zones.find((zone) => zone.id === outlined))
  const outline = useMemo(() => {
    if (pose === null || outlineZone === undefined) return null
    const polygons = zonePolygons(home, outlineZone, lights).map((polygon) => polygon.map(([x, y]) => projectPoint(pose, [x, y, 0])))
    return polygons.length === 0 ? null : { zoneId: outlineZone.id, polygons, widthPx: behaviour.outlinePx }
  }, [pose, outlineZone, home, lights, behaviour.outlinePx])
  // §7.6 compose: "Rooms outside the chosen zone dimmed", and the zone's own labels in `text`: its rooms',
  // its own, and those of the running sub-zones inside it.
  const composeShape = useMemo((): ComposeShape | null => {
    if (pose === null || composeZone === undefined) return null
    const lit = zoneRooms(home, composeZone, lights)
    const dims = home.rooms.filter((room) => !lit.has(room.id)).map((room) => room.polygon.map(([x, y]) => projectPoint(pose, [x, y, 0])))
    return { dims, chosen: new Set([...lit, composeZone.id, ...subZonesIn(composeZone, zones)]) }
  }, [pose, composeZone, home, lights, zones])
  // §8.1's overlays, and State-Problems' and State-Transition's tags: desktop `live` only (F3 decision 18).
  const overlaid = behaviour.overlays && behaviour.interactive
  const tags = useMemo(() => (overlaid ? zoneTags(running, bodies) : []), [overlaid, running, bodies])

  /** The pointer on the stage, in CSS px, with the room under it. */
  const under = (event: MouseEvent<HTMLElement>) => {
    const box = event.currentTarget.getBoundingClientRect()
    const [x, y] = [event.clientX - box.left, event.clientY - box.top]
    const room = pose === null ? null : pickRoom(home, pose, x, y)
    return { x, y, room: room?.hasLights ? room : null }
  }
  /** The picture's pointer, while a click on a room does something; the light under it is Live's alone. */
  const pointer = {
    onPointerMove: (event: PointerEvent<HTMLElement>) => {
      const { x, y, room } = under(event)
      // A light's tooltip is for a mouse; a touch goes to the room under it.
      setHovered(behaviour.interactive && event.pointerType === 'mouse' ? pickLight(points, x, y) : null)
      setOverRoom(room !== null)
    },
    onPointerLeave: () => {
      setHovered(null)
      setOverRoom(false)
    },
    onClick: (event: MouseEvent<HTMLElement>) => {
      const { room } = under(event)
      if (room === null) return
      if (behaviour.roomClick === 'choose' && compose !== null) compose.choose(room.id)
      else navigate(roomTo(room), { state: roomState })
    },
  }

  const light = hovered === null ? undefined : lights.find((candidate) => candidate.id === hovered)
  const body = bodies.find((candidate) => candidate.lightId === hovered)
  const state = hovered === null ? undefined : states.get(hovered)
  const previewWords =
    previewing === null || composeZone === undefined ? null : { look: previewing, zone: composeZone.name, running: looksOn(composeZone, running) }
  const zoneBox = outline === null ? null : boxOf(outline.polygons)

  return (
    <section ref={ref} aria-label={STAGE_LABEL} className="relative size-full overflow-hidden bg-bg">
      {webgl ? (
        // The picture. Greyed is the only thing a frozen stage does to it (§7.6).
        <div
          className="absolute inset-0"
          style={{ filter: behaviour.greyed ? GREYED : undefined, cursor: overRoom ? 'pointer' : undefined }}
          {...(behaviour.roomClick !== null ? pointer : {})}
        >
          {pose !== null && (
            <>
              <StageCanvas
                home={home}
                writer={writer}
                entries={entries}
                mask={mask}
                pose={pose}
                cadenceMs={behaviour.cadenceMs}
                fx={null}
              />
              <StageSvg pose={pose} marks={marks} labels={labels} sun={sunDrawn} outline={outline} compose={composeShape} />
              {focusZone !== undefined && framing !== null && (
                <div aria-hidden="true" data-vignette className="pointer-events-none absolute inset-0" style={{ background: FOCUS_VIGNETTE }} />
              )}
            </>
          )}
        </div>
      ) : (
        <NoWebGL />
      )}
      {webgl && previewWords !== null && behaviour.previewTag === 'card' && zoneBox !== null && (
        <PreviewCard {...previewWords} zoneBox={zoneBox} covered={compose?.covered === true} />
      )}
      {webgl && previewWords !== null && behaviour.previewTag === 'tag' && <PreviewTag />}
      {/* Each render's order: Main.html's tools and readout, its legend, then its zoom; Live-PutLookOn's card before the legend. */}
      {webgl && overlaid && (
        <>
          <StageTools
            mode={view.mode}
            onMode={(mode) => store({ ...stored, view: { ...view, mode } })}
            labels={stored.labels}
            onLabels={(on) => store({ ...stored, labels: on })}
          />
          <SunReadout sun={sun} />
        </>
      )}
      {webgl && behaviour.legend && <Legend />}
      {webgl && overlaid && <ViewControls view={view} onView={(next) => store({ ...stored, view: next })} />}
      {/* The rest of the interactive layer: §7.6 `live` only. */}
      {behaviour.interactive && (
        <>
          {webgl && pose !== null && tags.length > 0 && <ZoneTags tags={tags} pose={pose} />}
          {webgl && pose !== null && light !== undefined && body !== undefined && state !== undefined && (
            <LightTooltip
              light={light}
              state={state}
              text={tooltipText(light, running, zoneNames)}
              at={projectPoint(pose, anchorOf(body))}
              stage={pose}
            />
          )}
          <RoomLinks rooms={home.rooms} to={roomTo} state={roomState} />
        </>
      )}
    </section>
  )
}
