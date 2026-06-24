// User activity tracker + idle-limit check.
//
// Strategy:
//   - On any real interaction (mouse / key / touch / scroll) we mark "now" in
//     localStorage. Writes are throttled to once per 30s to avoid hammering it.
//   - axios refresh-flow consults `isIdleTooLong()` BEFORE issuing a refresh.
//     If the user has been idle longer than the limit we treat the session as
//     expired and force a re-login.
//   - localStorage is the single source of truth across tabs.

const ACTIVITY_KEY = 'last_activity'
const THROTTLE_MS = 30 * 1000               // 30s between writes
const IDLE_LIMIT_MS = 48 * 60 * 60 * 1000   // 48h

let lastWrite = 0

export function touchActivity(): void {
  const now = Date.now()
  if (now - lastWrite < THROTTLE_MS) return
  lastWrite = now
  try { localStorage.setItem(ACTIVITY_KEY, String(now)) } catch {}
}

export function isIdleTooLong(): boolean {
  const raw = localStorage.getItem(ACTIVITY_KEY)
  if (!raw) return false
  const last = parseInt(raw, 10)
  if (!Number.isFinite(last)) return false
  return Date.now() - last > IDLE_LIMIT_MS
}

export function clearActivity(): void {
  try { localStorage.removeItem(ACTIVITY_KEY) } catch {}
  lastWrite = 0
}

// Reset the timestamp without going through the 30s throttle. Call this right
// after login so a fresh session never inherits a stale "last_activity".
export function resetActivityNow(): void {
  lastWrite = Date.now()
  try { localStorage.setItem(ACTIVITY_KEY, String(lastWrite)) } catch {}
}

let attached = false
export function initActivityTracker(): void {
  if (attached) return
  attached = true
  // Seed once so the very first refresh check has something to compare.
  resetActivityNow()
  const events = ['mousedown', 'mousemove', 'keydown', 'scroll', 'click', 'touchstart']
  for (const ev of events) {
    window.addEventListener(ev, touchActivity, { passive: true, capture: true })
  }
}
