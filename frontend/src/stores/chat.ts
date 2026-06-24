import { defineStore } from 'pinia'
import { api } from '@/api'
import { useSpace } from './space'

export const useChat = defineStore('chat', {
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
        api.myAgents().then(r => r.items ?? r).catch(() => []),
        api.myDefaultAgent().catch(() => null),
        api.conversations().then(r => r.items ?? r).catch(() => []),
      ])
      this.agents = as
      this.defaultAgent = def
      this.convs = cs
      if (!this.currentAgent) this.currentAgent = def || (this.agents as any[])[0] || null
      this.loaded = true
    },
    selectAgent(a: any) {
      const switched = a?.id !== this.currentAgent?.id
      this.currentAgent = a
      // Switching agent → drop the active conv from local state so the welcome
      // screen for the new agent is shown. The previous conv still exists in
      // the sidebar list (and DB) and can be re-opened by clicking it.
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
      useSpace().reset()
    },
    /** "New conversation" UX action — local-only reset that surfaces the
     *  welcome screen for the current agent. We deliberately do NOT call the
     *  create-conversation API here, so users who switch agents and click
     *  around without sending anything don't accumulate empty conversations
     *  in their history. The real DB row is created lazily by `ensureConv()`
     *  on the first send. */
    async newConv() {
      this.currentConvId = null
      this.messages = []
      this.pendingFiles = []
      return null
    },
    /** Lazy creator: ensures a real DB conversation exists before the first
     *  message is sent. Returns the existing conv if one is already active. */
    async ensureConv() {
      if (this.currentConvId) {
        return this.convs.find((x) => x.id === this.currentConvId) || null
      }
      if (!this.currentAgent) return null
      const c = await api.createConversation(this.currentAgent.id)
      this.convs.unshift(c)
      this.currentConvId = c.id
      this.messages = []
      // keep pendingFiles — user may have attached files before sending
      return c
    },
    async selectConv(c: any) {
      this.currentConvId = c.id
      const a = this.agents.find((x) => x.id === c.agent_id)
      if (a) this.currentAgent = a
      const res = await api.messages(c.id)
      this.messages = res.items ?? res
      this.pendingFiles = []
      // Refresh which assistant messages are favorited so star icons render.
      const ids = this.messages
        .filter((m: any) => m.role === 'assistant' && Number.isFinite(m.id))
        .map((m: any) => m.id as number)
      useSpace().loadForMessages(ids)
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
