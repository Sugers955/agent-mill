<template>
  <div class="page">
    <div class="page-head">
      <span class="page-title">工作流</span>
      <el-button type="primary" @click="onCreate">新建工作流</el-button>
    </div>
    <div class="surface">
      <el-table :data="workflows" stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="名称" min-width="200" />
        <el-table-column prop="description" label="描述" min-width="260" show-overflow-tooltip />
        <el-table-column label="状态" width="80">
          <template #default="{ row }"><el-tag :type="row.status==='published'?'success':'info'" size="small">{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="run_count" label="运行" width="60" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text @click="editWorkflow(row)">编辑</el-button>
            <el-button size="small" text @click="runWorkflow(row)">运行</el-button>
            <el-button size="small" text type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'

const router = useRouter()
const workflows = ref<any[]>([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const r = await api.request('/api/admin/workflows')
    workflows.value = r || []
  } finally { loading.value = false }
}

function onCreate() {
  router.push('/admin/workflows/new').catch(() => {})
}

function editWorkflow(wf: any) {
  router.push(`/admin/workflows/${wf.id}`).catch(() => {})
}

async function runWorkflow(wf: any) {
  try {
    await api.request(`/api/admin/workflows/${wf.id}/run`, { method: 'POST' })
    ElMessage.success('工作流已注册，可在 Agent 对话中调用')
    await load()
  } catch { ElMessage.error('运行失败') }
}

async function remove(row: any) {
  try { await ElMessageBox.confirm(`确定删除「${row.name}」？`, '确认') } catch { return }
  await api.request(`/api/admin/workflows/${row.id}`, { method: 'DELETE' })
  ElMessage.success('已删除')
  await load()
}

onMounted(load)
</script>
