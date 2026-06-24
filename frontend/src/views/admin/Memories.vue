<template>
  <div class="page memories-page">
    <div class="page-head">
      <span class="page-title">记忆管理</span>
    </div>

    <!-- 筛选条件 -->
    <div class="filter-bar">
      <el-select v-model="selectedAgentId" placeholder="选择数字员工" clearable style="width: 200px">
        <el-option v-for="a in agents" :key="a.id" :label="a.name" :value="a.id" />
      </el-select>
      <el-select v-model="selectedUserId" placeholder="选择用户" clearable style="width: 200px">
        <el-option v-for="u in users" :key="u.id" :label="u.username" :value="u.id" />
      </el-select>
      <el-button type="primary" @click="loadMemories" :disabled="!selectedAgentId || !selectedUserId">
        查询
      </el-button>
    </div>

    <!-- 记忆列表 -->
    <el-table :data="memories" stripe v-loading="loading" style="margin-top: 16px">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="memory_type" label="类型" width="100">
        <template #default="{ row }">
          <el-tag :type="getTypeTag(row.memory_type)" size="small">
            {{ getTypeLabel(row.memory_type) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="content" label="内容" show-overflow-tooltip />
      <el-table-column prop="importance" label="重要性" width="100">
        <template #default="{ row }">
          <el-progress :percentage="Math.round(row.importance * 100)" :stroke-width="8" />
        </template>
      </el-table-column>
      <el-table-column prop="access_count" label="访问次数" width="80" />
      <el-table-column prop="created_at" label="创建时间" width="160">
        <template #default="{ row }">
          {{ formatTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button size="small" text @click="editMemory(row)">编辑</el-button>
          <el-button size="small" text type="danger" @click="deleteMemory(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="dialogVisible" title="编辑记忆" width="500px">
      <el-form :model="editingMemory" label-width="80px">
        <el-form-item label="类型">
          <el-select v-model="editingMemory.memory_type" style="width: 100%">
            <el-option label="偏好" value="preference" />
            <el-option label="事实" value="fact" />
            <el-option label="决策" value="decision" />
            <el-option label="上下文" value="context" />
          </el-select>
        </el-form-item>
        <el-form-item label="内容">
          <el-input v-model="editingMemory.content" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="重要性">
          <el-slider v-model="importanceValue" :min="0" :max="100" :step="1" show-input />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveMemory">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'

const agents = ref<any[]>([])
const users = ref<any[]>([])
const selectedAgentId = ref<number | null>(null)
const selectedUserId = ref<number | null>(null)
const memories = ref<any[]>([])
const loading = ref(false)

const dialogVisible = ref(false)
const editingMemory = ref<any>({})
const importanceValue = ref(50)

const typeLabels: Record<string, string> = {
  preference: '偏好',
  fact: '事实',
  decision: '决策',
  context: '上下文',
}

const typeTags: Record<string, string> = {
  preference: 'success',
  fact: 'info',
  decision: 'warning',
  context: '',
}

function getTypeLabel(type: string) {
  return typeLabels[type] || type
}

function getTypeTag(type: string) {
  return typeTags[type] || ''
}

function formatTime(t: string) {
  if (!t) return ''
  const d = new Date(t)
  if (isNaN(d.getTime())) return t
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadAgents() {
  const res = await api.agents()
  agents.value = res.items || res
}

async function loadUsers() {
  const res = await api.users({ limit: 200 })
  users.value = res.items || res
}

async function loadMemories() {
  if (!selectedAgentId.value || !selectedUserId.value) return
  
  loading.value = true
  try {
    const res = await api.memories(selectedAgentId.value, selectedUserId.value || undefined)
    memories.value = res.items || res
  } catch (e: any) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function editMemory(row: any) {
  editingMemory.value = { ...row }
  importanceValue.value = Math.round(row.importance * 100)
  dialogVisible.value = true
}

async function saveMemory() {
  try {
    await api.updateMemory(editingMemory.value.id, {
      ...editingMemory.value,
      importance: importanceValue.value / 100,
    })
    ElMessage.success('保存成功')
    dialogVisible.value = false
    loadMemories()
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  }
}

async function deleteMemory(row: any) {
  try {
    await ElMessageBox.confirm('确定删除这条记忆？', '确认')
    await api.deleteMemory(row.id)
    ElMessage.success('删除成功')
    loadMemories()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.message || '删除失败')
    }
  }
}

watch(selectedAgentId, () => {
  memories.value = []
})

onMounted(() => {
  loadAgents()
  loadUsers()
})
</script>

<style scoped>
.memories-page {
  padding: 20px;
}

.page-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
}

.filter-bar {
  display: flex;
  gap: 12px;
  align-items: center;
}
</style>
