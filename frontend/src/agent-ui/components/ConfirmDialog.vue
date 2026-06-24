<template>
  <div class="confirm-dialog">
    <h3 v-if="schema.title" class="title">{{ schema.title }}</h3>
    <el-descriptions :column="1" border size="small">
      <el-descriptions-item v-for="(f, i) in fields" :key="i" :label="f.label">{{ f.value }}</el-descriptions-item>
    </el-descriptions>
    <div class="actions">
      <el-button v-for="a in actions" :key="a.name"
        :type="a.style === 'primary' ? 'primary' : (a.style === 'danger' ? 'danger' : 'default')"
        @click="fire(a)">{{ a.label }}</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ActionDef, UIMessage } from '../types/schema'

const props = defineProps<{ schema: UIMessage; onAction: (a: ActionDef, params: any, ctx: any) => void }>()

const fields = computed<{ label: string; value: any }[]>(() => {
  const arr = props.schema.data_model?.fields
  if (Array.isArray(arr)) return arr
  // Fallback: render data_model itself as kv pairs
  return Object.entries(props.schema.data_model || {})
    .filter(([k]) => !k.startsWith('_'))
    .map(([k, v]) => ({ label: k, value: typeof v === 'object' ? JSON.stringify(v) : v }))
})

const actions = computed<ActionDef[]>(() => props.schema.actions || [])

function fire(a: ActionDef) {
  props.onAction(a, null, { row: props.schema.data_model })
}
</script>

<style scoped>
.confirm-dialog { display: flex; flex-direction: column; gap: 10px; }
.title { margin: 0; font-size: 16px; font-weight: 600; }
.actions { display:flex; gap: 8px; justify-content: flex-end; }
</style>
