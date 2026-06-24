/**
 * 通用 API 构造器 — 桌面端和移动端共享
 *
 * 接受 HTTP 客户端适配器，返回统一的 API 对象。
 * 各平台只需实现 HttpClient 接口，即可获得完整的 API 方法。
 */
import { EP } from './endpoints'

export interface HttpClient {
  get(path: string, params?: Record<string, any>): Promise<any>
  post(path: string, body?: any, params?: Record<string, any>): Promise<any>
  patch(path: string, body?: any, params?: Record<string, any>): Promise<any>
  put(path: string, body?: any, params?: Record<string, any>): Promise<any>
  del(path: string, params?: Record<string, any>): Promise<any>
  postForm(path: string, fd: FormData): Promise<any>
  request(path: string, opts?: { method?: string; data?: any; params?: Record<string, any>; headers?: Record<string, string> }): Promise<any>
}

export function createApi(http: HttpClient) {
  return {
    // ── auth ──────────────────────────────────────────────
    login: (username: string, password: string) =>
      http.post(EP.login, { username, password }),
    me: () => http.get(EP.me),
    changePassword: (old_password: string, new_password: string) =>
      http.post(EP.changePassword, { old_password, new_password }),
    updateEmail: (email: string | null) =>
      http.patch(EP.updateEmail, { email }),
    ssoConfig: () => http.get(EP.ssoConfig),

    // ── tasks ─────────────────────────────────────────────
    tasks: () => http.get(EP.tasks),
    task: (id: number) => http.get(EP.task(id)),
    createTask: (p: any) => http.post(EP.tasks, p),
    createBatchTasks: (tasks: Array<{ agent_id: number; name?: string; prompt_text?: string }>) =>
      http.post(EP.tasksBatch, { tasks }),
    updateTask: (id: number, p: any) => http.patch(EP.task(id), p),
    deleteTask: (id: number) => http.del(EP.task(id)),
    runTask: (id: number) => http.post(`${EP.task(id)}/run`),
    toggleTask: (id: number) => http.post(`${EP.task(id)}/toggle`),
    taskRuns: (id: number, params: { limit?: number; offset?: number } = {}) =>
      http.get(EP.taskRuns(id), { params: { limit: 30, offset: 0, ...params } }),
    taskRun: (rid: number) => http.get(EP.taskRun(rid)),
    cancelTaskRun: (rid: number) => http.post(EP.cancelTaskRun(rid)),

    // ── notifications ─────────────────────────────────────
    notifications: (params: { unread?: number; limit?: number; offset?: number } = {}) =>
      http.get(EP.notifications, { params: { limit: 30, offset: 0, ...params } }),
    markNotificationRead: (id: number) => http.post(EP.notificationRead(id)),
    markAllNotificationsRead: () => http.post(EP.notificationsReadAll),

    // ── agents (user-facing) ──────────────────────────────
    myAgents: () => http.get(EP.agents),
    myDefaultAgent: () => http.get(EP.agentsDefault),
    agentCapabilities: (agent_id: number) => http.get(EP.agentCapabilities(agent_id)),
    agentMcpTools: (agent_id: number, mcp_id: number) =>
      http.get(EP.agentMcpTools(agent_id, mcp_id)),

    // ── conversations ─────────────────────────────────────
    conversations: () => http.get(EP.conversations),
    searchConversations: (q: string, agent_id?: number) => {
      const params: Record<string, any> = { q }
      if (agent_id) params.agent_id = agent_id
      return http.get(EP.conversationsSearch, { params })
    },
    createConversation: (agent_id?: number, title?: string) =>
      http.post(EP.conversations, { agent_id, title }),
    renameConversation: (id: number, title: string) =>
      http.patch(EP.conversation(id), { title }),
    deleteConversation: (id: number) => http.del(EP.conversation(id)),
    branchConversation: (convId: number, messageId: number) =>
      http.post(EP.branchConversation(convId), { message_id: messageId }),
    messages: (cid: number) => http.get(EP.conversationMessages(cid)),
    exportConversationUrl: (id: number, format: string = 'markdown') =>
      EP.conversationsExport(id, format),

    // ── files ─────────────────────────────────────────────
    uploadFile: (file: File, conversation_id?: number) => {
      const fd = new FormData()
      fd.append('file', file)
      if (conversation_id) fd.append('conversation_id', String(conversation_id))
      return http.postForm(EP.filesUpload, fd)
    },
    getFile: (id: number) => http.get(EP.file(id)),
    reparseFile: (id: number) => http.post(EP.fileReparse(id)),
    deleteFile: (id: number) => http.del(EP.file(id)),

    // ── downloads ─────────────────────────────────────────
    refreshDownload: (output_path: string) =>
      http.post(EP.downloadsRefresh, null, { params: { output_path } }),

    // ── favorites (Space) ─────────────────────────────────
    favorites: (params: { q?: string; agent_id?: number; limit?: number; offset?: number } = {}) =>
      http.get(EP.favorites, { params: { limit: 20, offset: 0, ...params } }),
    createFavorite: (message_id: number, note?: string) =>
      http.post(EP.favorites, { message_id, note }),
    updateFavorite: (id: number, note: string | null) =>
      http.patch(EP.favorite(id), { note }),
    deleteFavorite: (id: number) => http.del(EP.favorite(id)),
    deleteFavoriteByMessage: (message_id: number) =>
      http.del(EP.favoriteByMessage(message_id)),
    checkFavorites: (message_ids: number[]) =>
      http.get(EP.favoritesCheck, { params: { message_ids: message_ids.join(',') } }),

    // ── admin: roles ──────────────────────────────────────
    roles: () => http.get(EP.roles),
    createRole: (p: any) => http.post(EP.roles, p),
    updateRole: (id: number, p: any) => http.patch(EP.role(id), p),
    deleteRole: (id: number) => http.del(EP.role(id)),
    getRoleAgents: (roleId: number) => http.get(EP.roleAgents(roleId)),
    updateRoleAgents: (roleId: number, agentIds: number[]) =>
      http.put(EP.roleAgents(roleId), { agent_ids: agentIds }),

    // ── admin: users ──────────────────────────────────────
    users: (params: { q?: string; role_id?: number; department_id?: number; limit?: number; offset?: number } = {}) =>
      http.get(EP.users, { params: { limit: 20, offset: 0, ...params } }),
    createUser: (p: any) => http.post(EP.users, p),
    updateUser: (id: number, p: any) => http.patch(EP.user(id), p),
    deleteUser: (id: number) => http.del(EP.user(id)),

    // ── admin: departments ────────────────────────────────
    departments: (q?: string) =>
      http.get(EP.departments, { params: q ? { q } : {} }),
    departmentTree: () => http.get(EP.departmentsTree),
    createDepartment: (p: any) => http.post(EP.departments, p),
    updateDepartment: (id: number, p: any) => http.patch(EP.department(id), p),
    deleteDepartment: (id: number, force = false) =>
      http.del(EP.department(id), { params: { force } }),

    // ── admin: models ─────────────────────────────────────
    models: () => http.get(EP.models),
    createModel: (p: any) => http.post(EP.models, p),
    updateModel: (id: number, p: any) => http.patch(EP.model(id), p),
    deleteModel: (id: number) => http.del(EP.model(id)),
    testModel: (id: number) => http.post(EP.modelTest(id)),

    // ── admin: mcp ────────────────────────────────────────
    mcps: () => http.get(EP.mcps),
    createMcp: (p: any) => http.post(EP.mcps, p),
    updateMcp: (id: number, p: any) => http.patch(EP.mcp(id), p),
    deleteMcp: (id: number) => http.del(EP.mcp(id)),
    uploadMcpIcon: (id: number, file: File) => {
      const fd = new FormData()
      fd.append('file', file)
      return http.postForm(EP.mcpIcon(id), fd)
    },
    pingMcp: (id: number) => http.post(`${EP.mcp(id)}/ping`),
    mcpTools: (id: number) => http.get(EP.mcpTools(id)),
    resummarizeMcp: (id: number) => http.post(`${EP.mcp(id)}/resummarize`),

    // ── admin: skills ─────────────────────────────────────
    skills: () => http.get(EP.skills),
    createSkill: (p: any) => http.post(EP.skills, p),
    updateSkill: (id: number, p: any) => http.patch(EP.skill(id), p),
    deleteSkill: (id: number) => http.del(EP.skill(id)),
    uploadSkillIcon: (id: number, file: File) => {
      const fd = new FormData()
      fd.append('file', file)
      return http.postForm(EP.skillIcon(id), fd)
    },
    uploadSkill: (file: File, code: string, name: string, description: string, force = false) => {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('code', code)
      fd.append('name', name)
      fd.append('description', description || '')
      if (force) fd.append('force', 'true')
      return http.postForm(EP.skillUpload, fd)
    },
    skillFiles: (id: number) => http.get(EP.skillFiles(id)),
    skillTree: (id: number) => http.get(EP.skillFiles(id)),
    skillFile: (id: number, path: string) =>
      http.get(EP.skillFile(id), { params: { path } }),
    updateSkillFile: (id: number, path: string, content: string) =>
      http.put(EP.skillFile(id), { path, content }),
    saveSkillFile: (id: number, path: string, content: string) =>
      http.put(EP.skillFile(id), { path, content }),
    skillSummary: (id: number) => http.get(EP.skillSummary(id)),
    resummarizeSkill: (id: number) => http.post(`${EP.skill(id)}/resummarize`),

    // ── admin: packs ──────────────────────────────────────
    packs: () => http.get(EP.packs),
    createPack: (p: any) => http.post(EP.packs, p),
    updatePack: (id: number, p: any) => http.patch(EP.pack(id), p),
    deletePack: (id: number) => http.del(EP.pack(id)),

    // ── admin: approvals ──────────────────────────────────
    approvals: (params: { status?: string; limit?: number; offset?: number } = {}) =>
      http.get(EP.approvals, { params: { limit: 50, offset: 0, ...params } }),
    decideApproval: (id: number, payload: { decision: 'approved' | 'rejected'; reason?: string | null }) =>
      http.post(EP.approvalDecision(id), payload),

    // ── admin: agents ─────────────────────────────────────
    agents: () => http.get(EP.adminAgents),
    agent: (id: number) => http.get(EP.adminAgent(id)),
    createAgent: (p: any) => http.post(EP.adminAgents, p),
    updateAgent: (id: number, p: any) => http.patch(EP.adminAgent(id), p),
    deleteAgent: (id: number) => http.del(EP.adminAgent(id)),
    uploadAgentIcon: (id: number, file: File) => {
      const fd = new FormData()
      fd.append('file', file)
      return http.postForm(EP.adminAgentIcon(id), fd)
    },
    polishAgentText: (p: { kind: 'description' | 'system_prompt'; text: string; agent_name?: string; model_id?: number }) =>
      http.post(EP.agentPolish, p),

    // ── admin: logs ───────────────────────────────────────
    callLogs: (params: { limit?: number; offset?: number; user_id?: number; agent_id?: number } = {}) =>
      http.get(EP.logsCalls, { params: { limit: 20, offset: 0, ...params } }),
    auditLogs: (params: { limit?: number; offset?: number; user_id?: number; action?: string; resource_type?: string } = {}) =>
      http.get(EP.logsAudit, { params: { limit: 20, offset: 0, ...params } }),
    auditUserActivity: (userId: number, days = 30) =>
      http.get(EP.auditUserActivity(userId), { params: { days } }),
    auditMyActivity: (days = 30) =>
      http.get(EP.auditMyActivity, { params: { days } }),

    // ── admin: stats ──────────────────────────────────────
    statsOverview: () => http.get(EP.statsOverview),
    statsByUser: () => http.get(EP.statsByUser),
    statsByAgent: () => http.get(EP.statsByAgent),
    statsByModel: () => http.get(EP.statsByModel),
    statsTrend: (days = 30) => http.get(EP.statsTrend, { params: { days } }),
    statsByDepartment: () => http.get(EP.statsByDepartment),
    statsAgentEffectiveness: () => http.get(EP.statsAgentEffectiveness),
    statsLatencyTrend: (days = 30) => http.get(EP.statsLatencyTrend, { params: { days } }),
    statsErrorTrend: (days = 30) => http.get(EP.statsErrorTrend, { params: { days } }),
    statsSystemHealth: () => http.get(EP.statsSystemHealth),
    statsTokenDetail: (params: any = {}) => http.get(EP.statsTokenDetail, { params: { limit: 50, offset: 0, ...params } }),
    statsTokenExport: (params: any = {}) => http.get(EP.statsTokenExport, { params }),

    // ── admin: quotas ─────────────────────────────────────
    quotas: (params: { page?: number; size?: number } = {}) =>
      http.get(EP.quotas, { params: { page: 1, size: 20, ...params } }),
    createQuota: (p: any) => http.post(EP.quotas, p),
    updateQuota: (userId: number, p: any) => http.put(EP.quota(userId), p),
    deleteQuota: (userId: number) => http.del(EP.quota(userId)),
    quotaUsage: (userId: number) => http.get(EP.quotaUsage(userId)),

    // ── admin: memories ───────────────────────────────────
    memories: (agentId: number, userId?: number) => http.get(EP.memories(agentId), userId ? { params: { user_id: userId } } : undefined),
    updateMemory: (id: number, p: any) => http.put(EP.memory(id), p),
    deleteMemory: (id: number) => http.del(EP.memory(id)),

    // ── generic request (for endpoints without dedicated methods) ──
    request: (path: string, opts?: { method?: string; data?: any; params?: Record<string, any>; headers?: Record<string, string> }) => {
      const method = (opts?.method || 'GET').toLowerCase() as 'get' | 'post' | 'put' | 'patch' | 'delete'
      if (method === 'get') return http.get(path, opts?.params)
      if (method === 'delete') return http.del(path, opts?.params)
      if (method === 'put') return http.put(path, opts?.data, opts?.params)
      if (method === 'patch') return http.patch(path, opts?.data, opts?.params)
      return http.post(path, opts?.data, opts?.params)
    },
  }
}

export type Api = ReturnType<typeof createApi>
