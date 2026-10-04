// Preview only's one way to change (§5.6, §11.5). The top bar's switch, the phone's eye, the stage's
// label and the phone's banner all send through it. It holds the control while the change is on its way
// and says why one was refused (Review Focus 1). The switch shows the server's `transport`, never what
// was asked, so a refused change never moves it.
import { useState } from 'react'
import { failureText, setPreviewOnly } from '@/api/actions'
import { useAnnounce } from '@/design/announce'

export interface PreviewControl {
  /** A change is on its way: the control that sent it waits. */
  pending: boolean
  change: (on: boolean) => void
}

export function usePreviewControl(): PreviewControl {
  const announce = useAnnounce()
  const [pending, setPending] = useState(false)
  const change = (on: boolean) => {
    setPending(true)
    setPreviewOnly(on)
      .catch((error: unknown) => announce(failureText(`turn preview only ${on ? 'on' : 'off'}`, error)))
      .finally(() => setPending(false))
  }
  return { pending, change }
}
