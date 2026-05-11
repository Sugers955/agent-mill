import axios from 'axios'
import { ElMessage } from 'element-plus'
import { isIdleTooLong, clearActivity } from '@/lib/activity'

const http = axios.create({ baseURL: '/', timeout: 30000 })

http.interceptors.request.use((cfg) => {
  const token = localStorage.getItem('access_token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

// In-flight refresh promise — when many requests 401 at the same time, we only
// want to hit /api/auth/refresh ONCE and let everyone reuse the result.
let refreshPromise: Promise<string> | null = null

async function refreshAccessToken(): Promise<string> {
  if (refreshPromise) return refreshPromise
  refreshPromise = (async () => {
    const refresh = localStorage.getItem('refresh_token')
    if (!refresh) throw new Error('no refresh token')
    // Use a bare axios call so we don't reenter our own interceptor.
    const r = await axios.post('/api/auth/refresh', { refresh_token: refresh })
    const access = r.data?.access_token as string
    const newRefresh = r.data?.refresh_token as string
    if (!access) throw new Error('refresh returned no access_token')
    localStorage.setItem('access_token', access)
    if (newRefresh) localStorage.setItem('refresh_token', newRefresh)
    return access
  })()
  refreshPromise.finally(() => {
    // Allow the next 401 burst to trigger a fresh refresh.
    refreshPromise = null
  })
  return refreshPromise
}

function forceLogout() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  clearActivity()
  if (location.pathname !== '/login') location.href = '/login'
}

http.interceptors.response.use(
  (r) => r,
  async (err) => {
    const status = err.response?.status
    const config = err.config || {}
    const url: string = config.url || ''

    // 401 handling: try a silent refresh once, then replay the original request.
    if (status === 401 && !config._retry) {
      // Auth endpoints themselves are NOT retried — a 401 here means the
      // refresh token has truly expired or the password changed.
      const isAuthEndpoint =
        url.includes('/api/auth/login') ||
        url.includes('/api/auth/refresh')
      if (isAuthEndpoint) {
        forceLogout()
        return Promise.reject(err)
      }

      // Idle-limit policy: if the user has been away longer than the 48h limit,
      // do NOT silently re-issue tokens — force a re-login as policy demands.
      if (isIdleTooLong()) {
        forceLogout()
        return Promise.reject(err)
      }

      config._retry = true
      try {
        const newAccess = await refreshAccessToken()
        config.headers = config.headers || {}
        config.headers.Authorization = `Bearer ${newAccess}`
        return http(config)
      } catch {
        forceLogout()
        return Promise.reject(err)
      }
    }

    // Non-401 errors: keep the original UX (toast + reject).
    const data = err.response?.data
    let msg = err.message
    if (typeof data?.detail === 'string') msg = data.detail
    else if (Array.isArray(data?.detail)) {
      msg = data.detail
        .map((d: any) => `${(d.loc || []).slice(-1)[0] || ''}: ${d.msg}`)
        .join('; ')
    } else if (data?.message) msg = data.message
    if (status !== 401) ElMessage.error(msg || '请求失败')
    return Promise.reject(err)
  },
)

export default http
