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
        <el-form-item label="描述">
          <div class="polish-wrap">
            <el-input v-model="form.description" type="textarea" :rows="3"
                      placeholder="一句话介绍这个智能体；可点击右下角的「✨ AI 润色」自动生成简介 + 2 个示例问题" />
            <button type="button" class="polish-btn"
                    :disabled="polishing.description"
                    @click="onPolish('description')">
              <span v-if="polishing.description">润色中…</span>
              <span v-else>✨ AI 润色</span>
            </button>
          </div>
        </el-form-item>
        <el-form-item label="System Prompt">
          <div class="polish-wrap">
            <el-input v-model="form.system_prompt" type="textarea" :rows="6"
                      placeholder="给智能体的系统提示词；可点击右下角的「✨ AI 润色」让 AI 帮你结构化" />
            <button type="button" class="polish-btn"
                    :disabled="polishing.system_prompt"
                    @click="onPolish('system_prompt')">
              <span v-if="polishing.system_prompt">润色中…</span>
              <span v-else>✨ AI 润色</span>
            </button>
          </div>
        </el-form-item>
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
        <el-form-item label="最大轮次">
          <el-input-number v-model="form.max_turns" :min="1" :max="100" :step="1" controls-position="right" />
          <span style="margin-left:8px;font-size:12px;color:var(--m-text-secondary)">轮 · 一次对话内允许的工具调用循环上限,默认 15</span>
        </el-form-item>
        <el-form-item label="努力程度">
          <el-select v-model="form.effort" style="width:220px">
            <el-option label="low — 轻量推理,响应快" value="low" />
            <el-option label="medium — 平衡推理（默认）" value="medium" />
            <el-option label="high — 深入分析,适合重构/调试" value="high" />
            <el-option label="xhigh — 扩展推理深度（推荐 Opus 4.7）" value="xhigh" />
            <el-option label="max — 最大推理深度,多步骤问题" value="max" />
          </el-select>
        </el-form-item>
        <el-form-item label="挂载 Skills">
          <el-select v-model="form.skill_ids" multiple style="width:100%">
            <el-option v-for="s in skills" :key="s.id" :label="`${s.code} (${s.type})`" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="挂载 Packs">
          <el-select v-model="form.pack_ids" multiple style="width:100%">
            <el-option v-for="p in packs" :key="p.id" :label="`${p.code} @ ${p.version}`" :value="p.id" />
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
        <el-divider style="margin:16px 0 8px"><span style="font-size:12px;color:var(--m-text-secondary)">文件上传策略</span></el-divider>
        <el-form-item label="允许扩展名">
          <el-input v-model="extText" placeholder="逗号分隔,如: pdf,docx,png. 留空=不限" />
        </el-form-item>
        <el-form-item label="单文件大小">
          <el-input-number v-model="maxSizeMb" :min="0" :max="500" :step="5" controls-position="right" />
          <span style="margin-left:8px;font-size:12px;color:var(--m-text-secondary)">MB · 0 表示用全局默认</span>
        </el-form-item>
        <el-form-item label="单次发送上限">
          <el-input-number v-model="maxFilesPerSend" :min="0" :max="50" :step="1" controls-position="right" />
          <span style="margin-left:8px;font-size:12px;color:var(--m-text-secondary)">个 · 一次发送最多带几个文件,0 表示不限</span>
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
const packs = ref<any[]>([])
const roles = ref<any[]>([])
const visible = ref(false)
const editing = ref<any | null>(null)
const form = reactive<any>(emptyForm())
const extText = ref('')
const maxSizeMb = ref<number>(0)
const maxFilesPerSend = ref<number>(0)
const polishing = reactive({ description: false, system_prompt: false })

async function onPolish(kind: 'description' | 'system_prompt') {
  if (polishing[kind]) return
  polishing[kind] = true
  try {
    const r = await api.polishAgentText({
      kind,
      text: (form as any)[kind] || '',
      agent_name: form.name || undefined,
      model_id: form.default_model_id || undefined,
    })
    if (r?.text) {
      ;(form as any)[kind] = r.text
      ElMessage.success('已润色')
    } else {
      ElMessage.warning('润色返回为空')
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '润色失败')
  } finally {
    polishing[kind] = false
  }
}

function emptyForm() {
  return {
    code: '', name: '', description: '', icon: '', system_prompt: '',
    default_model_id: null, fallback_model_id: null,
    upload_policy_json: {}, max_turns: 15, effort: 'low',
    enabled: true, is_default: false,
    skill_ids: [], mcp_ids: [], pack_ids: [], role_ids: [],
  }
}

async function load() {
  ;[rows.value, models.value, skills.value, mcps.value, packs.value, roles.value] = await Promise.all([
    api.agents(), api.models(), api.skills(), api.mcps(), api.packs(), api.roles(),
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
  maxSizeMb.value = 5
  maxFilesPerSend.value = 5
  visible.value = true
}
function openEdit(row: any) {
  editing.value = row
  Object.assign(form, emptyForm(), JSON.parse(JSON.stringify(row)))
  if (form.max_turns == null) form.max_turns = 15
  if (!form.effort) form.effort = 'low'
  const policy = row.upload_policy_json || {}
  extText.value = (policy.allowed_ext || []).join(',')
  maxSizeMb.value = Number(policy.max_size_mb || 0)
  // Backwards-compat: read legacy max_files_per_conv if present
  maxFilesPerSend.value = Number(policy.max_files_per_send || policy.max_files_per_conv || 0)
  visible.value = true
}
async function onSubmit() {
  const ext = extText.value.split(',').map(s => s.trim()).filter(Boolean)
  const policy: any = {}
  if (ext.length) policy.allowed_ext = ext
  if (maxSizeMb.value > 0) policy.max_size_mb = maxSizeMb.value
  if (maxFilesPerSend.value > 0) policy.max_files_per_send = maxFilesPerSend.value
  form.upload_policy_json = policy
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

/* AI polish — button sits in the bottom-right corner of the textarea */
.polish-wrap { position: relative; width: 100%; }
.polish-btn {
  position: absolute;
  right: 8px; bottom: 8px;
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 999px;
  border: 1px solid #dadce0;
  background: rgba(255, 255, 255, 0.95);
  color: #1a73e8;
  cursor: pointer;
  font-weight: 500;
  letter-spacing: 0.01em;
  transition: background .15s, border-color .15s, box-shadow .15s;
  z-index: 2;
  user-select: none;
}
.polish-btn:hover:not(:disabled) {
  background: #e8f0fe;
  border-color: #aecbfa;
  box-shadow: 0 1px 2px rgba(60,64,67,.1);
}
.polish-btn:disabled { color: #80868b; cursor: progress; }
.polish-wrap :deep(.el-textarea__inner) { padding-bottom: 36px; }
</style>
