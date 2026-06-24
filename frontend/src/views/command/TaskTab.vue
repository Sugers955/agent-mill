<template>
  <div class="task-tab">
    <div class="task-header">
      <div class="th-left">
        <h3 class="th-title">
          我的任务
          <span class="th-count">{{ tasks.length }}</span>
        </h3>
        <p class="th-sub">管理和跟踪数字员工的任务执行</p>
      </div>
      <el-button type="primary" @click="createTask">
        <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M8 3v10M3 8h10"/></svg>
        新建任务
      </el-button>
    </div>

    <div class="task-filters">
      <el-radio-group v-model="statusFilter" size="small">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="running">
          <span class="tf-dot running" />进行中
        </el-radio-button>
        <el-radio-button value="succeeded">
          <span class="tf-dot succeeded" />已完成
        </el-radio-button>
        <el-radio-button value="failed">
          <span class="tf-dot failed" />失败
        </el-radio-button>
        <el-radio-button value="pending">
          <span class="tf-dot pending" />待执行
        </el-radio-button>
      </el-radio-group>
    </div>

    <div class="task-list">
      <div v-for="task in filteredTasks" :key="task.id" class="task-card" @click="viewTask(task)">
        <div class="tc-left">
          <div class="tc-icon" :class="statusClass(task.last_run_status)">
            <svg v-if="task.last_run_status === 'running'" viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="8" r="6"/><path d="M8 4v4l3 2"/></svg>
            <svg v-else-if="task.last_run_status === 'succeeded'" viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M4 8l3 3 5-6"/></svg>
            <svg v-else-if="task.last_run_status === 'failed'" viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="8" cy="8" r="6"/><path d="M6 6l4 4M10 6l-4 4"/></svg>
            <svg v-else viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="8" cy="8" r="6"/><path d="M8 5v4"/></svg>
          </div>
        </div>
        <div class="tc-body">
          <div class="tc-name">{{ task.name }}</div>
          <div class="tc-meta">
            <span class="tc-agent">
              <svg viewBox="0 0 16 16" width="11" height="11" fill="none" stroke="currentColor" stroke-width="1.3"><circle cx="8" cy="6" r="3"/><path d="M3 14c0-2.761 2.239-5 5-5s5 2.239 5 5"/></svg>
              {{ task.agent_name || '--' }}
            </span>
            <span class="tc-sep" />
            <span class="tc-time" :title="task.last_run_at || task.created_at">
              <svg viewBox="0 0 16 16" width="11" height="11" fill="none" stroke="currentColor" stroke-width="1.3"><circle cx="8" cy="8" r="6"/><path d="M8 4v4l3 2"/></svg>
              {{ relTime(task.last_run_at || task.created_at) }}
            </span>
          </div>
        </div>
        <div class="tc-right">
          <span class="tc-status" :class="statusClass(task.last_run_status)">
            <span class="tc-status-dot" />
            {{ statusLabel(task.last_run_status) }}
          </span>
        </div>
      </div>

      <div v-if="!filteredTasks.length" class="task-empty">
        <svg viewBox="0 0 48 48" width="48" height="48" fill="none" opacity="0.2">
          <rect x="6" y="8" width="36" height="32" rx="4" stroke="currentColor" stroke-width="1.5" />
          <path d="M16 20h16M16 28h10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
        </svg>
        <p>{{ statusFilter ? '没有匹配状态的任务' : '暂无任务，点击上方按钮创建' }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api'

const router = useRouter()
const tasks = ref<any[]>([])
const statusFilter = ref('')

onMounted(async () => {
  try {
    const res = await api.tasks()
    tasks.value = res.items || res
  } catch (e) {
    console.error('Failed to load tasks:', e)
  }
})

const filteredTasks = computed(() => {
  if (!statusFilter.value) return tasks.value
  return tasks.value.filter(t => t.last_run_status === statusFilter.value)
})

function statusClass(s: string | null) {
  return s || 'pending'
}

function statusLabel(status: string | null) {
  const map: Record<string, string> = { pending: '待执行', running: '进行中', succeeded: '已完成', failed: '失败' }
  return map[status || ''] || '未知'
}

function relTime(date: string | null) {
  if (!date) return '--'
  const diff = Date.now() - new Date(date).getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  return `${Math.floor(diff / 86400000)}天前`
}

function createTask() { router.push('/tasks').catch(() => {}) }
function viewTask(task: any) { router.push(`/tasks?task=${task.id}`).catch(() => {}) }
</script>

<style scoped>
.task-tab { height: 100%; display: flex; flex-direction: column; }

.task-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.th-left { display: flex; flex-direction: column; gap: 4px; }
.th-title { margin: 0; font-size: 16px; font-weight: 600; color: var(--m-text); display: flex; align-items: center; gap: 8px; }
.th-count { font-size: 11px; font-weight: 500; color: var(--m-text-secondary); background: var(--m-bg-soft); padding: 1px 7px; border-radius: 8px; }
.th-sub { margin: 0; font-size: 13px; color: var(--m-text-secondary); }

.task-filters { margin-bottom: 16px; }
.tf-dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; margin-right: 4px; vertical-align: middle; }
.tf-dot.running { background: var(--m-primary); }
.tf-dot.succeeded { background: var(--m-success); }
.tf-dot.failed { background: var(--m-danger); }
.tf-dot.pending { background: var(--m-warning, #f59e0b); }

.task-list { flex: 1; display: flex; flex-direction: column; gap: 10px; overflow-y: auto; }
.task-card {
  display: flex; align-items: center; gap: 14px;
  padding: 14px 16px;
  background: var(--m-surface); border: 1px solid var(--m-border);
  border-radius: 12px; cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
  animation: taskIn 0.25s ease;
}
@keyframes taskIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
.task-card:hover { transform: translateY(-1px); border-color: var(--m-primary); box-shadow: 0 4px 16px rgba(0,0,0,0.04); }

.tc-icon {
  width: 36px; height: 36px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.tc-icon.running { background: var(--m-primary-soft); color: var(--m-primary); }
.tc-icon.succeeded { background: var(--m-success-soft); color: var(--m-success); }
.tc-icon.failed { background: var(--m-danger-soft); color: var(--m-danger); }
.tc-icon.pending { background: var(--m-warning-soft, rgba(245,158,11,0.1)); color: var(--m-warning, #f59e0b); }

.tc-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; }
.tc-name { font-size: 14px; font-weight: 500; color: var(--m-text); }
.tc-meta { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--m-text-secondary); }
.tc-agent, .tc-time { display: flex; align-items: center; gap: 4px; }
.tc-sep { width: 3px; height: 3px; border-radius: 50%; background: var(--m-text-tertiary); }

.tc-right { flex-shrink: 0; }
.tc-status {
  display: flex; align-items: center; gap: 5px;
  padding: 4px 10px; border-radius: 6px;
  font-size: 12px; font-weight: 500;
}
.tc-status-dot { width: 6px; height: 6px; border-radius: 50%; }
.tc-status.running { background: var(--m-primary-soft); color: var(--m-primary); }
.tc-status.running .tc-status-dot { background: var(--m-primary); animation: tc-pulse 1.2s ease-in-out infinite; }
.tc-status.succeeded { background: var(--m-success-soft); color: var(--m-success); }
.tc-status.succeeded .tc-status-dot { background: var(--m-success); }
.tc-status.failed { background: var(--m-danger-soft); color: var(--m-danger); }
.tc-status.failed .tc-status-dot { background: var(--m-danger); }
.tc-status.pending { background: rgba(245,158,11,0.1); color: #f59e0b; }
.tc-status.pending .tc-status-dot { background: #f59e0b; }
@keyframes tc-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

.task-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; color: var(--m-text-secondary); font-size: 13px; }
</style>
