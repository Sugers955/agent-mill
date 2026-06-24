<template>
  <div class="page runs-page">
    <div class="page-head">
      <div>
        <a class="back" @click="$router.push('/tasks')">‹ 返回任务列表</a>
        <div class="page-title">{{ task?.name || `任务 #${taskId}` }} · 执行历史</div>
        <div v-if="task?.description" class="muted small">{{ task.description }}</div>
      </div>
      <div class="head-actions">
        <el-button :icon="Refresh" @click="load">刷新</el-button>
        <el-button type="primary" :icon="VideoPlay" :loading="running" @click="onRun">立即运行</el-button>
      </div>
    </div>

    <el-table :data="rows" v-loading="loading" empty-text="暂无执行记录" style="width:100%">
      <el-table-column label="#" width="60">
        <template #default="{ row }">#{{ row.run_no }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <span class="status-cell">
            <span :class="['status-dot', row.status]"></span>
            {{ statusLabel(row.status) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="触发" width="70">
        <template #default="{ row }">{{ row.triggered_by === 'cron' ? '定时' : '手动' }}</template>
      </el-table-column>
      <el-table-column label="开始时间" width="160">
        <template #default="{ row }">{{ fmtTime(row.started_at || row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="耗时" width="100">
        <template #default="{ row }">
          <span v-if="row.duration_ms">{{ (row.duration_ms / 1000).toFixed(1) }}s</span>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="Tokens" width="120">
        <template #default="{ row }">
          <span v-if="row.tokens_in || row.tokens_out" class="muted small">
            {{ row.tokens_in }} / {{ row.tokens_out }}
          </span>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="摘要 / 错误" min-width="260">
        <template #default="{ row }">
          <el-tooltip
            v-if="row.error_message || row.summary"
            placement="top-start" :show-after="200" :hide-after="0"
            popper-class="run-cell-tip"
          >
            <template #content>
              <div class="tip-body">{{ row.error_message || row.summary }}</div>
            </template>
            <div :class="['cell-clip', row.error_message ? 'err' : 'summary']">
              {{ row.error_message || row.summary }}
            </div>
          </el-tooltip>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right" align="center">
        <template #default="{ row }">
          <div class="row-actions">
            <el-button link type="primary" :disabled="!row.conversation_id"
                       @click="goConv(row.conversation_id)">查看对话</el-button>
            <el-button v-if="['running','pending'].includes(row.status)"
                       link type="warning" @click="onCancel(row)">取消</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="total" class="pager">
      <el-pagination
        background
        layout="total, sizes, prev, pager, next, jumper"
        :total="total"
        :current-page="page"
        :page-size="pageSize"
        :page-sizes="[20, 30, 50, 100]"
        @current-change="onPageChange"
        @size-change="onPageSizeChange"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, VideoPlay } from '@element-plus/icons-vue'
import { api } from '@/api'

const route = useRoute()
const router = useRouter()
const taskId = Number(route.params.id)

const task = ref<any>(null)
const rows = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const running = ref(false)

async function load() {
  loading.value = true
  try {
    const offset = (page.value - 1) * pageSize.value
    const [t, p] = await Promise.all([
      api.task(taskId),
      api.taskRuns(taskId, { limit: pageSize.value, offset }),
    ])
    task.value = t
    rows.value = p.items || []
    total.value = p.total || 0
  } finally { loading.value = false }
}

function onPageChange(p: number) {
  page.value = p
  load()
}

function onPageSizeChange(size: number) {
  pageSize.value = size
  page.value = 1
  load()
}

async function onRun() {
  running.value = true
  try {
    await api.runTask(taskId)
    ElMessage.success('已启动')
    setTimeout(load, 600)
  } finally { running.value = false }
}

async function onCancel(row: any) {
  try {
    await ElMessageBox.confirm('确定取消该执行？', '确认', { type: 'warning' })
    await api.cancelTaskRun(row.id)
    ElMessage.success('已取消')
    await load()
  } catch {}
}

function goConv(cid: number | null) {
  if (!cid) return
  router.push(`/chat?conv=${cid}`).catch(() => {})
}

function statusLabel(s: string) {
  return ({
    succeeded: '成功', failed: '失败', running: '运行中', timeout: '超时',
    cancelled: '已取消', skipped: '已跳过', pending: '等待中',
  } as any)[s] || s
}
function fmtTime(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

onMounted(load)
</script>

<style scoped>
.page { padding: 24px 28px; }
.page-head {
  display: flex; align-items: flex-start; justify-content: space-between;
  margin-bottom: 18px; gap: 16px;
}
.page-title { font-size: 18px; font-weight: 600; margin-top: 4px; }
.back {
  font-size: 12px; color: var(--m-text-secondary);
  cursor: pointer; user-select: none;
}
.back:hover { color: var(--m-primary); }
.head-actions { display: flex; gap: 8px; }

.muted { color: var(--m-text-secondary); }
.small { font-size: 13px; }

/* Unify all run-table cell text to 13px so columns line up visually. */
.runs-page :deep(.el-table .cell) { font-size: 13px; }

.status-cell { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; }
.status-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--m-text-tertiary);
}
.status-dot.succeeded { background: var(--m-success); }
.status-dot.failed, .status-dot.timeout { background: var(--m-danger); }
.status-dot.running, .status-dot.pending { background: var(--m-primary); animation: pulse 1.4s ease-in-out infinite; }
.status-dot.cancelled, .status-dot.skipped { background: var(--m-text-secondary); }
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: .5; transform: scale(.8); }
}

.err { color: var(--m-danger); font-size: 13px; word-break: break-word; }
.summary { font-size: 13px; color: var(--m-text); white-space: pre-wrap; word-break: break-word; }

/* Truncate run summary/error to 2 lines so the table row stays compact;
   full text is visible via tooltip on hover. */
.cell-clip {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-size: 13px;
  line-height: 1.5;
  word-break: break-word;
  white-space: pre-wrap;
  max-height: 40px;
}
.cell-clip.err { color: var(--m-danger); }
.cell-clip.summary { color: var(--m-text); }
:deep(.run-cell-tip) {
  max-width: 480px !important;
}
:deep(.run-cell-tip .tip-body) {
  max-height: 320px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.55;
}

/* Action buttons in run row — text-only, no background, primary blue. */
.row-actions { display: inline-flex; align-items: center; gap: 14px; }
.row-actions :deep(.el-button) {
  margin-left: 0 !important;
  padding: 0 !important;
  height: auto !important;
  font-size: 13px !important;
  background: transparent !important;
  border: none !important;
}

.pager {
  display: flex; justify-content: flex-end;
  padding: 16px 0;
}

.row-actions {
  display: flex; align-items: center; justify-content: center; gap: 14px;
  white-space: nowrap;
}
.row-actions :deep(.el-button) {
  margin-left: 0 !important;
  padding: 0 !important;
  height: auto !important;
}
</style>
