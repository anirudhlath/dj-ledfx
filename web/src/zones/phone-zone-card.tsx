// Phone-Live's zone card: the zone, the inputs' icons and since when, the look's name, the swatches, the
// state's note and the short lights note, and brightness with Off at the touch size. Its top half links to
// the zone's detail (§8.10: "tap → zone detail"). It takes the compact view (since without the duration;
// no long notes) and the desktop card's controls. Look: Phone-Live.html's articles.
import { Link } from 'react-router'
import type { RunningZone } from '@/api/contract'
import { Button, ButtonLink } from '@/design/button'
import { cx } from '@/design/cx'
import { Icon } from '@/design/icon'
import { Slider } from '@/design/slider'
import { LightSwatch } from '@/lights/light-swatch'
import { useZoneControls } from './use-zone-controls'
import { ZoneNoteText } from './zone-card'
import { shortLightsNote, type ZoneView } from './zone-view'

export function PhoneZoneCard({ running, view }: { running: RunningZone; view: ZoneView }) {
  const { brightness, busy, off, restart } = useZoneControls(running, view.name, view.lookName)
  const crashed = running.state === 'crashed'
  const short = shortLightsNote(view.lights)
  const notes = short === null ? view.notes : [...view.notes, short]
  const offButton = (
    <Button variant="outline" size="sm" icon="power" aria-label={`Turn off ${view.name}`} disabled={busy} onClick={off}>
      Off
    </Button>
  )
  return (
    <article
      aria-label={`${view.name} — ${view.lookName}`}
      data-zone={running.zoneId}
      className={cx('flex flex-col gap-2 rounded-panel border bg-raised px-3.5 py-3', crashed ? 'border-signal-line' : 'border-line')}
    >
      <Link to={`/live/zones/${encodeURIComponent(running.zoneId)}`} className="flex flex-col gap-1.5">
        <span className="flex items-center justify-between gap-2">
          <span className="truncate text-meta font-semibold text-text-2">{view.name}</span>
          <span className="inline-flex shrink-0 items-center gap-1.5 text-[11.5px] text-text-3">
            {view.inputs?.map((input) => (
              <Icon key={input.kind} name={input.icon} size={14} className={input.waiting ? 'text-signal' : undefined} />
            ))}
            {view.since}
            <Icon name="right" size={14} />
          </span>
        </span>
        <span className="font-serif text-display-sm">{view.lookName}</span>
      </Link>
      {view.lights.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          {view.lights.map(({ light, state }) => (
            <LightSwatch key={light.id} light={light} state={state} size="phone" />
          ))}
        </div>
      )}
      {notes.map((note, index) => (
        <ZoneNoteText key={index} note={note} className="leading-[1.4]" />
      ))}
      {crashed ? (
        <div className="flex gap-2">
          <Button size="sm" icon="refresh" disabled={busy} onClick={restart}>
            Restart
          </Button>
          <ButtonLink variant="ghost" size="sm" to={`/looks/${encodeURIComponent(running.lookId)}`}>
            Details
          </ButtonLink>
          <div className="grow" />
          {offButton}
        </div>
      ) : (
        <div className="flex items-center gap-3">
          <Slider
            label={`Brightness for ${view.name}`}
            value={Math.round(brightness.value * 100)}
            onValueChange={(percent) => brightness.change(percent / 100)}
            format={(percent) => `${percent}%`}
            className="flex-1"
          />
          {offButton}
        </div>
      )}
    </article>
  )
}
