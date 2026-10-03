// Copy rules, spec §10: 24 h time, BPM with one decimal. English names are spelled out rather
// than taken from Intl: en-GB abbreviates September as "Sept", and the renders say "Sep".
const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

const pad = (n: number) => String(n).padStart(2, '0')

/** "19:14" */
export function formatTime(date: Date): string {
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/** "Wed 19:14", the phone header's clock. */
export function formatDayTime(date: Date): string {
  return `${DAYS[date.getDay()]} ${formatTime(date)}`
}

/** "Wed 23 Sep · 19:14", the desktop top bar's clock. */
export function formatDayDateTime(date: Date): string {
  return `${DAYS[date.getDay()]} ${date.getDate()} ${MONTHS[date.getMonth()]} · ${formatTime(date)}`
}

/** "121.8" */
export function formatBpm(bpm: number): string {
  return bpm.toFixed(1)
}

/** "38 ms"; an estimate reads "~38 ms". */
export function formatLatency(ms: number, estimated = false): string {
  return `${estimated ? '~' : ''}${Math.round(ms)} ms`
}

/** "124.00": a deck's track BPM, as §10 writes Pro DJ Link's raw tempo. */
export function formatTrackBpm(bpm: number): string {
  return bpm.toFixed(2)
}

/** "+1.2%": a deck's pitch, always signed. */
export function formatPitch(percent: number): string {
  return `${percent >= 0 ? '+' : ''}${percent.toFixed(1)}%`
}

/** "19:14:05": the phone's "last frame" while the link is down (Phone-State-Reconnecting). */
export function formatTimeWithSeconds(date: Date): string {
  return `${formatTime(date)}:${pad(date.getSeconds())}`
}

/**
 * A duration as §10 writes it: "42 s", "9 m", "1 h 10 m", "2 h". `'min'` writes the minutes as the slow
 * note does ("for 2 min", State-Problems). Floored, and never below zero.
 */
export function formatDuration(ms: number, minutes: 'm' | 'min' = 'm'): string {
  const seconds = Math.max(0, Math.floor(ms / 1000))
  if (seconds < 60) return `${seconds} s`
  const total = Math.floor(seconds / 60)
  const [hours, rest] = [Math.floor(total / 60), total % 60]
  if (hours === 0) return `${rest} ${minutes}`
  return rest === 0 ? `${hours} h` : `${hours} h ${rest} ${minutes}`
}

/** "2.4 s left": an overlay's time (Live-Doorbell), never below zero. */
export function formatSecondsLeft(ms: number): string {
  return `${(Math.max(0, ms) / 1000).toFixed(1)} s left`
}

const DAY_MS = 86_400_000
const startOfDay = (date: Date) => new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()

/**
 * A day as Start again says it (F3 decision 35): '' for today, "yesterday", a weekday within the week
 * ("Fri"), else "16 Sep". Days are counted between midnights, so a clock change doesn't move them.
 */
export function formatDayWord(date: Date, now: Date): string {
  const days = Math.round((startOfDay(now) - startOfDay(date)) / DAY_MS)
  if (days <= 0) return ''
  if (days === 1) return 'yesterday'
  if (days < 7) return DAYS[date.getDay()]
  return `${date.getDate()} ${MONTHS[date.getMonth()]}`
}

/**
 * "yesterday 18:02 – 23:31" (State-Nothing-Running). An end on another day than the start says its own
 * day, "today" included: "yesterday 23:31 – today 07:00".
 */
export function formatSpan(start: Date, end: Date, now: Date): string {
  const at = (date: Date, word: string) => (word === '' ? formatTime(date) : `${word} ${formatTime(date)}`)
  const endWord = startOfDay(start) === startOfDay(end) ? '' : formatDayWord(end, now) || 'today'
  return `${at(start, formatDayWord(start, now))} – ${at(end, endWord)}`
}
