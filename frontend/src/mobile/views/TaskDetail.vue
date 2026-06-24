<template>
  <div class="mb-page detail-mb">
    <header class="mb-header soft">
      <button class="mb-icon-btn" @click="$router.back()" aria-label="返回">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
      </button>
      <div class="mb-header-title"><span class="name">{{ task?.name || '任务详情' }}</span></div>
      <div style="width:36px"></div>
    </header>

    <div class="body">
      <section v-if="task" class="card">
        <div class="card-h">{{ task.name }}</div>
        <div v-if="task.description" class="card-d">{{ task.description }}</div>
        <div class="meta-row">
          <span class="kv"><span>数字员工</span>{{ task.agent_name || `#${task.agent_id}` }}</span>
          <span class="kv"><span>调度</span>{{ scheduleLabel(task) }}</span>
        </div>
        <div class="meta-row">
          <span class="kv"><span>启用</span>{{ task.enabled ? '是' : '否' }}</span>
          <span class="kv"><span>超时</span>{{ task.max_runtime_seconds }} s</span>
        </div>
        <button class="run" :disabled="running" @click="onRun">
          {{ running ? '启动中…' : '立即运行' }}
        </button>
      </section>

      <section class="card">
        <div class="card-title">提示词</div>
        <pre class="prompt">{{ task?.prompt_text || '（空）' }}</pre>
      </section>

      <section class="runs-section">
        <div class="card-title">执行历史 <span class="muted">{{ total }} 条</span></div>
        <div v-if="!runs.length && !loading" class="empty">暂无执行</div>
        <div v-for="r in runs" :key="r.id" class="run-card" @click="goConv(r)">
          <div class="run-h">
            <span class="run-no">#{{ r.run_no }}</span>
            <span class="status">
              <span :class="['dot', r.status]"></span>
              {{ statusLabel(r.status) }}
            </span>
            <span class="muted small">{{ r.triggered_by === 'cron' ? '定时' : '手动' }}</span>
            <span class="muted small" style="margin-left:auto">{{ relTime(r.started_at || r.created_at) }}</span>
          </div>
          <div v-if="r.error_message" class="err">{{ r.error_message }}</div>
          <div v-else-if="r.summary" class="summary">{{ r.summary }}</div>
          <div class="run-meta">
            <span v-if="r.duration_ms">{{ (r.duration_ms / 1000).toFixed(1) }} s</span>
            <span v-if="r.tokens_in || r.tokens_out">· {{ r.tokens_in }}/{{ r.tokens_out }} tok</span>
          </div>
        </div>
        <button v-if="total > runs.length" class="load-more" @click="loadMore" :disabled="loadingMore">
          {{ loadingMore ? '加载中…' : '加载更多' }}
        </button>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { showToast } from '../toast'

const route = useRoute()
const router = useRouter()
const taskId = Number(route.params.id)

const task = ref<any>(null)
const runs = ref<any[]>([])
const total = ref(0)
const loading = ref(false)
const loadingMore = ref(false)
const running = ref(false)

async function load() {
  loading.value = true
  try {
    const [t, page] = await Promise.all([
      api.task(taskId),
      api.taskRuns(taskId, { limit: 20 }),
    ])
    task.value = t
    runs.value = page.items || []
    total.value = page.total || 0
  } catch {} finally { loading.value = false }
}
async function loadMore() {
  loadingMore.value = true
  try {
    const page = await api.taskRuns(taskId, { limit: 20, offset: runs.value.length })
    runs.value = [...runs.value, ...(page.items || [])]
    total.value = page.total || runs.value.length
  } finally { loadingMore.value = false }
}
async function onRun() {
  running.value = true
  try {
    await api.runTask(taskId)
    showToast('已启动', 'success')
    setTimeout(load, 800)
  } finally { running.value = false }
}
function goConv(r: any) {
  if (r.conversation_id) {
    // 移动端 chat 用 hash 路由 + store；用 query 不直接生效，跳到 /chat 让用户手动选；
    // 这里先把会话 id 通过 store 选中再跳转
    router.push(`/chat?conv=${r.conversation_id}`)
  }
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

onMounted(load)
</script>

<style scoped>
.detail-mb { background: var(--m-bg); }
.mb-header.soft { background: var(--m-bg); border-bottom: none; }
.body { flex: 1; overflow: auto; padding: 8px 12px 24px; }

.card {
  background: var(--m-surface);
  border-radius: 14px;
  padding: 14px;
  margin-bottom: 10px;
  box-shadow: var(--m-shadow-1);
}
.card-h { font-size: 16px; font-weight: 600; color: var(--m-text); }
.card-d { font-size: 12.5px; color: var(--m-text-secondary); margin-top: 6px; line-height: 1.5; }
.card-title {
  font-size: 12px; color: var(--m-text-secondary);
  margin: 14px 4px 8px; font-weight: 600; letter-spacing: .03em; text-transform: uppercase;
}
.muted { color: var(--m-text-tertiary); font-weight: 400; text-transform: none; }
.small { font-size: 11px; }

.meta-row {
  display: flex; flex-wrap: wrap; gap: 14px;
  margin-top: 10px; font-size: 12px;
}
.kv { display: inline-flex; flex-direction: column; }
.kv > span:first-child {
  font-size: 11px; color: var(--m-text-tertiary); margin-bottom: 2px;
}

.run {
  margin-top: 14px; height: 38px; width: 100%;
  background: var(--m-primary); color: #fff;
  border-radius: 12px; font-size: 14px; font-weight: 500;
}
.run:disabled { background: var(--m-border-strong); }
.run:active:not(:disabled) { background: var(--m-primary-hover); }

.prompt {
  margin: 0;
  background: var(--m-bg-soft);
  border-radius: 10px; padding: 10px 12px;
  font-family: ui-monospace, Menlo, monospace;
  font-size: 12px; line-height: 1.55;
  white-space: pre-wrap; word-break: break-word;
  max-height: 240px; overflow: auto;
  color: var(--m-text);
}

.runs-section { margin-top: 4px; }
.empty { text-align: center; color: var(--m-text-tertiary); padding: 16px; font-size: 13px; }

.run-card {
  background: var(--m-surface);
  border-radius: 12px;
  padding: 12px;
  margin-bottom: 8px;
  box-shadow: var(--m-shadow-1);
}
.run-card:active { background: var(--m-bg-soft); }
.run-h {
  display: flex; align-items: center; gap: 8px;
  font-size: 13px; color: var(--m-text);
}
.run-no { font-weight: 600; }
.status { display: inline-flex; align-items: center; gap: 4px; }
.dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--m-text-tertiary);
}
.dot.succeeded { background: var(--m-success); }
.dot.failed, .dot.timeout { background: var(--m-danger); }
.dot.running, .dot.pending { background: var(--m-primary); }
.dot.cancelled, .dot.skipped { background: #9aa0a6; }

.err { color: var(--m-danger); font-size: 12px; margin-top: 6px; word-break: break-word; }
.summary {
  font-size: 12.5px; color: var(--m-text); margin-top: 6px;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
  white-space: pre-wrap; word-break: break-word;
}
.run-meta { font-size: 11px; color: var(--m-text-tertiary); margin-top: 6px; }

.load-more {
  width: 100%; height: 36px; margin-top: 4px;
  background: transparent;
  color: var(--m-primary);
  font-size: 13px; font-weight: 500;
}
.load-more:disabled { color: var(--m-text-tertiary); }
</style>
