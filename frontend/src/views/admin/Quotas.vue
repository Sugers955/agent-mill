<template>
  <div class="page">
    <div class="page-head">
      <span class="page-title">额度管理</span>
      <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>新建额度</el-button>
    </div>

    <div class="surface" style="padding:0">
      <el-table :data="items" stripe v-loading="loading">
        <el-table-column prop="user_name" label="用户" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.user_name || `#${row.user_id}` }}</template>
        </el-table-column>
        <el-table-column label="月度上限" width="140">
          <template #default="{ row }">{{ row.monthly_limit > 0 ? fmtTokens(row.monthly_limit) : '不限' }}</template>
        </el-table-column>
        <el-table-column label="当月已用" width="140">
          <template #default="{ row }">
            <span v-if="usageMap[row.user_id] !== undefined">{{ fmtTokens(usageMap[row.user_id]) }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="使用率" width="200">
          <template #default="{ row }">
            <template v-if="row.monthly_limit > 0 && usageMap[row.user_id] !== undefined">
              <el-progress
                :percentage="Math.min(100, Math.round(usageMap[row.user_id] * 100 / row.monthly_limit))"
                :color="progressColor(usageMap[row.user_id] * 100 / row.monthly_limit)"
                :stroke-width="14"
                :text-inside="true"
                style="width:100%"
              />
            </template>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="告警阈值" width="100">
          <template #default="{ row }">{{ row.alert_threshold }}%</template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text @click="openEdit(row)">编辑</el-button>
            <el-button size="small" text type="danger" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <el-pagination
          background
          layout="total, sizes, prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :current-page="page"
          :page-sizes="[20, 50, 100]"
          @current-change="(p: number) => { page = p; load() }"
          @size-change="(s: number) => { pageSize = s; page = 1; load() }"
        />
      </div>
    </div>

    <el-dialog v-model="visible" :title="editing ? '编辑额度' : '新建额度'" width="460px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="用户" v-if="!editing">
          <el-select v-model="form.user_id" filterable placeholder="搜索用户" style="width:100%">
            <el-option v-for="u in userList" :key="u.id" :label="u.display_name || u.username" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-else label="用户">
          <el-input :model-value="editing.user_name || `#${editing.user_id}`" disabled />
        </el-form-item>
        <el-form-item label="月度上限">
          <el-input-number v-model="form.monthly_limit" :min="0" :step="10000" style="width:100%" />
          <div class="form-hint">0 表示不限制</div>
        </el-form-item>
        <el-form-item label="告警阈值">
          <el-input-number v-model="form.alert_threshold" :min="0" :max="100" :step="10" style="width:100%" />
          <div class="form-hint">达到该百分比时发送告警通知</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'

const items = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const usageMap = reactive<Record<number, number>>({})

const visible = ref(false)
const editing = ref<any>(null)
const saving = ref(false)
const userList = ref<any[]>([])

const form = reactive({
  user_id: null as number | null,
  monthly_limit: 0,
  alert_threshold: 80,
})

function fmtTokens(n: number) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}

function progressColor(pct: number) {
  if (pct >= 90) return 'var(--m-danger)'
  if (pct >= 70) return 'var(--m-warning)'
  return 'var(--m-success)'
}

async function load() {
  loading.value = true
  try {
    const d = await api.quotas({ page: page.value, size: pageSize.value })
    items.value = d.items
    total.value = d.total
    // 并行加载每个用户的当月用量
    for (const q of d.items) {
      api.quotaUsage(q.user_id).then((u: any) => {
        usageMap[q.user_id] = u.monthly_usage
      }).catch(() => {})
    }
  } finally {
    loading.value = false
  }
}

async function loadUsers() {
  try {
    const d = await api.users({ limit: 200 })
    userList.value = d.items
  } catch {}
}

function openCreate() {
  editing.value = null
  form.user_id = null
  form.monthly_limit = 0
  form.alert_threshold = 80
  visible.value = true
  loadUsers()
}

function openEdit(row: any) {
  editing.value = row
  form.user_id = row.user_id
  form.monthly_limit = row.monthly_limit
  form.alert_threshold = row.alert_threshold
  visible.value = true
}

async function onSave() {
  if (!editing.value && !form.user_id) {
    ElMessage.warning('请选择用户')
    return
  }
  saving.value = true
  try {
    if (editing.value) {
      await api.updateQuota(editing.value.user_id, {
        monthly_limit: form.monthly_limit,
        alert_threshold: form.alert_threshold,
      })
    } else {
      await api.createQuota({
        user_id: form.user_id,
        monthly_limit: form.monthly_limit,
        alert_threshold: form.alert_threshold,
      })
    }
    ElMessage.success('保存成功')
    visible.value = false
    load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function onDelete(row: any) {
  try {
    await ElMessageBox.confirm(`确定删除用户 ${row.user_name || row.user_id} 的额度记录？`, '确认', { type: 'warning' })
    await api.deleteQuota(row.user_id)
    ElMessage.success('已删除')
    load()
  } catch {}
}

onMounted(load)
</script>

<style scoped>
.form-hint { font-size: 12px; color: var(--m-text-tertiary); margin-top: 4px; }
.muted { color: var(--m-text-tertiary); }
</style>
