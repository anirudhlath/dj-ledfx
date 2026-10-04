// What a zone's controls do, wherever they're drawn: the desktop card (§6.3), the phone's card (Phone-Live)
// and Zone detail (Phone-Zone). Brightness is throttled and stops sending while the link is down (Review
// Focus 3); Off and Restart hold the controls while they're on their way; a failure is said in words
// (Review Focus 1).
import { useState } from 'react'
import { failureText, restartZone, setBrightness, turnOff } from '@/api/actions'
import type { RunningZone } from '@/api/contract'
import { useConnectionStatus } from '@/chrome/hooks'
import { useAnnounce } from '@/design/announce'
import { useThrottledValue, type Throttled } from './use-throttled-value'

export interface ZoneControls {
  brightness: Throttled
  /** Off or Restart is on its way. */
  busy: boolean
  off: () => void
  restart: () => void
}

export function useZoneControls(running: RunningZone, name: string, lookName: string): ZoneControls {
  const announce = useAnnounce()
  const linked = useConnectionStatus() !== 'reconnecting'
  const [busy, setBusy] = useState(false)
  const brightness = useThrottledValue({
    server: running.brightness,
    send: (value) => setBrightness(running.zoneId, value),
    onFail: (error) => announce(failureText(`change the brightness of ${name}`, error)),
    enabled: linked,
  })
  const act = (action: () => Promise<void>, what: string) => {
    setBusy(true)
    action()
      .catch((error: unknown) => announce(failureText(what, error)))
      .finally(() => setBusy(false))
  }
  return {
    brightness,
    busy,
    off: () => act(() => turnOff(running.zoneId), `turn off ${name}`),
    restart: () => act(() => restartZone(running.zoneId), `restart ${lookName}`),
  }
}
