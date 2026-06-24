<template>
  <el-popover
    v-model:visible="open"
    trigger="click"
    placement="bottom-end"
    :width="380"
    popper-class="notif-pop"
    @show="onOpen"
  >
    <template #reference>
      <button class="bell-btn" :class="{ active: open }" aria-label="通知">
        <el-icon :size="18"><Bell /></el-icon>
        <span v-if="unread > 0" class="badge">{{ unread > 99 ? '99+' : unread }}</span>
      </button>
    </template>

    <div class="notif-head">
      <span class="title">通知</span>
      <a v-if="unread > 0" class="action" @click="onMarkAll">全部标为已读</a>
    </div>
    <div class="notif-body">
      <div v-if="loading && !items.length" class="state">加载中…</div>
      <div v-else-if="!items.length" class="state">暂无通知</div>
      <div
        v-for="n in items" :key="n.id"
        :class="['notif-item', { unread: !n.read_at }]"
        @click="onItemClick(n)"
      >
        <div class="dot"></div>
        <div class="meta">
          <div class="t">{{ n.title }}</div>
          <div v-if="n.body" class="b">{{ n.body }}</div>
          <div class="time">{{ relTime(n.created_at) }}</div>
        </div>
      </div>
    </div>
    <div class="notif-footer">
      <el-button text size="small" @click="refresh">刷新</el-button>
    </div>
  </el-popover>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { Bell } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { api } from '@/api'

const router = useRouter()
const open = ref(false)
const items = ref<any[]>([])
const unread = ref(0)
const loading = ref(false)

let pollTimer: any = null

async function refresh() {
  loading.value = true
  try {
    const r = await api.notifications({ limit: 20 })
    items.value = r.items || []
    unread.value = r.unread || 0
  } catch {} finally { loading.value = false }
}

async function onOpen() {
  await refresh()
}

async function onMarkAll() {
  await api.markAllNotificationsRead()
  await refresh()
}

async function onItemClick(n: any) {
  if (!n.read_at) {
    try { await api.markNotificationRead(n.id) } catch {}
    n.read_at = new Date().toISOString()
    unread.value = Math.max(0, unread.value - 1)
  }
  open.value = false
  // Routing: prefer detail_json link if present
  const d = n.detail_json || {}
  if (n.type === 'task_run' && d.task_id) {
    router.push(`/tasks/${d.task_id}/runs`).catch(() => {})
  } else if (n.link_url) {
    // Strip our APP_BASE_URL prefix if it matches
    const url = String(n.link_url)
    if (url.startsWith(location.origin)) router.push(url.slice(location.origin.length)).catch(() => {})
    else window.open(url, '_blank')
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

onMounted(() => {
  refresh()
  pollTimer = setInterval(refresh, 60_000)
})
onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.bell-btn {
  position: relative;
  width: 36px; height: 36px; border-radius: 50%;
  border: none; background: transparent; cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center;
  color: var(--m-text-secondary);
  transition: background .15s, color .15s;
}
.bell-btn:hover, .bell-btn.active { background: var(--m-surface-variant); color: var(--m-text); }
.badge {
  position: absolute; top: 2px; right: 2px;
  min-width: 8px; height: 14px; padding: 0 4px;
  border-radius: 7px;
  background: var(--m-danger); color: var(--m-on-primary, #fff);
  font-size: 10px; font-weight: 600; line-height: 14px;
  text-align: center;
  border: 1.5px solid var(--m-surface);
  box-sizing: content-box;
  pointer-events: none;
  transform: translate(35%, -35%);
}
/* dot-only style when no number is shown */
.badge.dot { width: 8px; height: 8px; padding: 0; min-width: 0; border-radius: 50%; }

.notif-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 4px 4px 8px;
  border-bottom: 1px solid var(--m-border);
}
.notif-head .title { font-size: 13px; font-weight: 600; }
.notif-head .action {
  font-size: 12px; color: var(--m-primary); cursor: pointer; user-select: none;
}
.notif-head .action:hover { text-decoration: underline; }

.notif-body { max-height: 360px; overflow: auto; padding: 4px 0; }
.state {
  text-align: center; color: var(--m-text-tertiary);
  padding: 24px 0; font-size: 13px;
}
.notif-item {
  display: flex; gap: 10px; padding: 10px 4px;
  cursor: pointer;
  border-radius: 8px;
  transition: background .15s;
}
.notif-item:hover { background: var(--m-surface-variant); }
.notif-item .dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: transparent; margin-top: 6px; flex-shrink: 0;
}
.notif-item.unread .dot { background: var(--m-primary); }
.notif-item .meta { flex: 1; min-width: 0; }
.notif-item .t {
  font-size: 13px; font-weight: 500;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.notif-item .b {
  font-size: 12px; color: var(--m-text-secondary);
  margin-top: 2px;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}
.notif-item .time {
  font-size: 11px; color: var(--m-text-tertiary); margin-top: 4px;
}

.notif-footer {
  border-top: 1px solid var(--m-border);
  text-align: center;
  padding-top: 4px;
}
</style>
