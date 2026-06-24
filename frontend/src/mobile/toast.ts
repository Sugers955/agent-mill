// Lightweight toast for the mobile app. No Element Plus dependency.
let host: HTMLDivElement | null = null

function ensureHost(): HTMLDivElement {
  if (host && document.body.contains(host)) return host
  host = document.createElement('div')
  host.className = 'mb-toast-host'
  document.body.appendChild(host)
  return host
}

export function showToast(text: string, type: 'info' | 'success' | 'error' = 'info', duration = 2400) {
  if (!text) return
  const root = ensureHost()
  const el = document.createElement('div')
  el.className = `mb-toast mb-toast-${type}`
  el.textContent = text
  root.appendChild(el)
  // animate in
  requestAnimationFrame(() => el.classList.add('show'))
  setTimeout(() => {
    el.classList.remove('show')
    setTimeout(() => el.remove(), 220)
  }, duration)
}

export function toastSuccess(t: string) { showToast(t, 'success') }
export function toastError(t: string) { showToast(t, 'error') }
