<template>
  <div class="status-timeline">
    <h3 v-if="schema.title" class="title">{{ schema.title }}</h3>
    <el-timeline>
      <el-timeline-item
        v-for="(s, i) in steps"
        :key="i"
        :type="iconType(s.status)"
        :timestamp="s.time || ''"
        :hollow="s.status === 'pending'"
      >
        <div class="step-title" :class="s.status">{{ s.title }}</div>
        <div v-if="s.description" class="step-desc">{{ s.description }}</div>
      </el-timeline-item>
    </el-timeline>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ActionDef, UIMessage } from '../types/schema'

const props = defineProps<{ schema: UIMessage; onAction?: (a: ActionDef, params: any, ctx: any) => void }>()

interface Step { title: string; description?: string; status?: 'done' | 'current' | 'pending'; time?: string }

const steps = computed<Step[]>(() => props.schema.data_model.steps || [])

function iconType(s?: string) {
  if (s === 'done') return 'success'
  if (s === 'current') return 'primary'
  return 'info'
}
</script>

<style scoped>
.status-timeline { display:flex; flex-direction: column; gap: 8px; }
.title { margin: 0 0 6px; font-size: 16px; font-weight: 600; }
.step-title { font-weight: 500; font-size: 14px; }
.step-title.current { color: var(--m-primary); }
.step-title.done { color: var(--m-success); }
.step-title.pending { color: var(--m-text-tertiary); }
.step-desc { font-size: 12px; color: var(--m-text-secondary); margin-top: 2px; }
</style>
