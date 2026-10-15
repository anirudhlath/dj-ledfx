// The stage's part of "Effects in space" (§7.4): while `on`, the fx channel is asked for (wantFx()), and let
// go when it's off or the stage goes. Components never touch the socket (§12).
import { useEffect } from 'react'
import { wantFx } from './live'

export function useFxStream(on: boolean): void {
  useEffect(() => (on ? wantFx() : undefined), [on])
}
