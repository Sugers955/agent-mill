import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '@/stores/auth'

const routes = [
  { path: '/login', component: () => import('@/views/Login.vue') },
  {
    path: '/',
    component: () => import('@/views/Layout.vue'),
    redirect: '/command',
    children: [
      { path: 'command', component: () => import('@/views/command/CommandCenter.vue') },
      { path: 'chat', component: () => import('@/views/chat/Chat.vue') },
      { path: 'tasks', component: () => import('@/views/tasks/Tasks.vue') },
      { path: 'tasks/:id/runs', component: () => import('@/views/tasks/TaskRuns.vue') },
      { path: 'space', component: () => import('@/views/space/Space.vue') },
      { path: 'admin/users', meta: { manage: true }, component: () => import('@/views/admin/Users.vue') },
      { path: 'admin/roles', meta: { manage: true }, component: () => import('@/views/admin/Roles.vue') },
      { path: 'admin/departments', meta: { manage: true }, component: () => import('@/views/admin/Departments.vue') },
      { path: 'admin/models', meta: { manage: true }, component: () => import('@/views/admin/Models.vue') },
      { path: 'admin/mcp', meta: { manage: true }, component: () => import('@/views/admin/MCP.vue') },
      { path: 'admin/skills', meta: { manage: true }, component: () => import('@/views/admin/Skills.vue') },
      { path: 'admin/agents', meta: { manage: true }, component: () => import('@/views/admin/Agents.vue') },
      { path: 'admin/packs', meta: { manage: true }, component: () => import('@/views/admin/Packs.vue') },
      { path: 'admin/approvals', meta: { manage: true }, component: () => import('@/views/admin/Approvals.vue') },
      { path: 'admin/logs', meta: { manage: true }, component: () => import('@/views/admin/Logs.vue') },
      { path: 'admin/dashboard', meta: { manage: true }, component: () => import('@/views/admin/Dashboard.vue') },
      { path: 'admin/quotas', meta: { manage: true }, component: () => import('@/views/admin/Quotas.vue') },
      { path: 'admin/memories', meta: { manage: true }, component: () => import('@/views/admin/Memories.vue') },
      { path: 'admin/knowledge', meta: { manage: true }, component: () => import('@/views/admin/KnowledgeBases.vue') },
      { path: 'admin/knowledge/:id', meta: { manage: true }, component: () => import('@/views/admin/KnowledgeBaseDetail.vue') },
      { path: 'admin/templates', meta: { manage: true }, component: () => import('@/views/admin/AgentTemplates.vue') },
      { path: 'admin/workflows', meta: { manage: true }, component: () => import('@/views/admin/WorkflowList.vue') },
      { path: 'admin/workflows/:id', meta: { manage: true }, component: () => import('@/views/admin/WorkflowEditor.vue') },
      { path: 'operator', meta: { manage: true }, component: () => import('@/views/admin/Dashboard.vue') },
    ],
  },
]

// 生产环境使用 /agent-mill/ 作为 base
const base = import.meta.env.PROD ? '/agent-mill/' : '/'
const router = createRouter({ history: createWebHistory(base), routes })

router.beforeEach(async (to) => {
  if (to.path === '/login' || to.path === '/agent-mill/login') return true
  const auth = useAuth()
  const token = localStorage.getItem('access_token')
  if (!token) return '/login'
  if (!auth.user) {
    try { await auth.fetchMe() } catch { return '/login' }
  }
  if (to.meta.manage && !auth.canManage) return '/command'
  return true
})

export default router
