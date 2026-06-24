<template>
  <el-drawer
    :model-value="modelValue"
    @update:model-value="(v: boolean) => $emit('update:modelValue', v)"
    :size="drawerSize"
    direction="rtl"
    :title="title"
    :destroy-on-close="false"
  >
    <div v-if="loading" class="state-loading">加载中…</div>
    <div v-else-if="error" class="state-error">{{ error }}</div>
    <div v-else-if="caps" class="cap-wrap">
      <section class="cap-section">
        <div class="sec-head">
          <el-icon><InfoFilled /></el-icon>
          <span>这位员工能帮你做什么</span>
        </div>
        <p class="intro">{{ agentIntro }}</p>
      </section>

      <section v-if="caps.skills?.length" class="cap-section">
        <div class="sec-head">
          <el-icon><MagicStick /></el-icon>
          <span>技能 ({{ caps.skills.length }})</span>
        </div>
        <div class="card-list">
          <div v-for="s in caps.skills" :key="s.id" class="cap-card">
            <div class="cap-card-head">
              <span class="cap-card-title">{{ s.name }}</span>
              <el-tag size="small" effect="light">{{ skillTypeLabel(s.type) }}</el-tag>
            </div>
            <div class="cap-card-body">
              {{ s.user_summary || s.description || '这个能力还没有生成介绍,可请管理员在后台刷新。' }}
            </div>
          </div>
        </div>
      </section>

      <section v-if="caps.mcps?.length" class="cap-section">
        <div class="sec-head">
          <el-icon><Connection /></el-icon>
          <span>外部工具 ({{ caps.mcps.length }})</span>
        </div>
        <div class="card-list">
          <div v-for="m in caps.mcps" :key="m.id" class="cap-card">
            <div class="cap-card-head">
              <span class="cap-card-title">{{ m.name }}</span>
            </div>
            <div class="cap-card-body">
              {{ m.user_summary || '这个外部工具还没有生成介绍,可请管理员在后台刷新。' }}
            </div>
            <div v-if="m.tool_summaries?.length" class="tool-list">
              <div v-for="t in m.tool_summaries" :key="t.name" class="tool-row">
                <span class="tool-dot"></span>
                <div class="tool-text">
                  <span class="tool-label">{{ t.label || t.name }}</span>
                  <span v-if="t.description" class="tool-desc">{{ t.description }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section v-if="caps.packs?.length" class="cap-section">
        <div class="sec-head">
          <el-icon><Collection /></el-icon>
          <span>方案包 ({{ caps.packs.length }})</span>
        </div>
        <div class="card-list">
          <div v-for="p in caps.packs" :key="p.id" class="cap-card">
            <div class="cap-card-head">
              <span class="cap-card-title">{{ p.name }}</span>
              <el-tag size="small" effect="light">v{{ p.version }}</el-tag>
            </div>
            <div class="cap-card-body">
              {{ p.description || '这是一套预设的多步流程,能自动完成一系列工作。' }}
            </div>
          </div>
        </div>
      </section>

      <section v-if="!caps.skills?.length && !caps.mcps?.length && !caps.packs?.length" class="cap-section">
        <p class="intro">该员工目前没有挂载任何技能或外部工具。</p>
      </section>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { InfoFilled, MagicStick, Connection, Collection } from '@element-plus/icons-vue'
import { api } from '@/api'

const props = defineProps<{
  modelValue: boolean
  agentId: number | null
  agentName?: string
}>()
defineEmits<{ 'update:modelValue': [v: boolean] }>()

const caps = ref<any | null>(null)
const loading = ref(false)
const error = ref('')

const drawerSize = computed(() => Math.min(window.innerWidth - 80, 640))
const title = computed(() => {
  if (caps.value?.agent?.name) return `${caps.value.agent.name} · 使用说明`
  if (props.agentName) return `${props.agentName} · 使用说明`
  return '员工能力说明'
})

const agentIntro = computed(() => {
  if (!caps.value) return ''
  const parts: string[] = []
  const descr = caps.value.agent?.description
  if (descr) parts.push(descr)
  const skillN = caps.value.skills?.length || 0
  const mcpN = caps.value.mcps?.length || 0
  const packN = caps.value.packs?.length || 0
  const bits: string[] = []
  if (skillN) bits.push(`${skillN} 项技能`)
  if (mcpN) bits.push(`${mcpN} 个外部工具`)
  if (packN) bits.push(`${packN} 个方案包`)
  if (bits.length) parts.push(`它挂载了 ${bits.join('、')},你可以结合下面的能力向它提问或交付任务。`)
  else parts.push('这是一位通用对话员工,直接向它提问即可。')
  return parts.join(' ')
})

function skillTypeLabel(t: string) {
  return t === 'composite' ? '组合技能' : '原子技能'
}

async function load(id: number) {
  loading.value = true
  error.value = ''
  caps.value = null
  try {
    caps.value = await api.agentCapabilities(id)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || '加载失败'
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.modelValue, props.agentId] as const,
  ([vis, id]) => {
    if (vis && id) load(id)
  },
  { immediate: true },
)
</script>

<style scoped>
.state-loading, .state-error {
  padding: 40px; text-align: center; color: var(--m-text-tertiary);
}
.state-error { color: var(--m-danger); }
.cap-wrap { padding: 8px 20px 32px; display: flex; flex-direction: column; gap: 24px; }
.cap-section { display: flex; flex-direction: column; gap: 10px; }
.sec-head {
  display: flex; align-items: center; gap: 8px;
  font-size: 14px; font-weight: 600; color: var(--m-text);
}
.intro {
  margin: 0; color: var(--m-text-secondary); font-size: 13px; line-height: 1.7;
  background: var(--m-bg-soft); padding: 12px 14px; border-radius: 10px;
}
.card-list { display: flex; flex-direction: column; gap: 10px; }
.cap-card {
  border: 1px solid var(--m-border); border-radius: 10px;
  padding: 12px 14px; background: var(--m-surface);
}
.cap-card-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.cap-card-title { font-weight: 500; color: var(--m-text); }
.cap-card-body {
  color: var(--m-text-secondary); font-size: 13px; line-height: 1.6;
}
.tool-list {
  margin-top: 10px; padding-top: 10px; border-top: 1px dashed var(--m-border);
  display: flex; flex-direction: column; gap: 6px;
}
.tool-row { display: flex; gap: 8px; align-items: flex-start; }
.tool-dot {
  width: 6px; height: 6px; margin-top: 8px; border-radius: 50%;
  background: var(--m-primary); flex-shrink: 0;
}
.tool-text { display: flex; flex-direction: column; gap: 2px; }
.tool-label { font-size: 13px; color: var(--m-text); }
.tool-desc { font-size: 12px; color: var(--m-text-secondary); line-height: 1.5; }
</style>
