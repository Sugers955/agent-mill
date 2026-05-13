import { createRouter, createWebHashHistory } from 'vue-router'
import { useMobileAuth } from './stores/auth'

const routes = [
  { path: '/login', component: () => import('./views/Login.vue') },
  { path: '/chat', component: () => import('./views/Chat.vue') },
  { path: '/tasks', component: () => import('./views/Tasks.vue') },
  { path: '/tasks/:id', component: () => import('./views/TaskDetail.vue') },
  { path: '/space', component: () => import('./views/Space.vue') },
  { path: '/notifications', component: () => import('./views/Notifications.vue') },
  { path: '/me', component: () => import('./views/Me.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/chat' },
]

const router = createRouter({ history: createWebHashHistory('/m.html'), routes })

router.beforeEach(async (to) => {
  if (to.path === '/login') return true
  const token = localStorage.getItem('access_token')
  if (!token) return '/login'
  const auth = useMobileAuth()
  if (!auth.user) {
    try { await auth.fetchMe() } catch { return '/login' }
  }
  return true
})

export default router
