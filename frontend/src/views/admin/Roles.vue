<template>
  <div class="page roles-page">
    <div class="page-head">
      <span class="page-title">角色管理</span>
      <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>新建角色</el-button>
    </div>

    <el-table :data="rows" stripe v-loading="loading">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="code" label="编码" width="160">
        <template #default="{ row }">
          <code class="mono">{{ row.code }}</code>
          <el-tag v-if="isProtected(row.code)" size="small" effect="light" style="margin-left:6px">内置</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="名称" width="180" />
      <el-table-column prop="description" label="描述" show-overflow-tooltip />
      <el-table-column label="可用数字员工" width="120">
        <template #default="{ row }">
          <el-tag size="small">{{ getAgentCount(row.id) }} 个</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button size="small" text @click="openEdit(row)">编辑</el-button>
          <el-button size="small" text @click="openAgents(row)">授权</el-button>
          <el-button size="small" text type="danger" :disabled="isProtected(row.code)" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 编辑角色弹窗 -->
    <el-dialog v-model="visible" :title="editing ? '编辑角色' : '新建角色'" width="480px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="编码" prop="code">
          <el-input v-model="form.code" :disabled="!!editing" placeholder="2-32 字符,字母数字下划线" />
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" @click="onSubmit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 数字员工授权弹窗 -->
    <el-dialog v-model="agentsVisible" :title="`授权 - ${agentsRole?.name || ''}`" width="600px">
      <div class="agents-auth-content">
        <div class="agents-auth-header">
          <span class="auth-label">勾选该角色可访问的数字员工：</span>
          <el-checkbox v-model="selectAll" @change="onSelectAll">全选</el-checkbox>
        </div>
        <el-checkbox-group v-model="selectedAgentIds" class="agents-checkbox-group">
          <div v-for="agent in allAgents" :key="agent.id" class="agent-checkbox-item">
            <el-checkbox :value="agent.id" :label="agent.id">
              <div class="agent-checkbox-content">
                <div class="agent-checkbox-avatar" :style="getAvatarStyle(agent)">
                  <img v-if="agent.icon_url" :src="agent.icon_url" alt="" class="avatar-img" />
                  <span v-else class="avatar-text">{{ getInitials(agent.name) }}</span>
                </div>
                <div class="agent-checkbox-info">
                  <span class="agent-checkbox-name">{{ agent.name }}</span>
                  <span class="agent-checkbox-code">{{ agent.code }}</span>
                </div>
              </div>
            </el-checkbox>
          </div>
        </el-checkbox-group>
      </div>
      <template #footer>
        <el-button @click="agentsVisible = false">取消</el-button>
        <el-button type="primary" :loading="agentsSaving" @click="onSaveAgents">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'
import { GRADIENTS } from '@/shared/constants'

const PROTECTED = new Set(['admin', 'operator', 'user'])

const rows = ref<any[]>([])
const loading = ref(false)
const visible = ref(false)
const editing = ref<any | null>(null)
const formRef = ref<any>(null)
const form = reactive<any>({ code: '', name: '', description: '' })

// 数字员工授权相关
const agentsVisible = ref(false)
const agentsRole = ref<any>(null)
const allAgents = ref<any[]>([])
const selectedAgentIds = ref<number[]>([])
const agentsSaving = ref(false)

// 角色-数字员工映射缓存
const roleAgentMap = ref<Record<number, number[]>>({})

const selectAll = computed({
  get: () => selectedAgentIds.value.length === allAgents.value.length && allAgents.value.length > 0,
  set: () => {}
})

// 渐变色板

function getAvatarStyle(agent: any) {
  if (agent.icon_url) return {}
  const idx = (agent.id || 0) % GRADIENTS.length
  return { background: GRADIENTS[idx] }
}

function getInitials(name: string) {
  if (!name) return '?'
  return name.charAt(0).toUpperCase()
}

const rules = {
  code: [
    { required: true, message: '请输入编码', trigger: 'blur' },
    { min: 2, max: 32, message: '2-32 字符', trigger: 'blur' },
  ],
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
}

function isProtected(code: string) { return PROTECTED.has(code) }

function getAgentCount(roleId: number) {
  return roleAgentMap.value[roleId]?.length || 0
}

function onSelectAll(val: any) {
  if (val) {
    selectedAgentIds.value = allAgents.value.map(a => a.id)
  } else {
    selectedAgentIds.value = []
  }
}

async function load() {
  loading.value = true
  try {
    const res = await api.roles()
    rows.value = res.items || res
    // 加载每个角色的数字员工授权
    await loadRoleAgentMap()
  } finally {
    loading.value = false
  }
}

async function loadRoleAgentMap() {
  const map: Record<number, number[]> = {}
  for (const role of rows.value) {
    try {
      const result = await api.getRoleAgents(role.id)
      map[role.id] = result.agent_ids || []
    } catch {
      map[role.id] = []
    }
  }
  roleAgentMap.value = map
}

onMounted(load)

function openCreate() {
  editing.value = null
  Object.assign(form, { code: '', name: '', description: '' })
  visible.value = true
}

function openEdit(row: any) {
  editing.value = row
  Object.assign(form, { code: row.code, name: row.name, description: row.description || '' })
  visible.value = true
}

async function openAgents(row: any) {
  agentsRole.value = row
  selectedAgentIds.value = roleAgentMap.value[row.id] || []
  
  // 加载所有数字员工
  if (allAgents.value.length === 0) {
    try {
      const res = await api.agents()
      allAgents.value = res.items || res
    } catch {
      allAgents.value = []
    }
  }
  
  agentsVisible.value = true
}

async function onSubmit() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  try {
    if (editing.value) {
      await api.updateRole(editing.value.id, { name: form.name, description: form.description })
    } else {
      await api.createRole(form)
    }
    visible.value = false
    ElMessage.success('保存成功')
    await load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  }
}

async function onSaveAgents() {
  if (!agentsRole.value) return
  agentsSaving.value = true
  try {
    await api.updateRoleAgents(agentsRole.value.id, selectedAgentIds.value)
    roleAgentMap.value[agentsRole.value.id] = [...selectedAgentIds.value]
    agentsVisible.value = false
    ElMessage.success('授权保存成功')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    agentsSaving.value = false
  }
}

async function onDelete(row: any) {
  try {
    await ElMessageBox.confirm(`删除角色 "${row.name}"?`, '确认', { type: 'warning' })
    await api.deleteRole(row.id)
    ElMessage.success('已删除')
    await load()
  } catch (e: any) {
    if (e?.response) ElMessage.error(e.response.data?.detail || '删除失败')
  }
}
</script>

<style scoped>
.roles-page {
  background: var(--m-bg);
  min-height: 100vh;
}

.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--m-text);
}

.mono {
  font-family: 'Roboto Mono', monospace;
  font-size: 12px;
}

/* 数字员工授权弹窗 */
.agents-auth-content {
  max-height: 500px;
  overflow-y: auto;
}

.agents-auth-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--m-border);
}

.auth-label {
  font-size: 14px;
  color: var(--m-text-secondary);
}

.agents-checkbox-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.agent-checkbox-item {
  padding: 8px 12px;
  border: 1px solid var(--m-border);
  border-radius: 8px;
  transition: all 0.2s ease;
}

.agent-checkbox-item:hover {
  border-color: #6366F1;
  background: rgba(99, 102, 241, 0.02);
}

.agent-checkbox-item :deep(.el-checkbox__label) {
  width: 100%;
}

.agent-checkbox-content {
  display: flex;
  align-items: center;
  gap: 12px;
}

.agent-checkbox-avatar {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  overflow: hidden;
  flex-shrink: 0;
}

.agent-checkbox-avatar .avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.agent-checkbox-avatar .avatar-text {
  font-size: 14px;
  font-weight: 600;
  color: var(--m-on-primary, #FFFFFF);
}

.agent-checkbox-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.agent-checkbox-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--m-text);
}

.agent-checkbox-code {
  font-size: 12px;
  color: var(--m-text-tertiary);
  font-family: 'Roboto Mono', monospace;
}
</style>
