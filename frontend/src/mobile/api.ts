/**
 * Mobile API — 使用共享 createApi 工厂 + fetch 适配器
 *
 * 使用 fetch 直接调用，避免引入 Element Plus（桌面端 api/http.ts 依赖 ElMessage）。
 */
import { showToast } from './toast'
import { createApi } from '@/shared/api/createApi'
import { parseApiError } from '@/shared/api/errorParser'

const BASE = ''

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = localStorage.getItem('access_token')
  const h: Record<string, string> = { ...extra }
  if (token) h.Authorization = `Bearer ${token}`
  return h
}

async function handle(resp: Response): Promise<any> {
  if (resp.status === 401) {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    if (location.pathname !== '/m.html' || !location.hash.startsWith('#/login')) {
      location.hash = '#/login'
    }
    throw new Error('未登录')
  }
  const text = await resp.text()
  let data: any = null
  if (text) {
    try { data = JSON.parse(text) } catch { data = text }
  }
  if (!resp.ok) {
    const msg = parseApiError(data, `HTTP ${resp.status}`)
    showToast(msg)
    throw new Error(msg)
  }
  return data
}

// fetch → HttpClient 适配器
const fetchAdapter = {
  get: async (path: string, params?: Record<string, any>) => {
    let url = BASE + path
    if (params) {
      const qs = new URLSearchParams()
      for (const [k, v] of Object.entries(params)) {
        if (v != null) qs.set(k, String(v))
      }
      const qsStr = qs.toString()
      if (qsStr) url += `?${qsStr}`
    }
    const r = await fetch(url, { headers: authHeaders() })
    return handle(r)
  },
  post: async (path: string, body?: any, params?: Record<string, any>) => {
    let url = BASE + path
    if (params) {
      const qs = new URLSearchParams()
      for (const [k, v] of Object.entries(params)) {
        if (v != null) qs.set(k, String(v))
      }
      const qsStr = qs.toString()
      if (qsStr) url += `?${qsStr}`
    }
    const r = await fetch(url, {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: body == null ? undefined : JSON.stringify(body),
    })
    return handle(r)
  },
  patch: async (path: string, body?: any, params?: Record<string, any>) => {
    let url = BASE + path
    if (params) {
      const qs = new URLSearchParams()
      for (const [k, v] of Object.entries(params)) {
        if (v != null) qs.set(k, String(v))
      }
      const qsStr = qs.toString()
      if (qsStr) url += `?${qsStr}`
    }
    const r = await fetch(url, {
      method: 'PATCH',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: body == null ? undefined : JSON.stringify(body),
    })
    return handle(r)
  },
  put: async (path: string, body?: any, params?: Record<string, any>) => {
    let url = BASE + path
    if (params) {
      const qs = new URLSearchParams()
      for (const [k, v] of Object.entries(params)) {
        if (v != null) qs.set(k, String(v))
      }
      const qsStr = qs.toString()
      if (qsStr) url += `?${qsStr}`
    }
    const r = await fetch(url, {
      method: 'PUT',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: body == null ? undefined : JSON.stringify(body),
    })
    return handle(r)
  },
  del: async (path: string, params?: Record<string, any>) => {
    let url = BASE + path
    if (params) {
      const qs = new URLSearchParams()
      for (const [k, v] of Object.entries(params)) {
        if (v != null) qs.set(k, String(v))
      }
      const qsStr = qs.toString()
      if (qsStr) url += `?${qsStr}`
    }
    const r = await fetch(url, { method: 'DELETE', headers: authHeaders() })
    return handle(r)
  },
  postForm: async (path: string, fd: FormData) => {
    const r = await fetch(BASE + path, { method: 'POST', headers: authHeaders(), body: fd })
    return handle(r)
  },
  request: async (path: string, opts?: { method?: string; data?: any; params?: Record<string, any> }) => {
    const method = opts?.method || 'GET'
    let url = BASE + path
    if (opts?.params) {
      const qs = new URLSearchParams()
      for (const [k, v] of Object.entries(opts.params)) {
        if (v != null) qs.set(k, String(v))
      }
      const qsStr = qs.toString()
      if (qsStr) url += `?${qsStr}`
    }
    const headers: Record<string, string> = { ...authHeaders() }
    if (opts?.data) headers['Content-Type'] = 'application/json'
    const r = await fetch(url, { method, headers, body: opts?.data ? JSON.stringify(opts.data) : undefined })
    return handle(r)
  },
}

export const api = createApi(fetchAdapter)
