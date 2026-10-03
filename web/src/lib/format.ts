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
