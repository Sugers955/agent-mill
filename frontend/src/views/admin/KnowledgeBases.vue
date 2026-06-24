<template>
  <div class="page">
    <div class="page-head">
      <span class="page-title">知识库</span>
      <el-button type="primary" @click="showCreate = true">新建知识库</el-button>
    </div>

    <div class="surface">
      <el-table :data="bases" stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="名称" min-width="200" />
        <el-table-column prop="description" label="描述" min-width="260" show-overflow-tooltip />
        <el-table-column label="文档数" width="80">
          <template #default="{ row }">{{ row.document_count || 0 }}</template>
        </el-table-column>
        <el-table-column label="分块数" width="80">
          <template #default="{ row }">{{ row.chunk_count || 0 }}</template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text @click="viewDetail(row)">管理</el-button>
            <el-button size="small" text type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="showCreate" title="新建知识库" width="460px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="知识库名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="描述这个知识库的用途" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="onCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'

const router = useRouter()
const bases = ref<any[]>([])
const loading = ref(false)
const showCreate = ref(false)
const creating = ref(false)
const form = ref({ name: '', description: '' })

async function load() {
  loading.value = true
  try {
    const res = await api.request('/api/admin/knowledge/bases')
    bases.value = res || []
  } finally { loading.value = false }
}

function viewDetail(row: any) {
  router.push(`/admin/knowledge/${row.id}`).catch(() => {})
}

async function onCreate() {
  if (!form.value.name) { ElMessage.warning('请输入名称'); return }
  creating.value = true
  try {
    await api.request('/api/admin/knowledge/bases', { method: 'POST', data: { name: form.value.name, description: form.value.description } })
    ElMessage.success('已创建')
    showCreate.value = false
    form.value = { name: '', description: '' }
    await load()
  } finally { creating.value = false }
}

async function remove(row: any) {
  try { await ElMessageBox.confirm(`确定删除知识库「${row.name}」？`, '确认') } catch { return }
  await api.request(`/api/admin/knowledge/bases/${row.id}`, { method: 'DELETE' })
  ElMessage.success('已删除')
  await load()
}

onMounted(load)
</script>
