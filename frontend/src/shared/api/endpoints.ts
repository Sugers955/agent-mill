/**
 * API 端点路径定义 — 桌面端和移动端共享
 * 只定义路径，不绑定 HTTP 实现
 */
export const EP = {
  // auth
  login: '/api/auth/login',
  me: '/api/auth/me',
  changePassword: '/api/auth/change-password',
  updateEmail: '/api/auth/me/email',
  ssoConfig: '/api/auth/sso/config',

  // tasks
  tasks: '/api/tasks',
  tasksBatch: '/api/tasks/batch',
  task: (id: number) => `/api/tasks/${id}`,
  taskRuns: (id: number) => `/api/tasks/${id}/runs`,
  taskRun: (rid: number) => `/api/task-runs/${rid}`,
  cancelTaskRun: (rid: number) => `/api/task-runs/${rid}/cancel`,

  // notifications
  notifications: '/api/notifications',
  notificationRead: (id: number) => `/api/notifications/${id}/read`,
  notificationsReadAll: '/api/notifications/read-all',

  // agents
  agents: '/api/agents',
  agentsDefault: '/api/agents/default',
  agentCapabilities: (id: number) => `/api/agents/${id}/capabilities`,
  agentMcpTools: (agentId: number, mcpId: number) => `/api/agents/${agentId}/mcps/${mcpId}/tools`,

  // conversations
  conversations: '/api/conversations',
  conversationsSearch: '/api/conversations/search',
  conversation: (id: number) => `/api/conversations/${id}`,
  conversationMessages: (cid: number) => `/api/conversations/${cid}/messages`,
  conversationsExport: (id: number, format: string) => `/api/conversations/${id}/export?format=${format}`,
  branchConversation: (convId: number) => `/api/conversations/${convId}/branch`,

  // files
  filesUpload: '/api/files/upload',
  file: (id: number) => `/api/files/${id}`,
  fileReparse: (id: number) => `/api/files/${id}/reparse`,

  // downloads
  downloadsRefresh: '/api/downloads/refresh',

  // favorites
  favorites: '/api/favorites',
  favorite: (id: number) => `/api/favorites/${id}`,
  favoriteByMessage: (mid: number) => `/api/favorites/by-message/${mid}`,
  favoritesCheck: '/api/favorites/check',

  // admin - roles
  roles: '/api/admin/roles',
  role: (id: number) => `/api/admin/roles/${id}`,
  roleAgents: (id: number) => `/api/admin/roles/${id}/agents`,

  // admin - users
  users: '/api/admin/users',
  user: (id: number) => `/api/admin/users/${id}`,

  // admin - departments
  departments: '/api/admin/departments',
  departmentsTree: '/api/admin/departments/tree',
  department: (id: number) => `/api/admin/departments/${id}`,

  // admin - models
  models: '/api/admin/models',
  model: (id: number) => `/api/admin/models/${id}`,
  modelTest: (id: number) => `/api/admin/models/${id}/test`,

  // admin - mcp
  mcps: '/api/admin/mcp',
  mcp: (id: number) => `/api/admin/mcp/${id}`,
  mcpIcon: (id: number) => `/api/admin/mcp/${id}/icon`,
  mcpTools: (id: number) => `/api/admin/mcp/${id}/tools`,

  // admin - skills
  skills: '/api/admin/skills',
  skill: (id: number) => `/api/admin/skills/${id}`,
  skillIcon: (id: number) => `/api/admin/skills/${id}/icon`,
  skillUpload: '/api/admin/skills/upload',
  skillFiles: (id: number) => `/api/admin/skills/${id}/files`,
  skillFile: (id: number) => `/api/admin/skills/${id}/file`,
  skillSummary: (id: number) => `/api/admin/skills/${id}/summary`,

  // admin - packs
  packs: '/api/admin/packs',
  pack: (id: number) => `/api/admin/packs/${id}`,

  // admin - approvals
  approvals: '/api/admin/approvals',
  approvalDecision: (id: number) => `/api/admin/approvals/${id}/decision`,

  // admin - agents (management)
  adminAgents: '/api/admin/agents',
  adminAgent: (id: number) => `/api/admin/agents/${id}`,
  adminAgentIcon: (id: number) => `/api/admin/agents/${id}/icon`,
  agentPolish: '/api/admin/agents/polish',

  // admin - logs
  logsCalls: '/api/admin/logs/calls',
  logsAudit: '/api/admin/audit/logs',
  auditUserActivity: (userId: number) => `/api/admin/audit/user/${userId}`,
  auditMyActivity: '/api/admin/audit/my-activity',

  // admin - stats
  statsOverview: '/api/admin/stats/overview',
  statsByUser: '/api/admin/stats/by-user',
  statsByAgent: '/api/admin/stats/by-agent',
  statsByModel: '/api/admin/stats/by-model',
  statsTrend: '/api/admin/stats/trend',
  statsByDepartment: '/api/admin/stats/by-department',
  statsAgentEffectiveness: '/api/admin/stats/agent-effectiveness',
  statsLatencyTrend: '/api/admin/stats/latency-trend',
  statsErrorTrend: '/api/admin/stats/error-trend',
  statsSystemHealth: '/api/admin/stats/system-health',
  statsTokenDetail: '/api/admin/stats/token-detail',
  statsTokenExport: '/api/admin/stats/token-export',

  // admin - quotas
  quotas: '/api/admin/quotas',
  quota: (userId: number) => `/api/admin/quotas/${userId}`,
  quotaUsage: (userId: number) => `/api/admin/quotas/${userId}/usage`,

  // admin - memories
  memories: (agentId: number) => `/api/memories/${agentId}`,
  memory: (id: number) => `/api/memories/${id}`,
} as const
