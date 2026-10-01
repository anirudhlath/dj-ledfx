// The stage (§7) in its `live` and `frozen` modes: the canvas, the SVG layer over it and the HTML
// overlays, all placed from one camera pose (camera.ts). React renders this when the data, the view
// or the hovered light changes; frames go from the frame store to the canvas without it (§7.5).
import { useMemo, useState, type MouseEvent, type PointerEvent } from 'react'
import { useNavigate } from 'react-router'
import type { Id, Room } from '@/api/contract'
import { useElementSize } from '@/lib/use-element-size'
import { useReducedMotion } from '@/lib/use-media-query'
import { stageBodies } from './bodies'
import { cadenceMs } from './cadence'
import { bearingDeg, FIT_VIEW, fitPose, LIVE_PADDING, projectPoint } from './camera'
import { SPEC } from './design-numbers'
import { FrameWriter, writerEntries } from './frame-writer'
import { stageLabels } from './labels'
import { anchorOf, lightMarks } from './marks'
import { Legend } from './overlays/legend'
import { LightTooltip } from './overlays/light-tooltip'
import { NoWebGL } from './overlays/no-webgl'
import { RoomLinks } from './overlays/room-links'
import { StageSvg } from './overlays/stage-svg'
import { StageTools } from './overlays/stage-tools'
import { SunReadout } from './overlays/sun-readout'
import { ViewControls } from './overlays/view-controls'
import { WRITER_COLOURS } from './palette'
import { pickLight, pickRoom, screenPoints } from './picking'
import { roomMask } from './room-mask'
import { StageCanvas } from './stage-canvas'
import { sunScene } from './sun'
import { tooltipText } from './tooltip'
import type { StageData } from './use-stage-data'
import { useStageView } from './view-memory'
import { hasWebGL2 } from './webgl'

/** §7.6 frozen: the last frame, greyed as SPEC.frozen says, with no animation. */
const FROZEN = { filter: `grayscale(${SPEC.frozen.grayscale}) brightness(${SPEC.frozen.brightness})` }

export type StageVariant = 'desktop' | 'phone'

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
  const phone = variant === 'phone'
  const [ref, size] = useElementSize<HTMLElement>()
  const [stored, store] = useStageView(route)
  const view = phone ? FIT_VIEW : stored.view
  const reducedMotion = useReducedMotion()
  const [webgl] = useState(hasWebGL2)
  const [hovered, setHovered] = useState<Id | null>(null)
  const navigate = useNavigate()

  const pose = useMemo(() => fitPose(home.outline, size, LIVE_PADDING, view), [home.outline, size, view])
  const bodies = useMemo(() => stageBodies(lights), [lights])
  const writer = useMemo(() => new FrameWriter(writerEntries(bodies, lights, states, home.rooms), WRITER_COLOURS), [bodies, lights, states, home.rooms])
  const mask = useMemo(() => roomMask(home.rooms), [home.rooms])
  const marks = useMemo(() => (pose === null ? [] : lightMarks(pose, bodies, states)), [pose, bodies, states])
  const labels = useMemo(() => (phone || !stored.labels ? null : stageLabels(home, running, lights)), [phone, stored.labels, home, running, lights])
  const sunDrawn = useMemo(() => sunScene(home, sun), [home, sun])
  const points = useMemo(() => (pose === null ? [] : screenPoints(pose, bodies)), [pose, bodies])

  /** The pointer on the stage, in CSS px, with the room under it. */
  const under = (event: MouseEvent<HTMLElement>) => {
    const box = event.currentTarget.getBoundingClientRect()
    const [x, y] = [event.clientX - box.left, event.clientY - box.top]
    const room = pose === null ? null : pickRoom(home, pose, x, y)
    return { x, y, room: room?.hasLights ? room : null }
  }
  const onPointerMove = (event: PointerEvent<HTMLElement>) => {
    const { x, y, room } = under(event)
    // A light's tooltip is for a mouse; a touch goes to the room under it.
    setHovered(event.pointerType === 'mouse' ? pickLight(points, x, y) : null)
    event.currentTarget.style.cursor = room !== null && !frozen ? 'pointer' : ''
  }
  const onClick = (event: MouseEvent<HTMLElement>) => {
    const { room } = under(event)
    if (room !== null && !frozen) navigate(roomTo(room))
  }

  const light = hovered === null ? undefined : lights.find((candidate) => candidate.id === hovered)
  const body = bodies.find((candidate) => candidate.lightId === hovered)
  const state = hovered === null ? undefined : states.get(hovered)

  return (
    <section ref={ref} aria-label="Home, live" className="relative size-full overflow-hidden bg-bg">
      {webgl ? (
        <>
          {/* The picture: the pointer here picks lights and rooms; the overlays beside it keep their own clicks. */}
          <div
            className="absolute inset-0"
            style={frozen ? FROZEN : undefined}
            onPointerMove={onPointerMove}
            onPointerLeave={() => setHovered(null)}
            onClick={onClick}
          >
            {pose !== null && (
              <>
                <StageCanvas
                  home={home}
                  writer={writer}
                  mask={mask}
                  pose={pose}
                  bearing={bearingDeg(view.rotateDeg)}
                  frozen={frozen}
                  cadenceMs={cadenceMs({ phone, reducedMotion, frozen })}
                />
                <StageSvg pose={pose} marks={marks} labels={labels} sun={sunDrawn} sunLabel={!phone} />
              </>
            )}
          </div>
          {/* The phone's stage has no overlays (§8.10), and a frozen one none either (State-Reconnecting.png). */}
          {!phone && !frozen && (
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
          {pose !== null && light !== undefined && body !== undefined && state !== undefined && (
            <LightTooltip
              light={light}
              state={state}
              text={tooltipText(light, running, zoneNames)}
              at={projectPoint(pose, anchorOf(body))}
              stage={pose}
              frozen={frozen}
            />
          )}
        </>
      ) : (
        <NoWebGL />
      )}
      {!frozen && <RoomLinks rooms={home.rooms} to={roomTo} />}
    </section>
  )
}
