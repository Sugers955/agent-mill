<template>
  <div class="page">
    <div class="page-head">
      <span class="page-title">Agent 模板市场</span>
      <el-select v-model="category" placeholder="全部分类" clearable style="width:160px" @change="load">
        <el-option label="全部" value="" />
        <el-option v-for="c in categories" :key="c" :label="categoryLabel(c)" :value="c" />
      </el-select>
    </div>

    <div v-loading="loading" class="template-grid">
      <div v-for="tpl in templates" :key="tpl.id" class="template-card">
        <div class="tpl-icon">{{ tpl.icon || '🤖' }}</div>
        <div class="tpl-category">{{ categoryLabel(tpl.category) }}</div>
        <div class="tpl-name">{{ tpl.name }}</div>
        <div class="tpl-desc">{{ tpl.description }}</div>
        <div class="tpl-meta">
          <span>{{ tpl.agent_count }} 个 Agent</span>
          <span>{{ tpl.usage_count }} 次部署</span>
        </div>
        <div class="tpl-footer">
          <el-button size="small" type="primary" :loading="deploying === tpl.id" @click="onDeploy(tpl)">
            一键部署
          </el-button>
        </div>
      </div>
      <div v-if="!templates.length && !loading" class="empty">暂无可用的模板</div>
    </div>

    <el-dialog v-model="resultVisible" title="部署成功" width="520px">
      <p>模板「{{ deployedName }}」已部署，创建了以下数字员工：</p>
      <el-table :data="deployedAgents" stripe size="small">
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="code" label="编码" />
      </el-table>
      <template #footer>
        <el-button @click="resultVisible = false">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api'

const templates = ref<any[]>([])
const categories = ref<string[]>([])
const category = ref('')
const loading = ref(false)
const deploying = ref<number | null>(null)
const resultVisible = ref(false)
const deployedName = ref('')
const deployedAgents = ref<any[]>([])

const CATEGORY_LABELS: Record<string, string> = {
  hr: '人力资源', sales: '销售', marketing: '营销', finance: '财务',
  admin: '行政后勤', it: 'IT研发', support: '客服', general: '通用',
}

function categoryLabel(c: string) { return CATEGORY_LABELS[c] || c }

async function load() {
  loading.value = true
  try {
    const [tpls, cats] = await Promise.all([
      api.request(`/api/admin/agent-templates${category.value ? `?category=${category.value}` : ''}`),
      api.request('/api/admin/agent-templates/categories'),
    ])
    templates.value = tpls || []
    categories.value = cats || []
  } finally { loading.value = false }
}

async function onDeploy(tpl: any) {
  deploying.value = tpl.id
  try {
    const r = await api.request(`/api/admin/agent-templates/${tpl.id}/deploy`, { method: 'POST' })
    deployedName.value = r.template
    deployedAgents.value = r.agents || []
    resultVisible.value = true
    ElMessage.success(`已创建 ${r.count} 个数字员工`)
    await load()
  } catch { ElMessage.error('部署失败') }
  finally { deploying.value = null }
}

onMounted(load)
</script>

<style scoped>
.template-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px; margin-top: 16px;
}
.template-card {
  background: var(--m-surface); border: 1px solid var(--m-border);
  border-radius: var(--m-radius-lg); padding: 20px;
  display: flex; flex-direction: column; gap: 8px;
  transition: box-shadow .2s;
}
.template-card:hover { box-shadow: var(--m-shadow-2); }
.tpl-icon { font-size: 40px; line-height: 1; }
.tpl-category { font-size: 11px; color: var(--m-primary); font-weight: 600; text-transform: uppercase; letter-spacing: .05em; }
.tpl-name { font-size: 16px; font-weight: 600; color: var(--m-text); }
.tpl-desc { font-size: 13px; color: var(--m-text-secondary); line-height: 1.5; flex: 1; }
.tpl-meta { display: flex; gap: 16px; font-size: 12px; color: var(--m-text-tertiary); }
.tpl-footer { padding-top: 8px; }
.empty { grid-column: 1 / -1; text-align: center; padding: 48px; color: var(--m-text-tertiary); }
</style>
