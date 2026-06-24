<template>
  <div class="mb-page notif-mb">
    <header class="mb-header soft">
      <button class="mb-icon-btn" @click="$router.back()" aria-label="返回">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
      </button>
      <div class="mb-header-title"><span class="name">通知</span></div>
      <button v-if="unread > 0" class="action-btn" @click="onMarkAll">全部已读</button>
      <div v-else style="width:36px"></div>
    </header>

    <div class="body">
      <div v-if="loading && !items.length" class="empty">加载中…</div>
      <div v-else-if="!items.length" class="empty">暂无通知</div>
      <div
        v-for="n in items" :key="n.id"
        :class="['notif', { unread: !n.read_at }]"
        @click="onItemClick(n)"
      >
        <div class="dot"></div>
        <div class="meta">
          <div class="t">{{ n.title }}</div>
          <div v-if="n.body" class="b">{{ n.body }}</div>
          <div class="time">{{ relTime(n.created_at) }}</div>
        </div>
      </div>
      <button v-if="total > items.length" class="load-more" @click="loadMore" :disabled="loadingMore">
        {{ loadingMore ? '加载中…' : '加载更多' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'

const router = useRouter()
const items = ref<any[]>([])
const total = ref(0)
const unread = ref(0)
const loading = ref(false)
const loadingMore = ref(false)

async function load() {
  loading.value = true
  try {
    const r = await api.notifications({ limit: 30 })
    items.value = r.items || []
    total.value = r.total || 0
    unread.value = r.unread || 0
  } catch {} finally { loading.value = false }
}
async function loadMore() {
  loadingMore.value = true
  try {
    const r = await api.notifications({ limit: 30, offset: items.value.length })
    items.value = [...items.value, ...(r.items || [])]
    total.value = r.total || items.value.length
  } finally { loadingMore.value = false }
}
async function onMarkAll() {
  await api.markAllNotificationsRead()
  await load()
}
async function onItemClick(n: any) {
  if (!n.read_at) {
    try { await api.markNotificationRead(n.id) } catch {}
    n.read_at = new Date().toISOString()
    unread.value = Math.max(0, unread.value - 1)
  }
  const d = n.detail_json || {}
  if (n.type === 'task_run' && d.task_id) {
    router.push(`/tasks/${d.task_id}`)
  }
}
function relTime(iso: string) {
  const t = new Date(iso).getTime()
  const diff = Date.now() - t
  if (diff < 60_000) return '刚刚'
  if (diff < 3600_000) return `${Math.floor(diff / 60_000)} 分钟前`
  if (diff < 86400_000) return `${Math.floor(diff / 3600_000)} 小时前`
  return new Date(iso).toLocaleString()
}

onMounted(load)
</script>

<style scoped>
.notif-mb { background: var(--m-bg); }
.mb-header.soft { background: var(--m-bg); border-bottom: none; }
.body { flex: 1; overflow: auto; padding: 4px 12px 24px; }
.empty {
  text-align: center; color: var(--m-text-tertiary);
  padding: 60px 20px; font-size: 14px;
}
.action-btn {
  height: 36px; padding: 0 12px;
  font-size: 12.5px; color: var(--m-primary); font-weight: 500;
}
.action-btn:active { background: var(--m-surface-variant); border-radius: 8px; }

.notif {
  display: flex; gap: 10px;
  background: var(--m-surface);
  border-radius: 12px;
  padding: 12px;
  margin-bottom: 8px;
  box-shadow: var(--m-shadow-1);
}
.notif:active { background: var(--m-bg-soft); }
.notif .dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: transparent; margin-top: 6px; flex-shrink: 0;
}
.notif.unread .dot { background: var(--m-primary); }
.notif .meta { flex: 1; min-width: 0; }
.notif .t { font-size: 14px; font-weight: 500; color: var(--m-text); }
.notif .b {
  font-size: 12.5px; color: var(--m-text-secondary); margin-top: 4px;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
  white-space: pre-wrap; word-break: break-word;
}
.notif .time { font-size: 11px; color: var(--m-text-tertiary); margin-top: 4px; }

.load-more {
  width: 100%; height: 36px; margin-top: 4px;
  background: transparent; color: var(--m-primary);
  font-size: 13px; font-weight: 500;
}
.load-more:disabled { color: var(--m-text-tertiary); }
</style>
