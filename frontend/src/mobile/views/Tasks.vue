<template>
  <div class="mb-page tasks-mb">
    <header class="mb-header soft">
      <button class="mb-icon-btn" @click="$router.back()" aria-label="返回">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
      </button>
      <span class="page-title">任务</span>
      <button class="mb-icon-btn" @click="$router.push('/notifications')" aria-label="通知">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
      </button>
    </header>

    <div class="body">
      <div v-if="loading && !rows.length" class="empty">加载中…</div>
      <div v-else-if="!rows.length" class="empty">
        <div>暂无任务</div>
        <div class="hint">请在 PC 端创建</div>
      </div>

      <div v-for="t in rows" :key="t.id" class="task-card" @click="$router.push(`/tasks/${t.id}`)">
        <div class="row1">
          <span class="name">{{ t.name }}</span>
          <span v-if="!t.enabled" class="off-tag">已停用</span>
        </div>
        <div v-if="t.description" class="desc">{{ t.description }}</div>
        <div class="row2">
          <span class="schedule" :data-type="t.schedule_type">{{ scheduleLabel(t) }}</span>
          <span v-if="t.last_run_status" class="status">
            <span :class="['dot', t.last_run_status]"></span>
            {{ statusLabel(t.last_run_status) }} · {{ relTime(t.last_run_at) }}
          </span>
        </div>
        <div class="row3">
          <span class="agent">{{ t.agent_name || `#${t.agent_id}` }}</span>
          <button class="run" :disabled="runningId === t.id" @click.stop="onRun(t)">
            {{ runningId === t.id ? '启动中…' : '立即运行' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '../api'
import { showToast } from '../toast'

const rows = ref<any[]>([])
const loading = ref(false)
const runningId = ref<number | null>(null)

async function load() {
  loading.value = true
  try { rows.value = await api.tasks() } catch {} finally { loading.value = false }
}
onMounted(load)

async function onRun(t: any) {
  runningId.value = t.id
  try {
    await api.runTask(t.id)
    showToast('已启动，结束后会通过通知告知', 'success')
    setTimeout(load, 600)
  } catch {} finally { runningId.value = null }
}

function scheduleLabel(t: any) {
  if (t.schedule_type === 'manual') return '仅手动'
  if (t.schedule_type === 'once') return `单次 · ${(t.schedule_value || '').replace('T', ' ').slice(0, 16)}`
  return `cron · ${t.schedule_value}`
}
function statusLabel(s: string) {
  return ({
    succeeded: '成功', failed: '失败', running: '运行中', timeout: '超时',
    cancelled: '已取消', skipped: '已跳过', pending: '等待中',
  } as any)[s] || s
}
function relTime(iso: string) {
  if (!iso) return ''
  const t = new Date(iso).getTime()
  const diff = Date.now() - t
  if (diff < 60_000) return '刚刚'
  if (diff < 3600_000) return `${Math.floor(diff / 60_000)} 分钟前`
  if (diff < 86400_000) return `${Math.floor(diff / 3600_000)} 小时前`
  return new Date(iso).toLocaleDateString()
}
</script>

<style scoped>
.tasks-mb { background: var(--m-bg); }
.mb-header.soft { background: var(--m-bg); border-bottom: none; }
.body { flex: 1; overflow: auto; padding: 8px 12px 24px; }
.empty {
  text-align: center; color: var(--m-text-tertiary);
  padding: 60px 20px; font-size: 14px;
}
.empty .hint { font-size: 12px; margin-top: 6px; color: var(--m-text-tertiary); }

.task-card {
  background: var(--m-surface);
  border-radius: 14px;
  padding: 14px;
  margin-bottom: 10px;
  box-shadow: var(--m-shadow-1);
}
.task-card:active { background: var(--m-bg-soft); }
.row1 {
  display: flex; align-items: center; gap: 8px;
  font-size: 15px; font-weight: 600; color: var(--m-text);
}
.row1 .name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.off-tag {
  font-size: 11px; padding: 1px 6px;
  background: var(--m-surface-variant); color: var(--m-text-secondary);
  border-radius: var(--m-radius-pill);
}
.desc {
  font-size: 12.5px; color: var(--m-text-secondary);
  margin-top: 4px;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.row2 {
  display: flex; flex-wrap: wrap; gap: 8px;
  margin-top: 8px;
  font-size: 11.5px; color: var(--m-text-secondary);
}
.schedule {
  padding: 2px 8px; border-radius: var(--m-radius-pill);
  background: var(--m-surface-variant);
}
.schedule[data-type="cron"] { background: rgba(66,133,244,.08); color: var(--m-primary); }
.schedule[data-type="once"] { background: rgba(251,188,4,.12); color: #b06000; }
.status { display: inline-flex; align-items: center; gap: 4px; }
.dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--m-text-tertiary);
}
.dot.succeeded { background: var(--m-success); }
.dot.failed, .dot.timeout { background: var(--m-danger); }
.dot.running, .dot.pending { background: var(--m-primary); }
.dot.cancelled, .dot.skipped { background: #9aa0a6; }

.row3 {
  display: flex; align-items: center; justify-content: space-between;
  margin-top: 12px;
}
.agent { font-size: 12px; color: var(--m-text-secondary); }
.run {
  background: var(--m-primary); color: #fff;
  height: 30px; padding: 0 14px; border-radius: 999px;
  font-size: 12.5px; font-weight: 500;
}
.run:disabled { background: var(--m-border-strong); }
.run:active:not(:disabled) { background: var(--m-primary-hover); }
</style>
