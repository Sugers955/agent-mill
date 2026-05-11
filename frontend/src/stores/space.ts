// Personal "Space" store: keeps an in-memory map of which assistant messages
// in the *currently loaded* conversation have been favorited, so star icons
// can render in O(1). The map is loaded once per conversation.
import { defineStore } from 'pinia'
import { api } from '@/api'

export const useSpace = defineStore('space', {
  state: () => ({
    // message_id (number) → favorite_id (number)
    favByMessage: {} as Record<number, number>,
  }),
  actions: {
    /** Load favorite-ids for a batch of messages in one round-trip. */
    async loadForMessages(messageIds: number[]) {
      // Reset before loading — never bleed across conversations.
      this.favByMessage = {}
      const ids = messageIds.filter((id) => Number.isFinite(id) && id > 0)
      if (!ids.length) return
      try {
        const map = await api.checkFavorites(ids)
        const next: Record<number, number> = {}
        for (const [k, v] of Object.entries(map || {})) {
          const mid = Number(k)
          if (Number.isFinite(mid)) next[mid] = v as number
        }
        this.favByMessage = next
      } catch {
        // network glitch — leave map empty; stars just won't show as filled
      }
    },

    isFavorited(messageId: number | undefined | null): boolean {
      if (!messageId) return false
      return !!this.favByMessage[messageId]
    },

    favoriteIdOf(messageId: number | undefined | null): number | null {
      if (!messageId) return null
      return this.favByMessage[messageId] ?? null
    },

    /** Optimistic add: assume success, rollback if the API fails. */
    async favorite(messageId: number, note?: string): Promise<boolean> {
      // Pre-fill with a sentinel so the star turns solid immediately.
      const prev = this.favByMessage[messageId]
      this.favByMessage[messageId] = -1  // pending
      try {
        const fav = await api.createFavorite(messageId, note)
        this.favByMessage[messageId] = fav.id
        return true
      } catch (e) {
        // rollback
        if (prev) this.favByMessage[messageId] = prev
        else delete this.favByMessage[messageId]
        throw e
      }
    },

    /** Optimistic remove. */
    async unfavorite(messageId: number): Promise<boolean> {
      const prev = this.favByMessage[messageId]
      delete this.favByMessage[messageId]
      try {
        await api.deleteFavoriteByMessage(messageId)
        return true
      } catch (e) {
        if (prev) this.favByMessage[messageId] = prev
        throw e
      }
    },

    reset() {
      this.favByMessage = {}
    },
  },
})
