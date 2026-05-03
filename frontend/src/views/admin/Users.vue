<template>
  <div class="page">
    <div class="page-head">
      <span class="page-title">用户管理</span>
      <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>新建用户</el-button>
    </div>
    <div class="surface" style="padding:0">
    <el-table :data="users" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="username" label="用户名" />
      <el-table-column prop="display_name" label="姓名" />
      <el-table-column label="角色">
        <template #default="{ row }">{{ row.role.name }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'">{{ row.status === 'active' ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button size="small" text @click="openEdit(row)">编辑</el-button>
          <el-button size="small" text type="danger" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    </div>

    <el-dialog v-model="visible" :title="editing ? '编辑用户' : '新建用户'" width="480px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="90px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :disabled="!!editing" placeholder="3-64 字符" />
        </el-form-item>
        <el-form-item :label="editing ? '新密码' : '密码'" :prop="editing ? 'passwordOpt' : 'password'">
          <el-input v-model="form.password" type="password" :placeholder="editing ? '留空则不改' : '至少 6 位'" show-password />
        </el-form-item>
        <el-form-item label="姓名"><el-input v-model="form.display_name" /></el-form-item>
        <el-form-item label="角色" prop="role_id">
          <el-select v-model="form.role_id" placeholder="请选择角色">
            <el-option v-for="r in roles" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="editing" label="状态">
          <el-select v-model="form.status">
            <el-option label="启用" value="active" />
            <el-option label="停用" value="disabled" />
          </el-select>
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

const users = ref<any[]>([])
const roles = ref<any[]>([])
const visible = ref(false)
const editing = ref<any | null>(null)
const formRef = ref<any>(null)
const form = reactive<any>({ username: '', password: '', display_name: '', role_id: null, status: 'active' })
const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 64, message: '用户名 3-64 字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
  passwordOpt: [
    { validator: (_: any, v: string, cb: any) => (!v || v.length >= 6) ? cb() : cb(new Error('密码至少 6 位')), trigger: 'blur' },
  ],
  role_id: [{ required: true, message: '请选择角色', trigger: 'change' }],
}

async function load() {
  users.value = await api.users()
  roles.value = await api.roles()
}
onMounted(load)

function openCreate() {
  editing.value = null
  Object.assign(form, { username: '', password: '', display_name: '', role_id: roles.value[0]?.id, status: 'active' })
  visible.value = true
}
function openEdit(row: any) {
  editing.value = row
  Object.assign(form, { username: row.username, password: '', display_name: row.display_name, role_id: row.role.id, status: row.status })
  visible.value = true
}
async function onSubmit() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  try {
    if (editing.value) {
      const p: any = { display_name: form.display_name, role_id: form.role_id, status: form.status }
      if (form.password) p.password = form.password
      await api.updateUser(editing.value.id, p)
    } else {
      await api.createUser({ username: form.username, password: form.password, display_name: form.display_name, role_id: form.role_id })
    }
    visible.value = false
    ElMessage.success('保存成功')
    await load()
  } catch {}
}
async function onDelete(row: any) {
  try {
    await ElMessageBox.confirm(`删除 ${row.username}?`, '确认', { type: 'warning' })
    await api.deleteUser(row.id)
    await load()
  } catch {}
}
</script>
