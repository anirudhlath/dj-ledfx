// /inputs (§4.3): on the phone it's the Tempo tab (Phone-Tempo, F3); the desktop's Inputs page is F6's.
import { useIsPhone } from '@/lib/use-media-query'
import { PhoneTempo } from '@/live/phone-tempo'
import { Placeholder } from './placeholder'

export function InputsPage() {
  return useIsPhone() ? <PhoneTempo /> : <Placeholder name="Inputs" milestone="F6" />
}
