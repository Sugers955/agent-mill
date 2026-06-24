<template>
  <div class="page">
    <div class="page-head"><span class="page-title">日志</span></div>

    <div class="filters">
      <el-select
        v-model="filterUserId"
        placeholder="按用户筛选"
        clearable
        filterable
        class="filter-select"
        @change="onFilterChange"
      >
        <el-option
          v-for="u in users"
          :key="u.id"
          :label="u.display_name ? `${u.display_name} (${u.username})` : u.username"
          :value="u.id"
        />
      </el-select>
      <el-select
        v-if="tab === 'calls'"
        v-model="filterAgentId"
        placeholder="按数字员工筛选"
        clearable
        filterable
        class="filter-select"
        @change="onFilterChange"
      >
        <el-option v-for="a in agents" :key="a.id" :label="a.name" :value="a.id" />
      </el-select>
      <el-select
        v-if="tab === 'audit'"
        v-model="filterAction"
        placeholder="按动作筛选"
        clearable
        class="filter-select filter-small"
        @change="onFilterChange"
      >
        <el-option label="login" value="login" />
        <el-option label="logout" value="logout" />
        <el-option label="create" value="create" />
        <el-option label="update" value="update" />
        <el-option label="delete" value="delete" />
        <el-option label="read" value="read" />
      </el-select>
      <el-select
        v-if="tab === 'audit'"
        v-model="filterResourceType"
        placeholder="按资源类型筛选"
        clearable
        class="filter-select filter-small"
        @change="onFilterChange"
      >
        <el-option label="auth" value="auth" />
        <el-option label="user" value="user" />
        <el-option label="agent" value="agent" />
        <el-option label="model" value="model" />
        <el-option label="conversation" value="conversation" />
        <el-option label="task" value="task" />
        <el-option label="skill" value="skill" />
        <el-option label="role" value="role" />
        <el-option label="file" value="file" />
      </el-select>
      <el-button v-if="hasFilter" link type="primary" @click="clearFilters">清空筛选</el-button>
    </div>

    <el-tabs v-model="tab">
      <el-tab-pane label="调用日志" name="calls">
        <el-table :data="calls.items" border v-loading="loading">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column label="时间" width="170">
            <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="用户" width="140" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.user_name">{{ row.user_name }}</span>
              <span v-else-if="row.user_id" class="muted">#{{ row.user_id }}</span>
              <span v-else class="muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="Agent" width="140" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.agent_name">{{ row.agent_name }}</span>
              <span v-else-if="row.agent_id" class="muted">#{{ row.agent_id }}</span>
              <span v-else class="muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="模型" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.model_name">{{ row.model_name }}</span>
              <span v-else-if="row.model_id" class="muted">#{{ row.model_id }}</span>
              <span v-else class="muted">—</span>
              <span v-if="row.model_provider" class="muted"> ({{ row.model_provider }})</span>
            </template>
          </el-table-column>
          <el-table-column prop="tokens_in" label="输入Tokens" width="110" />
          <el-table-column prop="tokens_out" label="输出Tokens" width="110" />
          <el-table-column prop="latency_ms" label="耗时(ms)" width="100" />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.status === 'ok' ? 'success' : 'danger'" size="small" effect="light">
                {{ row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="error" label="错误" min-width="160" show-overflow-tooltip />
        </el-table>
        <div class="pager">
          <el-pagination
            background
            layout="total, sizes, prev, pager, next, jumper"
            :total="calls.total"
            :page-size="pageSize"
            :current-page="page"
            :page-sizes="[20, 50, 100, 200]"
            @current-change="onPageChange"
            @size-change="onSizeChange"
          />
        </div>
      </el-tab-pane>

      <el-tab-pane label="审计日志" name="audit">
        <el-table :data="audits.items" border v-loading="loading" style="width:100%">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column label="时间" width="165">
            <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="用户" width="130" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.user_name">{{ row.user_name }}</span>
              <span v-else-if="row.user_id" class="muted">#{{ row.user_id }}</span>
              <span v-else class="muted">—</span>
            </template>
          </el-table-column>
          <el-table-column prop="action" label="动作" width="100" />
          <el-table-column prop="resource_type" label="资源类型" width="100" />
          <el-table-column prop="resource_id" label="资源ID" width="80" />
          <el-table-column prop="ip_address" label="IP" width="130" />
          <el-table-column label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.status === 'success' ? 'success' : row.status === 'denied' ? 'warning' : 'danger'" size="small" effect="light">
                {{ row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="详情" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">
              <code class="detail-json">{{ row.detail_json ? JSON.stringify(row.detail_json) : '' }}</code>
            </template>
          </el-table-column>
          <el-table-column prop="error_message" label="错误信息" min-width="160" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.error_message" class="error-text">{{ row.error_message }}</span>
              <span v-else class="muted">—</span>
            </template>
          </el-table-column>
        </el-table>
        <div class="pager">
          <el-pagination
            background
            layout="total, sizes, prev, pager, next, jumper"
            :total="audits.total"
            :page-size="pageSize"
            :current-page="page"
            :page-sizes="[20, 50, 100, 200]"
            @current-change="onPageChange"
            @size-change="onSizeChange"
          />
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { api } from '@/api'

const tab = ref('calls')
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const calls = ref<{ items: any[]; total: number }>({ items: [], total: 0 })
const audits = ref<{ items: any[]; total: number }>({ items: [], total: 0 })

const filterUserId = ref<number | null>(null)
const filterAgentId = ref<number | null>(null)
const filterAction = ref<string | null>(null)
const filterResourceType = ref<string | null>(null)
const users = ref<any[]>([])
const agents = ref<any[]>([])

const hasFilter = computed(() => filterUserId.value != null || filterAgentId.value != null || filterAction.value != null || filterResourceType.value != null)

async function load() {
  loading.value = true
  try {
    const offset = (page.value - 1) * pageSize.value
    if (tab.value === 'calls') {
      const res = await api.callLogs({
        limit: pageSize.value,
        offset,
        user_id: filterUserId.value ?? undefined,
        agent_id: filterAgentId.value ?? undefined,
      })
      calls.value = { items: res.items ?? res, total: res.total ?? (Array.isArray(res) ? res.length : 0) }
    } else {
      const res = await api.auditLogs({
        limit: pageSize.value,
        offset,
        user_id: filterUserId.value ?? undefined,
        action: filterAction.value ?? undefined,
        resource_type: filterResourceType.value ?? undefined,
      })
      audits.value = { items: res.items ?? res, total: res.total ?? (Array.isArray(res) ? res.length : 0) }
    }
  } finally {
    loading.value = false
  }
}

function onPageChange(p: number) {
  page.value = p
  load()
}

function onSizeChange(s: number) {
  pageSize.value = s
  page.value = 1
  load()
}

function onFilterChange() {
  page.value = 1
  load()
}

function clearFilters() {
  filterUserId.value = null
  filterAgentId.value = null
  filterAction.value = null
  filterResourceType.value = null
  page.value = 1
  load()
}

function fmtTime(s: string) {
  if (!s) return ''
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return s
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

onMounted(async () => {
  const [us, as] = await Promise.all([
    api.users({ limit: 200 }).catch(() => ({ items: [] })),
    api.agents().catch(() => []),
  ])
  users.value = us.items || []
  agents.value = as.items || as
  await load()
})

watch(tab, () => {
  page.value = 1
  filterAction.value = null
  filterResourceType.value = null
  if (tab.value === 'audit') filterAgentId.value = null
  load()
})
</script>

<style scoped>
.muted { color: var(--m-text-tertiary); }
.error-text { color: var(--el-color-danger); font-size: 12px; }
.detail-json { font-size: 11px; line-height: 1.5; white-space: pre-wrap; word-break: break-all; }
.filters {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 0 4px;
}
.filter-select { width: 240px; }
.filter-small { width: 150px; }
.pager { display: flex; justify-content: flex-end; margin-top: 12px; }
</style>
