<template>
  <div class="page">
    <div class="page-head"><span class="page-title">日志</span></div>
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
        <el-table :data="audits.items" border v-loading="loading">
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
          <el-table-column prop="action" label="动作" width="160" />
          <el-table-column prop="target_type" label="对象类型" width="120" />
          <el-table-column prop="target_id" label="对象ID" width="100" />
          <el-table-column label="详情" min-width="240" show-overflow-tooltip>
            <template #default="{ row }"><code>{{ JSON.stringify(row.detail_json) }}</code></template>
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
import { ref, onMounted, watch } from 'vue'
import { api } from '@/api'

const tab = ref('calls')
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const calls = ref<{ items: any[]; total: number }>({ items: [], total: 0 })
const audits = ref<{ items: any[]; total: number }>({ items: [], total: 0 })

async function load() {
  loading.value = true
  try {
    const offset = (page.value - 1) * pageSize.value
    if (tab.value === 'calls') calls.value = await api.callLogs(pageSize.value, offset)
    else audits.value = await api.auditLogs(pageSize.value, offset)
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

function fmtTime(s: string) {
  if (!s) return ''
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return s
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

onMounted(load)
watch(tab, () => {
  page.value = 1
  load()
})
</script>

<style scoped>
.muted { color: var(--m-text-tertiary); }
.pager { display: flex; justify-content: flex-end; margin-top: 12px; }
</style>
