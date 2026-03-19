import { useEffect, useRef, useState } from "react"
import { wsClient } from "@/lib/ws-client"
import type { BeatState } from "@/lib/types"

const INITIAL: BeatState = {
  bpm: 0,
  beatPhase: 0,
  barPhase: 0,
  isPlaying: false,
  beatPos: 1,
  pitchPercent: null,
  deckNumber: null,
  deckName: null,
}

export function useBeat(): BeatState {
  const [state, setState] = useState<BeatState>(INITIAL)
  const lastServerUpdate = useRef(0)
  const lastInterpTime = useRef(0)
  const stateRef = useRef(state)
  stateRef.current = state

  useEffect(() => {
    const unsub = wsClient.on("beat", (msg) => {
      const now = performance.now()
      lastServerUpdate.current = now
      lastInterpTime.current = now
      setState({
        bpm: (msg.bpm as number) || 0,
        beatPhase: (msg.beat_phase as number) || 0,
        barPhase: (msg.bar_phase as number) || 0,
        isPlaying: (msg.is_playing as boolean) || false,
        beatPos: (msg.beat_pos as number) || 1,
        pitchPercent: (msg.pitch_percent as number) ?? null,
        deckNumber: (msg.deck_number as number) ?? null,
        deckName: (msg.deck_name as string) ?? null,
      })
    })

    // Client-side phase interpolation between server updates
    let rafId: number
    const interpolate = () => {
      const s = stateRef.current
      const now = performance.now()
      if (s.isPlaying && s.bpm > 0 && lastInterpTime.current > 0) {
        const elapsed = (now - lastInterpTime.current) / 1000
        const beatsPerSec = s.bpm / 60
        const phaseDelta = (elapsed * beatsPerSec) % 1
        lastInterpTime.current = now
        setState((prev) => ({
          ...prev,
          beatPhase: (prev.beatPhase + phaseDelta) % 1,
          barPhase: (prev.barPhase + phaseDelta / 4) % 1,
        }))
      }
      rafId = requestAnimationFrame(interpolate)
    }
    rafId = requestAnimationFrame(interpolate)

    return () => {
      unsub()
      cancelAnimationFrame(rafId)
    }
  }, [])

  return state
}
