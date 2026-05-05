import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '@/stores/auth'

const routes = [
  { path: '/login', component: () => import('@/views/Login.vue') },
  {
    path: '/',
    component: () => import('@/views/Layout.vue'),
    redirect: '/chat',
    children: [
      { path: 'chat', component: () => import('@/views/chat/Chat.vue') },
      { path: 'admin/users', meta: { manage: true }, component: () => import('@/views/admin/Users.vue') },
      { path: 'admin/roles', meta: { manage: true }, component: () => import('@/views/admin/Roles.vue') },
      { path: 'admin/departments', meta: { manage: true }, component: () => import('@/views/admin/Departments.vue') },
      { path: 'admin/models', meta: { manage: true }, component: () => import('@/views/admin/Models.vue') },
      { path: 'admin/mcp', meta: { manage: true }, component: () => import('@/views/admin/MCP.vue') },
      { path: 'admin/skills', meta: { manage: true }, component: () => import('@/views/admin/Skills.vue') },
      { path: 'admin/agents', meta: { manage: true }, component: () => import('@/views/admin/Agents.vue') },
      { path: 'admin/logs', meta: { manage: true }, component: () => import('@/views/admin/Logs.vue') },
    ],
  },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to) => {
  if (to.path === '/login') return true
  const auth = useAuth()
  const token = localStorage.getItem('access_token')
  if (!token) return '/login'
  if (!auth.user) {
    try { await auth.fetchMe() } catch { return '/login' }
  }
  if (to.meta.manage && !auth.canManage) return '/chat'
  return true
})

export default router
