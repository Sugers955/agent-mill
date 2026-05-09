import http from './http'

export const api = {
  // auth
  login: (username: string, password: string) =>
    http.post('/api/auth/login', { username, password }).then((r) => r.data),
  me: () => http.get('/api/auth/me').then((r) => r.data),
  changePassword: (old_password: string, new_password: string) =>
    http.post('/api/auth/change-password', { old_password, new_password }).then((r) => r.data),

  // chat
  myAgents: () => http.get('/api/agents').then((r) => r.data),
  myDefaultAgent: () => http.get('/api/agents/default').then((r) => r.data),
  agentCapabilities: (agent_id: number) =>
    http.get(`/api/agents/${agent_id}/capabilities`).then((r) => r.data),
  agentMcpTools: (agent_id: number, mcp_id: number) =>
    http.get(`/api/agents/${agent_id}/mcps/${mcp_id}/tools`).then((r) => r.data),
  conversations: () => http.get('/api/conversations').then((r) => r.data),
  createConversation: (agent_id?: number, title?: string) =>
    http.post('/api/conversations', { agent_id, title }).then((r) => r.data),
  renameConversation: (id: number, title: string) =>
    http.patch(`/api/conversations/${id}`, { title }).then((r) => r.data),
  deleteConversation: (id: number) =>
    http.delete(`/api/conversations/${id}`).then((r) => r.data),
  messages: (cid: number) =>
    http.get(`/api/conversations/${cid}/messages`).then((r) => r.data),

  uploadFile: (file: File, conversation_id?: number) => {
    const fd = new FormData()
    fd.append('file', file)
    if (conversation_id) fd.append('conversation_id', String(conversation_id))
    return http.post('/api/files/upload', fd).then((r) => r.data)
  },
  getFile: (id: number) => http.get(`/api/files/${id}`).then((r) => r.data),
  reparseFile: (id: number) => http.post(`/api/files/${id}/reparse`).then((r) => r.data),
  deleteFile: (id: number) => http.delete(`/api/files/${id}`).then((r) => r.data),

  // admin
  roles: () => http.get('/api/admin/roles').then((r) => r.data),
  createRole: (p: any) => http.post('/api/admin/roles', p).then((r) => r.data),
  updateRole: (id: number, p: any) => http.patch(`/api/admin/roles/${id}`, p).then((r) => r.data),
  deleteRole: (id: number) => http.delete(`/api/admin/roles/${id}`).then((r) => r.data),

  users: (params: { q?: string; role_id?: number; department_id?: number; limit?: number; offset?: number } = {}) =>
    http.get('/api/admin/users', { params: { limit: 20, offset: 0, ...params } }).then((r) => r.data),
  createUser: (p: any) => http.post('/api/admin/users', p).then((r) => r.data),
  updateUser: (id: number, p: any) => http.patch(`/api/admin/users/${id}`, p).then((r) => r.data),
  deleteUser: (id: number) => http.delete(`/api/admin/users/${id}`).then((r) => r.data),

  departments: (q?: string) =>
    http.get('/api/admin/departments', { params: q ? { q } : {} }).then((r) => r.data),
  departmentTree: () => http.get('/api/admin/departments/tree').then((r) => r.data),
  createDepartment: (p: any) => http.post('/api/admin/departments', p).then((r) => r.data),
  updateDepartment: (id: number, p: any) => http.patch(`/api/admin/departments/${id}`, p).then((r) => r.data),
  deleteDepartment: (id: number, force = false) =>
    http.delete(`/api/admin/departments/${id}`, { params: { force } }).then((r) => r.data),

  models: () => http.get('/api/admin/models').then((r) => r.data),
  createModel: (p: any) => http.post('/api/admin/models', p).then((r) => r.data),
  updateModel: (id: number, p: any) => http.patch(`/api/admin/models/${id}`, p).then((r) => r.data),
  deleteModel: (id: number) => http.delete(`/api/admin/models/${id}`).then((r) => r.data),
  testModel: (id: number) => http.post(`/api/admin/models/${id}/test`).then((r) => r.data),

  mcps: () => http.get('/api/admin/mcp').then((r) => r.data),
  createMcp: (p: any) => http.post('/api/admin/mcp', p).then((r) => r.data),
  updateMcp: (id: number, p: any) => http.patch(`/api/admin/mcp/${id}`, p).then((r) => r.data),
  deleteMcp: (id: number) => http.delete(`/api/admin/mcp/${id}`).then((r) => r.data),
  pingMcp: (id: number) => http.post(`/api/admin/mcp/${id}/ping`).then((r) => r.data),
  mcpTools: (id: number) => http.get(`/api/admin/mcp/${id}/tools`).then((r) => r.data),

  skills: () => http.get('/api/admin/skills').then((r) => r.data),
  createSkill: (p: any) => http.post('/api/admin/skills', p).then((r) => r.data),
  updateSkill: (id: number, p: any) => http.patch(`/api/admin/skills/${id}`, p).then((r) => r.data),
  deleteSkill: (id: number) => http.delete(`/api/admin/skills/${id}`).then((r) => r.data),
  uploadSkill: (file: File, code: string, name: string, description: string, force = false) => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('code', code)
    fd.append('name', name)
    fd.append('description', description || '')
    if (force) fd.append('force', 'true')
    return http.post('/api/admin/skills/upload', fd).then((r) => r.data)
  },
  skillFiles: (id: number) => http.get(`/api/admin/skills/${id}/files`).then((r) => r.data),
  skillFile: (id: number, path: string) =>
    http.get(`/api/admin/skills/${id}/file`, { params: { path } }).then((r) => r.data),
  saveSkillFile: (id: number, path: string, content: string) =>
    http.put(`/api/admin/skills/${id}/file`, { path, content }).then((r) => r.data),

  packs: () => http.get('/api/admin/packs').then((r) => r.data),
  createPack: (p: any) => http.post('/api/admin/packs', p).then((r) => r.data),
  updatePack: (id: number, p: any) => http.patch(`/api/admin/packs/${id}`, p).then((r) => r.data),
  deletePack: (id: number) => http.delete(`/api/admin/packs/${id}`).then((r) => r.data),
  approvals: (params: { status?: string; limit?: number; offset?: number } = {}) =>
    http.get('/api/admin/approvals', { params: { limit: 50, offset: 0, ...params } }).then((r) => r.data),
  decideApproval: (id: number, payload: { decision: 'approved' | 'rejected'; reason?: string | null }) =>
    http.post(`/api/admin/approvals/${id}/decision`, payload).then((r) => r.data),
  agents: () => http.get('/api/admin/agents').then((r) => r.data),
  agent: (id: number) => http.get(`/api/admin/agents/${id}`).then((r) => r.data),
  createAgent: (p: any) => http.post('/api/admin/agents', p).then((r) => r.data),
  updateAgent: (id: number, p: any) => http.patch(`/api/admin/agents/${id}`, p).then((r) => r.data),
  deleteAgent: (id: number) => http.delete(`/api/admin/agents/${id}`).then((r) => r.data),

  callLogs: (params: { limit?: number; offset?: number; user_id?: number; agent_id?: number } = {}) =>
    http.get('/api/admin/logs/calls', { params: { limit: 20, offset: 0, ...params } }).then((r) => r.data),
  auditLogs: (params: { limit?: number; offset?: number; user_id?: number } = {}) =>
    http.get('/api/admin/logs/audit', { params: { limit: 20, offset: 0, ...params } }).then((r) => r.data),
}
