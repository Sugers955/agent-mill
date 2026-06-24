import { defineStore } from 'pinia'
import { api } from '@/api'
import { useChat } from './chat'
import { clearActivity, resetActivityNow } from '@/lib/activity'

export const useAuth = defineStore('auth', {
  state: () => ({ user: null as any | null }),
  getters: {
    isAdmin: (s) => s.user?.role?.code === 'admin',
    isOperator: (s) => s.user?.role?.code === 'operator',
    canManage: (s) => ['admin', 'operator'].includes(s.user?.role?.code),
  },
  actions: {
    async login(username: string, password: string) {
      // 清除旧 token，避免旧会话干扰新登录
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      const res = await api.login(username, password)
      localStorage.setItem('access_token', res.access_token)
      localStorage.setItem('refresh_token', res.refresh_token)
      resetActivityNow()
      useChat().reset()
      await this.fetchMe()
    },
    async fetchMe() {
      this.user = await api.me()
    },
    logout() {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      clearActivity()
      this.user = null
      useChat().reset()
    },
  },
})
