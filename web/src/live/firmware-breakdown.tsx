// State-Firmware's box under a zone's card (F3 decision 20): the lights that run their own effect, then
// those that get a streamed copy, a row each with its swatch and its effect, and an effect four or more run
// folded into one line under its own head. Draws nothing for a zone whose lights stream. Look:
// State-Firmware.html.
import { cx } from '@/design/cx'
import { firmwareGroups, firmwareWords } from '@/lights/firmware'
import { LightSwatch } from '@/lights/light-swatch'
import type { SwatchLight } from '@/zones/zone-view'

export function FirmwareBreakdown({ zoneName, lights }: { zoneName: string; lights: readonly SwatchLight[] }) {
  const groups = firmwareGroups(lights)
  if (groups.length === 0) return null
  return (
    <section aria-label={`Lights in ${zoneName}`} className="flex flex-col rounded-card border border-line px-3.5 pt-1 pb-2.5">
      {groups.map((group) => (
        <div key={group.title} className="flex flex-col">
          <div className="flex items-baseline justify-between px-0.5 pt-2.5 pb-1">
            <h3 className="text-meta font-semibold text-text-2">{group.title}</h3>
            <span className="num text-label text-text-3">{group.lights.length}</span>
          </div>
          {group.folded === null ? (
            <ul>
              {group.lights.map(({ light, state }) => (
                <li key={light.id} className="flex h-9 items-center gap-2.5 border-t border-line-soft">
                  <LightSwatch light={light} state={state} />
                  <span className="min-w-0 grow truncate text-size-control font-medium">{light.name}</span>
                  <span className={cx('shrink-0 text-meta', state.status === 'streamed-copy' ? 'text-text' : 'text-text-2')}>
                    {firmwareWords(state)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="flex items-center gap-2.5 px-0.5 pt-1 pb-2">
              {/* State-Firmware draws the folded swatches at the phone's size (§6.6). */}
              <ul className="flex flex-wrap items-center gap-2">
                {group.lights.map(({ light, state }) => (
                  <li key={light.id} className="flex">
                    <LightSwatch light={light} state={state} size="phone" />
                  </li>
                ))}
              </ul>
              <span className="text-meta text-text-3">{group.folded}</span>
            </div>
          )}
        </div>
      ))}
    </section>
  )
}
