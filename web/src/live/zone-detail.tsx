// Zone detail (§8.10, Phone-Zone): /live/zones/:zoneId on the phone (F3 decision 23). Under the focused stage,
// which LivePage draws: the look's name, its meta line (F3 decision 38), brightness, Change, Tweak and Off at
// 48 px, and the zone's lights with their live swatches and words (F3 decision 24). With nothing running there,
// it says so (F3 decision 39). While the link is down the controls are dimmed and inert, as Live's cards are.
// ZoneTitle is the header's title. Look: Phone-Zone.html.
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useParams } from 'react-router'
import type { Id, Look, RunningZone } from '@/api/contract'
import { useLive } from '@/api/live-store'
import { queries } from '@/api/queries'
import { useConnectionStatus } from '@/chrome/hooks'
import { Button, ButtonLink } from '@/design/button'
import { cx } from '@/design/cx'
import { Icon } from '@/design/icon'
import { LIVE_SPEC } from '@/design/live-numbers'
import { Slider } from '@/design/slider'
import { LightSwatch } from '@/lights/light-swatch'
import { formatList, formatTime } from '@/lib/format'
import { useNow } from '@/lib/use-now'
import type { LightState } from '@/stage/show'
import { useZoneControls } from '@/zones/use-zone-controls'
import { useZoneWorld } from '@/zones/use-zone-world'
import { ZoneNoteText } from '@/zones/zone-card'
import { zoneView, type InputChip, type SwatchLight, type ZoneView } from '@/zones/zone-view'
import { ReconnectingCard } from './reconnecting'

/** Phone-Zone's 48 px buttons carry body-size text and 8 px padding. cx doesn't merge classes, so `!` beats lg's. */
const TALL = 'px-2! text-body!'

/** The header's title: the zone's name, or its id until REST has it (Review Focus 4). */
export function ZoneTitle() {
  const { zoneId = '' } = useParams()
  const zones = useQuery(queries.zones()).data
  return zones?.find((zone) => zone.id === zoneId)?.name ?? zoneId
}

export function ZoneDetail({ zoneId }: { zoneId: Id }) {
  const world = useZoneWorld()
  const zones = useLive((state) => state.running?.zones ?? null)
  const now = useNow()
  const running = zones?.find((zone) => zone.zoneId === zoneId)
  return (
    <div className="flex flex-col gap-3.5 px-4 pt-2 pb-4">
      <ReconnectingCard variant="phone" />
      {running !== undefined ? (
        <RunningDetail running={running} view={zoneView(running, world, now, true)} look={world.looks.get(running.lookId)} />
      ) : (
        // Nothing until the server has said what runs.
        zones !== null && <NotRunning zoneId={zoneId} name={world.zones.get(zoneId)?.name ?? zoneId} />
      )}
    </div>
  )
}

function RunningDetail({ running, view, look }: { running: RunningZone; view: ZoneView; look: Look | undefined }) {
  const { brightness, busy, off, restart } = useZoneControls(running, view.name, view.lookName)
  const frozen = useConnectionStatus() === 'reconnecting'
  const still = frozen ? { inert: true, style: { opacity: LIVE_SPEC.frozenCardsOpacity } } : {}
  return (
    <div className="flex flex-col gap-3.5" {...still}>
      <div className="flex flex-col gap-1.5">
        <h2 className="font-serif text-display-lg leading-none">{view.lookName}</h2>
        <p className="text-data text-text-3">{metaLine(view, look)}</p>
        {view.notes.map((note, index) => (
          <ZoneNoteText key={index} note={note} className="leading-[1.4]" />
        ))}
      </div>
      {running.state === 'crashed' ? (
        <Button size="lg" icon="refresh" disabled={busy} onClick={restart} className="w-full">
          Restart
        </Button>
      ) : (
        <div className="flex items-center gap-3">
          <Icon name="sun" size={18} className="shrink-0 text-text-3" />
          <Slider
            label={`Brightness for ${view.name}`}
            value={Math.round(brightness.value * 100)}
            onValueChange={(percent) => brightness.change(percent / 100)}
            format={(percent) => `${percent}%`}
            className="h-11 flex-1"
          />
        </div>
      )}
      <div className="grid grid-cols-3 gap-2">
        <ButtonLink size="lg" icon="looks" to={`/live/put?zone=${encodeURIComponent(running.zoneId)}`} className={TALL}>
          Change
        </ButtonLink>
        <ButtonLink size="lg" icon="sliders" to={`/looks/${encodeURIComponent(running.lookId)}`} className={TALL}>
          Tweak
        </ButtonLink>
        <Button variant="outline" size="lg" icon="power" aria-label={`Turn off ${view.name}`} disabled={busy} onClick={off} className={TALL}>
          Off
        </Button>
      </div>
      {view.lights.length > 0 && (
        <section aria-labelledby="zone-lights" className="flex flex-col">
          <h3 id="zone-lights" className="label-caps pb-1.5">
            Lights · live
          </h3>
          <ul className="flex flex-col">
            {view.lights.map(({ light, state }) => (
              <LightRow key={light.id} light={light} state={state} />
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

/** F3 decision 39: a zone with no look of its own. */
function NotRunning({ zoneId, name }: { zoneId: Id; name: string }) {
  return (
    <div className="flex flex-col gap-3">
      <h2 className="font-serif text-[32px] leading-none">Nothing running</h2>
      <p className="text-size-control leading-[1.45] text-text-2">{name} has no look of its own.</p>
      <ButtonLink variant="primary" size="cta" icon="plus" to={`/live/put?zone=${encodeURIComponent(zoneId)}`}>
        Put a look on
      </ButtonLink>
    </div>
  )
}

/**
 * F3 decision 38, Phone-Zone's "Ambient · no input · since 19:05 · 11 lights": the look's category as §8.2's
 * chips write it, its inputs, the compact card's since and the card's context line.
 */
function metaLine(view: ZoneView, look: Look | undefined): string {
  const parts = [look === undefined ? null : look.category.charAt(0).toUpperCase() + look.category.slice(1), inputWords(view.inputs), view.since, view.context]
  return parts.filter((part) => part !== null).join(' · ')
}

/** "no input", or the look's inputs but Tempo, whose beat the context line names (F3 decision 10); null when REST doesn't know the look. */
function inputWords(inputs: readonly InputChip[] | null): string | null {
  if (inputs === null) return null
  if (inputs.length === 0) return 'no input'
  const named = inputs.filter((input) => input.kind !== 'tempo').map((input) => input.label)
  return named.length === 0 ? null : formatList(named)
}

function LightRow({ light, state }: SwatchLight) {
  // The swatch writer writes "glowing" or "waiting" into this element (F3 decision 24).
  const [words, setWords] = useState<HTMLSpanElement | null>(null)
  const away = state.status === 'offline' || state.status === 'switched-off'
  return (
    <li className="flex h-11 items-center gap-3 border-t border-line-soft">
      <LightSwatch light={light} state={state} size="table" words={words} />
      <span className={cx('min-w-0 grow truncate text-body font-medium', away ? 'text-text-3' : 'text-text')}>{light.name}</span>
      <StateWords state={state} live={setWords} />
    </li>
  )
}

/** F3 decision 24's words. A streaming or idle light's come from its frames, through `live`. */
function StateWords({ state, live }: { state: LightState; live: (element: HTMLSpanElement | null) => void }) {
  switch (state.status) {
    case 'offline':
      return (
        <span className="inline-flex shrink-0 items-center gap-1.75 text-data font-semibold text-signal">
          <span aria-hidden="true" className="box-border size-2 rounded-full border-dashed border-signal" style={{ borderWidth: LIVE_SPEC.swatch.offlinePx }} />
          {`Offline since ${formatTime(new Date(state.since))}`}
        </span>
      )
    case 'switched-off':
      return (
        <span className="inline-flex shrink-0 items-center gap-1.75 text-data text-text-3">
          <Icon name="power" size={13} />
          Switched off elsewhere · rejoins
        </span>
      )
    case 'own-effect':
      return <span className="shrink-0 text-meta text-text-3">{state.ownEffect === null ? 'Own effect' : `Own effect · ${state.ownEffect}`}</span>
    case 'streamed-copy':
      return <span className="shrink-0 text-meta text-text-3">Streamed copy</span>
    case 'reconnecting':
      return <span className="shrink-0 text-meta text-text-3">Reconnecting</span>
    default:
      // Phone-Zone.html sets "waiting" and "glowing" in mono.
      return <span ref={live} className="num shrink-0 text-meta text-text-3" />
  }
}
