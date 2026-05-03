import { defineStore } from 'pinia'
import { api } from '@/api'

export const useAuth = defineStore('auth', {
  state: () => ({ user: null as any | null }),
  getters: {
    isAdmin: (s) => s.user?.role?.code === 'admin',
    isOperator: (s) => s.user?.role?.code === 'operator',
    canManage: (s) => ['admin', 'operator'].includes(s.user?.role?.code),
  },
  actions: {
    async login(username: string, password: string) {
      const res = await api.login(username, password)
      localStorage.setItem('access_token', res.access_token)
      localStorage.setItem('refresh_token', res.refresh_token)
      await this.fetchMe()
    },
    async fetchMe() {
      this.user = await api.me()
    },
    logout() {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      this.user = null
    },
  },
})
