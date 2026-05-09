<template>
  <div class="page">
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
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button size="small" text @click="openEdit(row)">编辑</el-button>
          <el-button size="small" text type="danger" :disabled="isProtected(row.code)" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

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
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'

const PROTECTED = new Set(['admin', 'operator', 'user'])

const rows = ref<any[]>([])
const loading = ref(false)
const visible = ref(false)
const editing = ref<any | null>(null)
const formRef = ref<any>(null)
const form = reactive<any>({ code: '', name: '', description: '' })

const rules = {
  code: [
    { required: true, message: '请输入编码', trigger: 'blur' },
    { min: 2, max: 32, message: '2-32 字符', trigger: 'blur' },
  ],
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
}

function isProtected(code: string) { return PROTECTED.has(code) }

async function load() {
  loading.value = true
  try { rows.value = await api.roles() }
  finally { loading.value = false }
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
.page-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.mono { font-family: 'Roboto Mono', monospace; font-size: 12px; }
</style>
