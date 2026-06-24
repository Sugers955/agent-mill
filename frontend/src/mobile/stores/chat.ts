import { defineStore } from 'pinia'
import { api } from '../api'

export const useMobileChat = defineStore('mobile-chat', {
  state: () => ({
    agents: [] as any[],
    defaultAgent: null as any,
    currentAgent: null as any,
    convs: [] as any[],
    currentConvId: null as number | null,
    messages: [] as any[],
    pendingFiles: [] as any[],
    loaded: false,
  }),
  actions: {
    async loadInit() {
      const [as, def, cs] = await Promise.all([
        api.myAgents().catch(() => []),
        api.myDefaultAgent().catch(() => null),
        api.conversations().catch(() => []),
      ])
      this.agents = as.items || as
      this.defaultAgent = def
      this.convs = cs.items || cs
      if (!this.currentAgent) this.currentAgent = def || (this.agents as any[])[0] || null
      this.loaded = true
    },
    selectAgent(a: any) {
      const switched = a?.id !== this.currentAgent?.id
      this.currentAgent = a
      if (switched) {
        this.currentConvId = null
        this.messages = []
        this.pendingFiles = []
      }
    },
    reset() {
      this.agents = []
      this.defaultAgent = null
      this.currentAgent = null
      this.convs = []
      this.currentConvId = null
      this.messages = []
      this.pendingFiles = []
      this.loaded = false
    },
    async newConv() {
      this.currentConvId = null
      this.messages = []
      this.pendingFiles = []
    },
    async ensureConv() {
      if (this.currentConvId) {
        return this.convs.find((x) => x.id === this.currentConvId) || null
      }
      if (!this.currentAgent) return null
      const c = await api.createConversation(this.currentAgent.id)
      this.convs.unshift(c)
      this.currentConvId = c.id
      this.messages = []
      return c
    },
    async selectConv(c: any) {
      this.currentConvId = c.id
      const a = this.agents.find((x) => x.id === c.agent_id)
      if (a) this.currentAgent = a
      this.messages = await api.messages(c.id)
      this.pendingFiles = []
    },
    async renameConv(c: any, title: string) {
      const updated = await api.renameConversation(c.id, title)
      Object.assign(c, updated)
    },
    async deleteConv(c: any) {
      await api.deleteConversation(c.id)
      this.convs = this.convs.filter((x) => x.id !== c.id)
      if (this.currentConvId === c.id) {
        this.currentConvId = null
        this.messages = []
      }
    },
  },
})
