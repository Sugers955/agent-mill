// Mobile HTTP + API. Uses fetch directly to avoid pulling Element Plus into the
// mobile bundle (PC `api/http.ts` imports ElMessage). Mirrors `api/index.ts`
// surface for the endpoints the mobile UI needs.
import { showToast } from './toast'

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
    let msg = `HTTP ${resp.status}`
    if (data && typeof data === 'object') {
      if (typeof data.detail === 'string') msg = data.detail
      else if (Array.isArray(data.detail)) {
        msg = data.detail.map((d: any) => d.msg || '').filter(Boolean).join('; ') || msg
      } else if (data.message) msg = data.message
    } else if (typeof data === 'string' && data) msg = data
    showToast(msg)
    throw new Error(msg)
  }
  return data
}

async function get(path: string): Promise<any> {
  const r = await fetch(BASE + path, { headers: authHeaders() })
  return handle(r)
}

async function post(path: string, body?: any): Promise<any> {
  const r = await fetch(BASE + path, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: body == null ? undefined : JSON.stringify(body),
  })
  return handle(r)
}

async function patch(path: string, body?: any): Promise<any> {
  const r = await fetch(BASE + path, {
    method: 'PATCH',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: body == null ? undefined : JSON.stringify(body),
  })
  return handle(r)
}

async function del(path: string): Promise<any> {
  const r = await fetch(BASE + path, { method: 'DELETE', headers: authHeaders() })
  return handle(r)
}

async function postForm(path: string, fd: FormData): Promise<any> {
  const r = await fetch(BASE + path, { method: 'POST', headers: authHeaders(), body: fd })
  return handle(r)
}

export const api = {
  // auth
  login: (username: string, password: string) =>
    post('/api/auth/login', { username, password }),
  me: () => get('/api/auth/me'),
  changePassword: (old_password: string, new_password: string) =>
    post('/api/auth/change-password', { old_password, new_password }),
  updateEmail: (email: string | null) => patch('/api/auth/me/email', { email }),

  // tasks
  tasks: () => get('/api/tasks'),
  task: (id: number) => get(`/api/tasks/${id}`),
  runTask: (id: number) => post(`/api/tasks/${id}/run`),
  taskRuns: (id: number, params: { limit?: number; offset?: number } = {}) => {
    const qs = new URLSearchParams()
    qs.set('limit', String(params.limit ?? 30))
    qs.set('offset', String(params.offset ?? 0))
    return get(`/api/tasks/${id}/runs?${qs.toString()}`)
  },

  // notifications
  notifications: (params: { unread?: number; limit?: number; offset?: number } = {}) => {
    const qs = new URLSearchParams()
    if (params.unread != null) qs.set('unread', String(params.unread))
    qs.set('limit', String(params.limit ?? 30))
    qs.set('offset', String(params.offset ?? 0))
    return get(`/api/notifications?${qs.toString()}`)
  },
  markNotificationRead: (id: number) => post(`/api/notifications/${id}/read`),
  markAllNotificationsRead: () => post('/api/notifications/read-all'),

  // agents
  myAgents: () => get('/api/agents'),
  myDefaultAgent: () => get('/api/agents/default'),

  // conversations
  conversations: () => get('/api/conversations'),
  createConversation: (agent_id?: number, title?: string) =>
    post('/api/conversations', { agent_id, title }),
  renameConversation: (id: number, title: string) =>
    patch(`/api/conversations/${id}`, { title }),
  deleteConversation: (id: number) => del(`/api/conversations/${id}`),
  messages: (cid: number) => get(`/api/conversations/${cid}/messages`),

  // files
  uploadFile: (file: File, conversation_id?: number) => {
    const fd = new FormData()
    fd.append('file', file)
    if (conversation_id) fd.append('conversation_id', String(conversation_id))
    return postForm('/api/files/upload', fd)
  },
  getFile: (id: number) => get(`/api/files/${id}`),
  reparseFile: (id: number) => post(`/api/files/${id}/reparse`),
  deleteFile: (id: number) => del(`/api/files/${id}`),

  // favorites (Space)
  favorites: (params: { q?: string; agent_id?: number; limit?: number; offset?: number } = {}) => {
    const qs = new URLSearchParams()
    if (params.q) qs.set('q', params.q)
    if (params.agent_id != null) qs.set('agent_id', String(params.agent_id))
    qs.set('limit', String(params.limit ?? 20))
    qs.set('offset', String(params.offset ?? 0))
    return get(`/api/favorites?${qs.toString()}`)
  },
  deleteFavorite: (id: number) => del(`/api/favorites/${id}`),
  refreshDownload: (output_path: string) => {
    const qs = new URLSearchParams({ output_path })
    return post(`/api/downloads/refresh?${qs.toString()}`)
  },
}
