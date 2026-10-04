// §6.3 ZoneRow: "collapsed one-line zone (serif 20 look name, zone name, small swatches)", as
// State-Problems draws it. It links to /live/zones/:zoneId, where the panel draws the zone as a card again
// (F3 decision 23).
import { Link } from 'react-router'
import { LightSwatch } from '@/lights/light-swatch'
import type { ZoneView } from './zone-view'

export function ZoneRow({ view, to }: { view: ZoneView; to: string }) {
  return (
    <Link
      to={to}
      aria-label={`${view.name} — ${view.lookName}`}
      data-zone={view.zoneId}
      data-shape="row"
      className="flex items-center justify-between gap-2.5 rounded-tile border border-line bg-raised px-3.5 py-2.5 hover:border-line-strong"
    >
      <span className="flex min-w-0 items-baseline gap-2">
        <span className="font-serif text-display-xs whitespace-nowrap">{view.lookName}</span>
        <span className="text-meta whitespace-nowrap text-text-3">{view.name}</span>
      </span>
      <span className="flex flex-wrap items-center gap-1.25">
        {view.lights.map(({ light, state }) => (
          <LightSwatch key={light.id} light={light} state={state} size="row" />
        ))}
      </span>
    </Link>
  )
}
