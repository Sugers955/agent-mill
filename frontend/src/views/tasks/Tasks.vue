<template>
  <div class="page">
    <div class="page-head">
      <span class="page-title">自动化</span>
      <el-button type="primary" :icon="Plus" @click="openCreate">新建任务</el-button>
    </div>

    <el-table :data="rows" stripe v-loading="loading" empty-text="暂无任务" style="width:100%">
      <el-table-column label="名称" min-width="200">
        <template #default="{ row }">
          <div style="display:flex;align-items:center;gap:8px">
            <span style="font-weight:500">{{ row.name }}</span>
            <el-tag v-if="!row.enabled" size="small" type="info">已停用</el-tag>
          </div>
          <div v-if="row.description" class="muted small">{{ row.description }}</div>
        </template>
      </el-table-column>
      <el-table-column label="数字员工" width="140" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.agent_name">{{ row.agent_name }}</span>
          <span v-else class="muted">#{{ row.agent_id }}</span>
        </template>
      </el-table-column>
      <el-table-column label="调度" width="180" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="schedule-tag" :data-type="row.schedule_type">{{ scheduleLabel(row) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="上次执行" width="200">
        <template #default="{ row }">
          <div v-if="row.last_run_at" class="last-run">
            <span :class="['status-dot', row.last_run_status]"></span>
            <span>{{ statusLabel(row.last_run_status) }}</span>
            <span class="muted">· {{ relTime(row.last_run_at) }}</span>
          </div>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="启用" width="60" align="center">
        <template #default="{ row }">
          <el-switch :model-value="row.enabled" @change="onToggle(row)" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="340" fixed="right">
        <template #default="{ row }">
          <div class="row-actions">
            <el-button link type="primary" :icon="VideoPlay" :loading="runningId === row.id"
                       @click="onRun(row)">运行</el-button>
            <el-button link type="primary" :icon="Clock"
                       @click="$router.push(`/tasks/${row.id}/runs`)">历史</el-button>
            <el-button link type="primary" :icon="EditPen" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" :icon="Delete" @click="onDelete(row)">删除</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="visible" :title="editing ? '编辑任务' : '新建任务'" width="720px" :close-on-click-modal="false">
      <el-form :model="form" label-width="120px">
        <el-form-item label="名称">
          <el-input v-model="form.name" maxlength="128" show-word-limit />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
         <el-divider><span class="section-title">执行</span></el-divider>
        <el-form-item label="数字员工">
          <el-select v-model="form.agent_id" filterable style="width:100%">
            <el-option v-for="a in agents" :key="a.id" :label="a.name" :value="a.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="提示词">
          <el-input v-model="form.prompt_text" type="textarea" :rows="6"
                    placeholder="任务执行时发送给数字员工的内容" />
        </el-form-item>

        <el-divider><span class="section-title">调度</span></el-divider>
        <el-form-item label="调度类型">
          <el-radio-group v-model="form.schedule_type">
            <el-radio-button value="manual">仅手动</el-radio-button>
            <el-radio-button value="once">单次定时</el-radio-button>
            <el-radio-button value="cron">周期 (cron)</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.schedule_type === 'cron'" label="cron 表达式">
          <el-input v-model="form.schedule_value" placeholder="如 0 9 * * 1-5（工作日 9:00）" />
          <div class="cron-hints">
            <a v-for="p in cronPresets" :key="p.expr" @click.prevent="form.schedule_value = p.expr">{{ p.label }}</a>
          </div>
        </el-form-item>
        <el-form-item v-else-if="form.schedule_type === 'once'" label="执行时间">
          <el-date-picker
            v-model="form.schedule_value" type="datetime"
            format="YYYY-MM-DD HH:mm" value-format="YYYY-MM-DDTHH:mm:ss"
            style="width:100%" placeholder="选择执行时间" />
        </el-form-item>
        <el-form-item label="时区">
          <el-input v-model="form.timezone" placeholder="Asia/Shanghai" />
        </el-form-item>

        <el-divider><span class="section-title">通知</span></el-divider>
        <el-form-item label="通知渠道">
          <el-checkbox-group v-model="form.notify_channels">
            <el-checkbox value="inapp">站内</el-checkbox>
            <el-checkbox value="email">邮件</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item v-if="form.notify_channels.includes('email')" label="收件邮箱">
          <el-input v-model="form.notify_email_to" :placeholder="auth.user?.email || '默认使用账号绑定邮箱'" />
        </el-form-item>
        <el-form-item label="通知时机">
          <el-radio-group v-model="form.notify_on">
            <el-radio-button value="always">总是</el-radio-button>
            <el-radio-button value="success">仅成功</el-radio-button>
            <el-radio-button value="failure">仅失败</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-divider><span class="section-title">高级</span></el-divider>
        <el-form-item label="单次超时">
          <el-input-number v-model="form.max_runtime_seconds" :min="60" :max="86400" :step="60"
                            controls-position="right" />
          <span class="muted small" style="margin-left:8px">秒 · 默认 1800（30 分钟）</span>
        </el-form-item>
        <el-form-item label="并发策略">
          <el-radio-group v-model="form.concurrency_policy">
            <el-radio-button value="skip">上次未完成则跳过</el-radio-button>
            <el-radio-button value="queue" disabled>排队（暂未实现）</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, VideoPlay, Clock, EditPen, Delete } from '@element-plus/icons-vue'
import { api } from '@/api'
import { useAuth } from '@/stores/auth'

const auth = useAuth()
const rows = ref<any[]>([])
const agents = ref<any[]>([])
const loading = ref(false)
const visible = ref(false)
const saving = ref(false)
const editing = ref<any | null>(null)
const runningId = ref<number | null>(null)
const form = reactive<any>(emptyForm())

const cronPresets = [
  { label: '每小时', expr: '0 * * * *' },
  { label: '每天 9:00', expr: '0 9 * * *' },
  { label: '每天 18:00', expr: '0 18 * * *' },
  { label: '工作日 9:00', expr: '0 9 * * 1-5' },
  { label: '每周一 9:00', expr: '0 9 * * 1' },
  { label: '每月 1 号 9:00', expr: '0 9 1 * *' },
]

function emptyForm() {
  return {
    name: '', description: '', agent_id: null, prompt_text: '',
    schedule_type: 'manual', schedule_value: '', timezone: 'Asia/Shanghai',
    max_runtime_seconds: 1800, concurrency_policy: 'skip',
    notify_channels: ['inapp'], notify_email_to: '', notify_on: 'always',
    enabled: true,
  }
}

async function load() {
  loading.value = true
  try {
    const [t, a] = await Promise.all([api.tasks(), api.myAgents()])
    rows.value = t.items || t
    agents.value = a.items || a
  } finally { loading.value = false }
}
onMounted(load)

function openCreate() {
  editing.value = null
  Object.assign(form, emptyForm())
  if (agents.value.length && !form.agent_id) form.agent_id = agents.value[0].id
  visible.value = true
}

function openEdit(row: any) {
  editing.value = row
  Object.assign(form, emptyForm(), JSON.parse(JSON.stringify(row)))
  form.notify_channels = Array.isArray(row.notify_channels) ? [...row.notify_channels] : ['inapp']
  visible.value = true
}

async function onSubmit() {
  if (!form.name?.trim()) return ElMessage.warning('请输入任务名称')
  if (!form.agent_id) return ElMessage.warning('请选择数字员工')
  if (!form.prompt_text?.trim()) return ElMessage.warning('请输入提示词')
  if (form.schedule_type === 'cron' && !form.schedule_value?.trim())
    return ElMessage.warning('请填写 cron 表达式')
  if (form.schedule_type === 'once' && !form.schedule_value)
    return ElMessage.warning('请选择执行时间')
  saving.value = true
  try {
    const payload = { ...form }
    if (payload.schedule_type === 'manual') payload.schedule_value = null
    if (editing.value) await api.updateTask(editing.value.id, payload)
    else await api.createTask(payload)
    ElMessage.success('保存成功')
    visible.value = false
    await load()
  } finally { saving.value = false }
}

async function onDelete(row: any) {
  try {
    await ElMessageBox.confirm(`删除任务「${row.name}」？此操作不可恢复。`, '确认', { type: 'warning' })
    await api.deleteTask(row.id)
    ElMessage.success('已删除')
    await load()
  } catch {}
}

async function onToggle(row: any) {
  await api.toggleTask(row.id)
  await load()
}

async function onRun(row: any) {
  runningId.value = row.id
  try {
    await api.runTask(row.id)
    ElMessage.success('已启动，结束后会通过通知告知')
    await load()
  } finally { runningId.value = null }
}

function scheduleLabel(row: any) {
  if (row.schedule_type === 'manual') return '仅手动'
  if (row.schedule_type === 'once') return `单次 · ${(row.schedule_value || '').replace('T', ' ').slice(0, 16)}`
  return `cron · ${row.schedule_value}`
}

function statusLabel(s: string | null | undefined) {
  return ({
    succeeded: '成功', failed: '失败', running: '运行中', timeout: '超时',
    cancelled: '已取消', skipped: '已跳过', pending: '等待中',
  } as any)[s || ''] || s || '—'
}

function relTime(iso: string | null | undefined) {
  if (!iso) return ''
  const t = new Date(iso).getTime()
  const diff = Date.now() - t
  if (diff < 60_000) return '刚刚'
  if (diff < 3600_000) return `${Math.floor(diff / 60_000)} 分钟前`
  if (diff < 86400_000) return `${Math.floor(diff / 3600_000)} 小时前`
  return new Date(iso).toLocaleString()
}
</script>

<style scoped>
.page { padding: 24px 28px; }
.page-head {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 18px;
}
.page-title { font-size: 18px; font-weight: 600; letter-spacing: -.01em; }

/* Unify all table cell text to 13px so columns line up visually. */
.tasks-page :deep(.el-table .cell) { font-size: 13px; }

.small { font-size: 13px; }

.last-run {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px;
  white-space: nowrap;
}

.row-actions {
  display: flex; align-items: center; gap: 14px;
  white-space: nowrap;
}
.row-actions :deep(.el-button) {
  margin-left: 0 !important;
  padding: 0 !important;
  height: auto !important;
  font-size: 13px !important;
  background: transparent !important;
  border: none !important;
}
.row-actions :deep(.el-button .el-icon) { margin-right: 4px; font-size: 14px; }
.row-actions :deep(.el-button.is-loading),
.row-actions :deep(.el-button.is-loading::before) {
  background: transparent !important;
}

.muted { color: var(--m-text-secondary); }

.section-title { font-size: 12px; color: var(--m-text-secondary); }

.cron-hints {
  display: flex; flex-wrap: wrap; gap: 4px 10px;
  margin-top: 6px; font-size: 12px;
}
.cron-hints a {
  color: var(--m-primary); cursor: pointer; user-select: none;
}
.cron-hints a:hover { text-decoration: underline; }

.schedule-tag {
  display: inline-flex; align-items: center;
  font-size: 12px; padding: 2px 8px;
  border-radius: var(--m-radius-pill);
  background: var(--m-surface-variant);
  color: var(--m-text-secondary);
}
.schedule-tag[data-type="cron"] { background: rgba(66,133,244,.08); color: var(--m-primary); }
.schedule-tag[data-type="once"] { background: rgba(251,188,4,.12); color: var(--m-warning); }

.status-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--m-text-tertiary); flex-shrink: 0;
}
.status-dot.succeeded { background: var(--m-success); }
.status-dot.failed, .status-dot.timeout { background: var(--m-danger); }
.status-dot.running, .status-dot.pending { background: var(--m-primary); animation: pulse 1.4s ease-in-out infinite; }
.status-dot.cancelled, .status-dot.skipped { background: var(--m-text-secondary); }
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: .5; transform: scale(.8); }
}
</style>
