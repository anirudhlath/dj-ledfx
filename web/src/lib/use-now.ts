import { useEffect, useState } from 'react'

const untilNextMinute = (date: Date) => 60_000 - (date.getSeconds() * 1000 + date.getMilliseconds())

/** The current time, refreshed on each minute boundary: the chrome's clocks show minutes. */
export function useNow(): Date {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    let timer = setTimeout(function tick() {
      const current = new Date()
      setNow(current)
      timer = setTimeout(tick, untilNextMinute(current))
    }, untilNextMinute(new Date()))
    return () => clearTimeout(timer)
  }, [])
  return now
}
