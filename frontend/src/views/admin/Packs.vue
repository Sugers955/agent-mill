<template>
  <div class="page">
    <div class="page-head">
      <span class="page-title">工作流编排</span>
      <el-button type="primary" @click="openCreate">新建</el-button>
    </div>

    <div class="surface" style="padding:0">
      <el-table :data="rows" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="code" label="编码" width="180" />
        <el-table-column prop="name" label="名称" min-width="180" />
        <el-table-column prop="version" label="版本" width="100" />
        <el-table-column prop="description" label="描述" show-overflow-tooltip />
        <el-table-column label="启用" width="90">
          <template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '是' : '否' }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text @click="openEdit(row)">编辑</el-button>
            <el-button size="small" text type="danger" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="visible" :title="editing ? '编辑工作流' : '新建工作流'" width="860px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="编码"><el-input v-model="form.code" placeholder="snake_case, 如 case_investigation_v1" /></el-form-item>
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="版本"><el-input v-model="form.version" placeholder="1.0.0" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="YAML">
          <el-input v-model="form.yaml_text" type="textarea" :rows="18" placeholder="在这里粘贴工作流 YAML 配置" />
        </el-form-item>
        <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" @click="onSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'

const rows = ref<any[]>([])
const visible = ref(false)
const editing = ref<any | null>(null)
const form = reactive<any>(emptyForm())

function emptyForm() {
  return { code: '', name: '', version: '1.0.0', description: '', yaml_text: '', enabled: true }
}

async function load() {
  const res = await api.packs()
  rows.value = res.items || res
}
onMounted(load)

function openCreate() { editing.value = null; Object.assign(form, emptyForm()); visible.value = true }
function openEdit(row: any) { editing.value = row; Object.assign(form, JSON.parse(JSON.stringify(row))); visible.value = true }

async function onSubmit() {
  try {
    if (editing.value) await api.updatePack(editing.value.id, form)
    else await api.createPack(form)
    ElMessage.success('保存成功')
    visible.value = false
    await load()
  } catch (e: any) {
    const d = e?.response?.data?.detail
    if (typeof d === 'string') ElMessage.error(d)
  }
}

async function onDelete(row: any) {
  try {
    await ElMessageBox.confirm(`删除 ${row.name}?`, '确认', { type: 'warning' })
    await api.deletePack(row.id)
    ElMessage.success('已删除')
    await load()
  } catch {}
}
</script>
