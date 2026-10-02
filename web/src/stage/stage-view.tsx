// The stage (§7) in its `live` and `frozen` modes: the canvas, the SVG layer over it and the HTML
// overlays, all placed from one camera pose (camera.ts). What each mode does is decided once
// (behaviour.ts), and the stage is two parts: the picture (the canvas and the SVG layer, greyed while
// frozen) and the interactive layer (the pointer's tooltip and room click, the overlays, the rooms'
// links), which only `live` has. React renders this when the data, the view or the hovered light
// changes; frames go from the frame store to the canvas without it (§7.5).
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
import { stageLabels } from './labels'
import { anchorOf, lightMarks, statusesOf } from './marks'
import { Legend } from './overlays/legend'
import { LightTooltip } from './overlays/light-tooltip'
import { NoWebGL } from './overlays/no-webgl'
import { RoomLinks } from './overlays/room-links'
import { StageSvg } from './overlays/stage-svg'
import { StageTools } from './overlays/stage-tools'
import { SunReadout } from './overlays/sun-readout'
import { ViewControls } from './overlays/view-controls'
import { pickLight, pickRoom, screenPoints } from './picking'
import { roomMask } from './room-mask'
import { StageCanvas } from './stage-canvas'
import { STAGE_LABEL } from './stage-pending'
import { sunScene } from './sun'
import { tooltipText } from './tooltip'
import type { StageData } from './use-stage-data'
import { useStageView } from './view-memory'
import { hasWebGL2 } from './webgl'

/** §7.6 frozen: the last frame, greyed as SPEC.frozen says. */
const GREYED = `grayscale(${SPEC.frozen.grayscale}) brightness(${SPEC.frozen.brightness})`

export type { StageVariant } from './behaviour'

export interface StageViewProps {
  data: StageData
  /** The phone's stage has no labels and no overlays (§8.10). */
  variant: StageVariant
  /** Where the view is remembered (view-memory.ts). */
  route: string
  /** Where a click on a room goes: its zone's composer (§8.1). */
  roomTo: (room: Room) => string
}

export function StageView({ data, variant, route, roomTo }: StageViewProps) {
  const { home, lights, states, running, zoneNames, sun, frozen } = data
  const [ref, size] = useElementSize<HTMLElement>()
  const [stored, store] = useStageView(route)
  const reducedMotion = useReducedMotion()
  const behaviour = stageBehaviour({ mode: frozen ? 'frozen' : 'live', variant, reducedMotion, labels: stored.labels })
  // The phone's stage has no view controls, so it shows the fitted view (§8.10).
  const view = behaviour.overlays ? stored.view : FIT_VIEW
  const [webgl] = useState(hasWebGL2)
  const [hovered, setHovered] = useState<Id | null>(null)
  const [overRoom, setOverRoom] = useState(false)
  // Out of the interactive layer, the pointer picks nothing, and the link's return finds nothing picked.
  if (!behaviour.interactive && (hovered !== null || overRoom)) {
    setHovered(null)
    setOverRoom(false)
  }
  const navigate = useNavigate()

  const pose = useMemo(() => fitPose(home.outline, size, view), [home.outline, size, view])
  const bodies = useMemo(() => stageBodies(lights), [lights])
  // The engine pushes `lights` every few seconds while a look plays. The writer's arrays (and the
  // meshes over them) are made from which bodies are drawn alone, and take each push's colours in
  // place; the marks, from each light's status alone (I1).
  const entries = useMemo(() => writerEntries(bodies, lights, states, home.rooms), [bodies, lights, states, home.rooms])
  const layout = useStable(entries, sameLayout)
  const writer = useMemo(() => new FrameWriter(layout), [layout])
  const mask = useMemo(() => roomMask(home.rooms), [home.rooms])
  const statuses = useStable(useMemo(() => statusesOf(states), [states]), sameEntries)
  const marks = useMemo(() => (pose === null ? [] : lightMarks(pose, bodies, statuses)), [pose, bodies, statuses])
  const labels = useMemo(() => (behaviour.labels ? stageLabels(home, running, lights) : null), [behaviour.labels, home, running, lights])
  const sunDrawn = useMemo(() => sunScene(home, sun, behaviour.sunLabel), [home, sun, behaviour.sunLabel])
  const points = useMemo(() => (pose === null ? [] : screenPoints(pose, bodies)), [pose, bodies])

  /** The pointer on the stage, in CSS px, with the room under it. */
  const under = (event: MouseEvent<HTMLElement>) => {
    const box = event.currentTarget.getBoundingClientRect()
    const [x, y] = [event.clientX - box.left, event.clientY - box.top]
    const room = pose === null ? null : pickRoom(home, pose, x, y)
    return { x, y, room: room?.hasLights ? room : null }
  }
  /** The picture's pointer: the interactive layer's, so only while there is one. */
  const pointer = {
    onPointerMove: (event: PointerEvent<HTMLElement>) => {
      const { x, y, room } = under(event)
      // A light's tooltip is for a mouse; a touch goes to the room under it.
      setHovered(event.pointerType === 'mouse' ? pickLight(points, x, y) : null)
      setOverRoom(room !== null)
    },
    onPointerLeave: () => {
      setHovered(null)
      setOverRoom(false)
    },
    onClick: (event: MouseEvent<HTMLElement>) => {
      const { room } = under(event)
      if (room !== null) navigate(roomTo(room))
    },
  }

  const light = hovered === null ? undefined : lights.find((candidate) => candidate.id === hovered)
  const body = bodies.find((candidate) => candidate.lightId === hovered)
  const state = hovered === null ? undefined : states.get(hovered)

  return (
    <section ref={ref} aria-label={STAGE_LABEL} className="relative size-full overflow-hidden bg-bg">
      {webgl ? (
        // The picture. Greyed is the only thing a frozen stage does to it (§7.6).
        <div
          className="absolute inset-0"
          style={{ filter: behaviour.greyed ? GREYED : undefined, cursor: overRoom ? 'pointer' : undefined }}
          {...(behaviour.interactive ? pointer : {})}
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
              />
              <StageSvg pose={pose} marks={marks} labels={labels} sun={sunDrawn} />
            </>
          )}
        </div>
      ) : (
        <NoWebGL />
      )}
      {/* The interactive layer: §7.6 `live` only. */}
      {behaviour.interactive && (
        <>
          {webgl && behaviour.overlays && (
            <>
              <StageTools
                mode={view.mode}
                onMode={(mode) => store({ ...stored, view: { ...view, mode } })}
                labels={stored.labels}
                onLabels={(on) => store({ ...stored, labels: on })}
              />
              <SunReadout sun={sun} />
              <Legend />
              <ViewControls view={view} onView={(next) => store({ ...stored, view: next })} />
            </>
          )}
          {webgl && pose !== null && light !== undefined && body !== undefined && state !== undefined && (
            <LightTooltip
              light={light}
              state={state}
              text={tooltipText(light, running, zoneNames)}
              at={projectPoint(pose, anchorOf(body))}
              stage={pose}
            />
          )}
          <RoomLinks rooms={home.rooms} to={roomTo} />
        </>
      )}
    </section>
  )
}
