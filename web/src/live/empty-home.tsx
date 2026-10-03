// §9.4's empty homes, on Live (F3 decision 21). No lights placed: State-No-Lights-Placed's card, with
// "Place them roughly for me" and the map (Blink one is the map's, F7's). First run, no lights at all: "No
// lights yet", Find new lights, and the integrations that look. On the stage on desktop; under the phone's
// stage (Task 18). Nothing while the link is down: Reconnecting's card has the stage then.
import { useQuery } from '@tanstack/react-query'
import { useId, useState, type ReactNode } from 'react'
import { failureText, findLights, guessPlacements } from '@/api/actions'
import { queries } from '@/api/queries'
import { useConnectionStatus } from '@/chrome/hooks'
import { useAnnounce } from '@/design/announce'
import { Button, ButtonLink } from '@/design/button'
import { formatList } from '@/lib/format'
import { StageCard } from './stage-card'

type Variant = 'desktop' | 'phone'

export function EmptyHome({ variant }: { variant: Variant }) {
  const lights = useQuery(queries.lights()).data
  const frozen = useConnectionStatus() === 'reconnecting'
  if (lights === undefined || frozen) return null
  if (lights.length === 0) return <FirstRun variant={variant} />
  if (lights.every((light) => light.shape == null)) return <PlaceLights count={lights.length} variant={variant} />
  return null
}

function EmptyCard({ variant, title, children }: { variant: Variant; title: string; children: ReactNode }) {
  const id = useId()
  if (variant === 'phone') {
    return (
      <section aria-labelledby={id} className="flex flex-col gap-3 rounded-panel border border-line-strong bg-raised p-4">
        <h2 id={id} className="font-serif text-[24px] leading-[1.1]">
          {title}
        </h2>
        {children}
      </section>
    )
  }
  return (
    <StageCard labelledBy={id} className="w-105 gap-3.5 p-6">
      <h2 id={id} className="font-serif text-[34px] leading-[1.05]">
        {title}
      </h2>
      {children}
    </StageCard>
  )
}

function PlaceLights({ count, variant }: { count: number; variant: Variant }) {
  const announce = useAnnounce()
  const [busy, setBusy] = useState(false)
  const place = () => {
    setBusy(true)
    guessPlacements()
      .then(() => announce('Placed the lights at guessed spots. Confirm them on the map.'))
      .catch((error: unknown) => announce(failureText('place the lights', error)))
      .finally(() => setBusy(false))
  }
  return (
    <EmptyCard variant={variant} title={count === 1 ? 'Place your light' : `Place your ${count} lights`}>
      <p className="text-body leading-[1.5] text-text-2">
        Looks are drawn in 3D, so each light needs a spot in the home. Place them on the map, or let the app spread them around their
        rooms. Guessed spots stay marked until you confirm them.
      </p>
      <div className="flex flex-wrap gap-2.5">
        <Button variant="primary" icon="map" disabled={busy} onClick={place}>
          Place them roughly for me
        </Button>
        <ButtonLink to="/map">Open the map</ButtonLink>
      </div>
    </EmptyCard>
  )
}

function FirstRun({ variant }: { variant: Variant }) {
  const integrations = useQuery(queries.integrations()).data
  const announce = useAnnounce()
  const [busy, setBusy] = useState(false)
  const find = () => {
    setBusy(true)
    findLights()
      .then((found) => announce(found === 0 ? 'Found no new lights.' : `Found ${found} new ${found === 1 ? 'light' : 'lights'}.`))
      .catch((error: unknown) => announce(failureText('look for lights', error)))
      .finally(() => setBusy(false))
  }
  return (
    <EmptyCard variant={variant} title="No lights yet">
      {integrations !== undefined && (
        <p className="text-body leading-[1.5] text-text-2">
          {integrations.length === 0
            ? 'Every integration is off. Turn one on in Settings.'
            : `Find new lights looks for ${formatList(integrations)} lights on your network.`}
        </p>
      )}
      <div className="flex flex-wrap gap-2.5">
        <Button variant="primary" icon="search" disabled={busy} onClick={find}>
          Find new lights
        </Button>
      </div>
    </EmptyCard>
  )
}
