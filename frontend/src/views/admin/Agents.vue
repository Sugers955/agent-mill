<template>
  <div class="page">
    <div class="page-head"><span class="page-title">智能体管理</span>
      <el-button type="primary" @click="openCreate">新建智能体</el-button>
    </div>
    <el-table :data="rows" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column label="名称" min-width="200">
        <template #default="{ row }">
          <div style="display:flex;align-items:center;gap:8px">
            <span style="font-weight:500">{{ row.name }}</span>
            <el-tag v-if="row.is_default" type="primary" size="small" effect="light">默认</el-tag>
          </div>
          <div style="font-size:12px;color:var(--m-text-secondary);font-family:'Roboto Mono',monospace">{{ row.code }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="描述" show-overflow-tooltip min-width="180" />
      <el-table-column label="默认模型" width="180" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.default_model_id">{{ modelLabel(row.default_model_id) }}</span>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="技能" width="80" align="center">
        <template #default="{ row }">
          <span :class="{ muted: !row.skill_ids?.length }">{{ row.skill_ids?.length || 0 }}</span>
        </template>
      </el-table-column>
      <el-table-column label="MCP" width="80" align="center">
        <template #default="{ row }">
          <span :class="{ muted: !row.mcp_ids?.length }">{{ row.mcp_ids?.length || 0 }}</span>
        </template>
      </el-table-column>
      <el-table-column label="启用" width="80">
        <template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '是' : '否' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button size="small" text @click="openEdit(row)">编辑</el-button>
          <el-button size="small" text type="danger" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="visible" :title="editing ? '编辑智能体' : '新建智能体'" width="760px">
      <el-form :model="form" label-width="120px">
        <el-form-item label="编码"><el-input v-model="form.code" /></el-form-item>
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="System Prompt"><el-input v-model="form.system_prompt" type="textarea" :rows="4" /></el-form-item>
        <el-form-item label="默认模型">
          <el-select v-model="form.default_model_id" clearable>
            <el-option v-for="m in models" :key="m.id" :label="m.code" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="降级模型">
          <el-select v-model="form.fallback_model_id" clearable>
            <el-option v-for="m in models" :key="m.id" :label="m.code" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="挂载 Skills">
          <el-select v-model="form.skill_ids" multiple style="width:100%">
            <el-option v-for="s in skills" :key="s.id" :label="`${s.code} (${s.type})`" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="挂载 MCP">
          <el-select v-model="form.mcp_ids" multiple style="width:100%">
            <el-option v-for="m in mcps" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="可见角色">
          <el-select v-model="form.role_ids" multiple style="width:100%">
            <el-option v-for="r in roles" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="允许扩展名">
          <el-input v-model="extText" placeholder="逗号分隔,如: pdf,docx,png. 留空=不限" />
        </el-form-item>
        <el-form-item label="设为默认">
          <el-switch v-model="form.is_default" />
          <span style="margin-left:12px;font-size:12px;color:var(--m-text-secondary)">勾选后将取消其它智能体的默认状态。新用户首次进入对话会自动使用默认智能体。</span>
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
import { ref, onMounted, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'

const rows = ref<any[]>([])
const models = ref<any[]>([])
const skills = ref<any[]>([])
const mcps = ref<any[]>([])
const roles = ref<any[]>([])
const visible = ref(false)
const editing = ref<any | null>(null)
const form = reactive<any>(emptyForm())
const extText = ref('')

function emptyForm() {
  return {
    code: '', name: '', description: '', icon: '', system_prompt: '',
    default_model_id: null, fallback_model_id: null,
    upload_policy_json: {}, enabled: true, is_default: false,
    skill_ids: [], mcp_ids: [], role_ids: [],
  }
}

async function load() {
  ;[rows.value, models.value, skills.value, mcps.value, roles.value] = await Promise.all([
    api.agents(), api.models(), api.skills(), api.mcps(), api.roles(),
  ])
}
onMounted(load)

function modelLabel(id: number) {
  const m = models.value.find((x: any) => x.id === id)
  return m ? (m.code || m.model_id || `#${id}`) : `#${id}`
}

function openCreate() {
  editing.value = null
  Object.assign(form, emptyForm())
  extText.value = ''
  visible.value = true
}
function openEdit(row: any) {
  editing.value = row
  Object.assign(form, JSON.parse(JSON.stringify(row)))
  extText.value = (row.upload_policy_json?.allowed_ext || []).join(',')
  visible.value = true
}
async function onSubmit() {
  const ext = extText.value.split(',').map(s => s.trim()).filter(Boolean)
  form.upload_policy_json = ext.length ? { allowed_ext: ext } : {}
  if (editing.value) await api.updateAgent(editing.value.id, form)
  else await api.createAgent(form)
  visible.value = false
  ElMessage.success('保存成功')
  await load()
}
async function onDelete(row: any) {
  try { await ElMessageBox.confirm(`删除 ${row.code}?`, '确认', { type: 'warning' }); await api.deleteAgent(row.id); await load() } catch {}
}
</script>

<style scoped>
.muted { color: var(--m-text-tertiary); }
</style>
