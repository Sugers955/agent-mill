<template>
  <div class="page">
    <div class="page-head"><span class="page-title">模型管理</span>
      <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>新建模型</el-button>
    </div>
    <el-table :data="rows" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="code" label="编码" />
      <el-table-column label="供应商" width="160">
        <template #default="{ row }">
          <el-tag :type="providerTagType(row.provider)" effect="light">
            {{ providerLabel(row.provider) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="model_id" label="模型ID" />
      <el-table-column label="API Key" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.has_api_key" type="success">已配置</el-tag>
          <el-tag v-else type="info">未配置</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="enabled" label="启用" width="80">
        <template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '是' : '否' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="240">
        <template #default="{ row }">
          <el-button v-if="row.has_api_key" size="small" text @click="onTest(row)" :loading="testing[row.id]"><el-icon><MagicStick /></el-icon>测试</el-button>
          <el-button size="small" text @click="openEdit(row)">编辑</el-button>
          <el-button size="small" text type="danger" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="testVisible" title="模型测试" width="640px">
      <div v-if="testResult">
        <div class="qa-block">
          <div class="qa-label">问题</div>
          <div class="qa-content">{{ testResult.question }}</div>
        </div>
        <div class="qa-block answer">
          <div class="qa-label">回答</div>
          <div class="qa-content">{{ testResult.answer }}</div>
        </div>
        <div class="qa-stats">
          <span>输入 {{ testResult.tokens_in }} tokens</span>
          <span>输出 {{ testResult.tokens_out }} tokens</span>
        </div>
      </div>
      <template #footer><el-button @click="testVisible = false">关闭</el-button></template>
    </el-dialog>

    <el-dialog v-model="visible" :title="editing ? '编辑模型' : '新建模型'" width="640px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="供应商">
          <div class="provider-grid">
            <div
              v-for="p in PROVIDERS"
              :key="p.value"
              :class="['provider-card', { active: form.provider === p.value }]"
              @click="onProviderSelect(p.value)"
            >
              <div class="provider-name">{{ p.label }}</div>
              <div class="provider-hint">{{ p.hint }}</div>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="编码"><el-input v-model="form.code" placeholder="自定义,如 deepseek-chat-prod" /></el-form-item>
        <el-form-item label="模型ID">
          <el-input v-model="form.model_id" :placeholder="modelIdPlaceholder">
            <template v-if="modelIdSuggestions.length" #append>
              <el-dropdown trigger="click" @command="form.model_id = $event">
                <el-button text>常用 ▾</el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item v-for="m in modelIdSuggestions" :key="m" :command="m">{{ m }}</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item label="Base URL">
          <el-input v-model="form.base_url" :placeholder="basePlaceholder" />
          <div v-if="presetBase" style="font-size:12px;color:var(--m-text-secondary);margin-top:4px">
            留空则使用预设: <code>{{ presetBase }}</code>
          </div>
        </el-form-item>
        <el-form-item label="API Key"><el-input v-model="form.api_key" :placeholder="editing ? '留空则不改' : '从供应商控制台获取'" show-password /></el-form-item>
        <el-form-item label="Max Tokens"><el-input-number v-model="form.max_tokens" :min="1024" :max="200000" :step="1024" /></el-form-item>

        <el-form-item label="高级参数">
          <div style="display:flex;gap:6px;margin-bottom:6px;flex-wrap:wrap">
            <el-button size="small" @click="applyPreset('disable_thinking')">关闭思考</el-button>
            <el-button size="small" @click="applyPreset('enable_thinking')">开启思考</el-button>
            <el-button size="small" @click="extraText = '{}'">清空</el-button>
          </div>
          <el-input v-model="extraText" type="textarea" :rows="4"
                    placeholder='额外参数 JSON,会作为 extra_body 透传给模型 API。例如关闭思考: {"enable_thinking": false}' />
          <div style="font-size:12px;color:var(--m-text-secondary);margin-top:4px">
            常见关思考写法 ——
            <strong>Qwen3</strong>: <code>{"enable_thinking": false}</code> ·
            <strong>DeepSeek V3.2/V4 hybrid</strong>: <code>{"thinking": {"type": "disabled"} }</code> ·
            <strong>GLM-4.5</strong>: <code>{"thinking": {"type": "disabled"} }</code>
          </div>
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
import { ref, onMounted, reactive, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'

const PROVIDERS = [
  { value: 'anthropic', label: 'Anthropic', hint: 'Claude (官方 SDK + 技能/连接器)', base: '', models: ['claude-opus-4-6', 'claude-sonnet-4-6', 'claude-haiku-4-5-20251001'] },
  { value: 'deepseek',  label: 'DeepSeek',  hint: 'OpenAI 兼容', base: 'https://api.deepseek.com/v1', models: ['deepseek-v4-flash', 'deepseek-v4-pro'] },
  { value: 'qwen',      label: '通义千问 Qwen', hint: '阿里云 DashScope', base: 'https://dashscope.aliyuncs.com/compatible-mode/v1', models: ['qwen-max-2026', 'qwen-plus', 'qwen-turbo', 'qwen3-coder-plus'] },
  { value: 'glm',       label: '智谱 GLM',  hint: '智谱 AI', base: 'https://open.bigmodel.cn/api/paas/v4', models: ['glm-4-plus', 'glm-4-air', 'glm-4-flash', 'glm-4-long'] },
  { value: 'openai',    label: 'OpenAI',    hint: '官方 OpenAI', base: 'https://api.openai.com/v1', models: ['gpt-4o', 'gpt-4o-mini', 'o3-mini', 'o1'] },
  { value: 'openai-compatible', label: '其他 (OpenAI 兼容)', hint: '自填 base_url', base: '', models: [] },
]

const PROVIDER_MAP = Object.fromEntries(PROVIDERS.map(p => [p.value, p]))

const rows = ref<any[]>([])
const visible = ref(false)
const editing = ref<any | null>(null)
const form = reactive<any>(emptyForm())

function emptyForm() {
  return { code: '', provider: 'anthropic', model_id: '', base_url: '', api_key: '', max_tokens: 8192, enabled: true, extra_params: {} }
}

const extraText = ref('{}')

const DISABLE_THINKING_PRESETS: Record<string, any> = {
  qwen: { enable_thinking: false },
  deepseek: { thinking: { type: 'disabled' } },
  glm: { thinking: { type: 'disabled' } },
  anthropic: { thinking: { type: 'disabled' } },
  openai: {},
  'openai-compatible': { enable_thinking: false },
}
const ENABLE_THINKING_PRESETS: Record<string, any> = {
  qwen: { enable_thinking: true },
  deepseek: { thinking: { type: 'enabled' } },
  glm: { thinking: { type: 'enabled' } },
  anthropic: { thinking: { type: 'enabled' } },
  openai: {},
  'openai-compatible': { enable_thinking: true },
}

function applyPreset(kind: 'disable_thinking' | 'enable_thinking') {
  const map = kind === 'disable_thinking' ? DISABLE_THINKING_PRESETS : ENABLE_THINKING_PRESETS
  const preset = map[form.provider] || {}
  extraText.value = JSON.stringify(preset, null, 2)
}

const presetBase = computed(() => PROVIDER_MAP[form.provider]?.base || '')
const basePlaceholder = computed(() => presetBase.value || '自定义 OpenAI 兼容地址')
const modelIdSuggestions = computed(() => PROVIDER_MAP[form.provider]?.models || [])
const modelIdPlaceholder = computed(() => modelIdSuggestions.value[0] || '模型 ID')

function providerLabel(v: string) { return PROVIDER_MAP[v]?.label || v }
function providerTagType(v: string) {
  return ({ anthropic: 'warning', deepseek: 'primary', qwen: 'success', glm: 'info', openai: 'primary' } as any)[v] || ''
}

async function load() {
  const res = await api.models()
  rows.value = res.items || res
}
onMounted(load)

function openCreate() { editing.value = null; Object.assign(form, emptyForm()); extraText.value = '{}'; visible.value = true }
function openEdit(row: any) {
  editing.value = row
  Object.assign(form, { ...row, api_key: '' })
  extraText.value = JSON.stringify(row.extra_params || {}, null, 2)
  visible.value = true
}

function onProviderSelect(v: string) {
  form.provider = v
  // auto-fill base_url and a default model_id when empty
  const p = PROVIDER_MAP[v]
  if (p && (!form.base_url || form.base_url === presetBase.value)) form.base_url = p.base
  if (p && !form.model_id && p.models[0]) form.model_id = p.models[0]
}

async function onSubmit() {
  if (!form.code || !form.model_id) { ElMessage.error('请填写编码和模型 ID'); return }
  let parsedExtra: any = {}
  try { parsedExtra = JSON.parse(extraText.value || '{}') }
  catch { ElMessage.error('高级参数 JSON 格式错误'); return }
  const payload: any = { ...form, extra_params: parsedExtra }
  if (editing.value && !payload.api_key) delete payload.api_key
  if (editing.value) await api.updateModel(editing.value.id, payload)
  else await api.createModel(payload)
  visible.value = false
  ElMessage.success('保存成功')
  await load()
}
async function onDelete(row: any) {
  try { await ElMessageBox.confirm(`删除 ${row.code}?`, '确认', { type: 'warning' }); await api.deleteModel(row.id); await load() } catch {}
}

const testing = reactive<Record<number, boolean>>({})
const testVisible = ref(false)
const testResult = ref<any>(null)
async function onTest(row: any) {
  if (!row.has_api_key) {
    ElMessage.warning('请先配置 API Key')
    return
  }
  testing[row.id] = true
  try {
    testResult.value = await api.testModel(row.id)
    testVisible.value = true
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '测试失败')
  } finally { testing[row.id] = false }
}
</script>

<style scoped>
.provider-grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; width: 100%;
}
.provider-card {
  padding: 12px;
  border: 1px solid var(--m-border); border-radius: var(--m-radius);
  cursor: pointer; transition: all .15s;
  background: var(--m-surface);
}
.provider-card:hover { border-color: var(--m-primary); }
.provider-card.active {
  border-color: var(--m-primary); background: var(--m-primary-soft);
  box-shadow: 0 0 0 1px var(--m-primary) inset;
}
.provider-name { font-size: 13px; font-weight: 600; color: var(--m-text); }
.provider-hint { font-size: 11px; color: var(--m-text-secondary); margin-top: 2px; }

.qa-block { padding: 14px 16px; border-radius: var(--m-radius); background: var(--m-surface-variant); margin-bottom: 12px; }
.qa-block.answer { background: var(--m-primary-soft); }
.qa-label { font-size: 11px; font-weight: 600; color: var(--m-text-secondary); text-transform: uppercase; letter-spacing: .06em; margin-bottom: 6px; }
.qa-content { font-size: 14px; line-height: 1.6; white-space: pre-wrap; word-break: break-word; color: var(--m-text); }
.qa-stats { display: flex; gap: 16px; font-size: 12px; color: var(--m-text-secondary); margin-top: 8px; }
</style>
