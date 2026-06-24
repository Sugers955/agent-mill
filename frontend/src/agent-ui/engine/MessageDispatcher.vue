<template>
  <div class="ui-surface" :data-surface-id="schema.surface_id">
    <div v-if="!isValid" class="fallback">
      <div class="fallback-head">⚠️ 未知 UI Schema,降级显示原始数据</div>
      <pre>{{ rawJson }}</pre>
    </div>
    <component
      v-else-if="comp"
      :is="comp"
      :schema="schema"
      :on-action="onAction"
      @action="onAction"
    />
    <div v-else class="fallback">
      <div class="fallback-head">⚠️ 未注册组件: {{ schema.component_type }}</div>
      <pre>{{ rawJson }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ActionDef, UIMessage } from '../types/schema'
import { isValidSchema } from './SchemaParser'
import { getComponent } from './ComponentRegistry'
import { runAction, type AgentCall } from './ActionRunner'

const props = defineProps<{
  schema: UIMessage
  onAgentCall: AgentCall
}>()

const isValid = computed(() => isValidSchema(props.schema))
const comp = computed(() => isValid.value ? getComponent(props.schema.component_type) : null)
const rawJson = computed(() => JSON.stringify(props.schema, null, 2))

async function onAction(action: ActionDef, params: any = null, ctx: any = {}) {
  // Children may pre-resolve params and pass them in `ctx`. Keep both paths.
  const callCtx = ctx || {}
  if (params != null && typeof params === 'object' && !Array.isArray(params)) {
    callCtx.form = callCtx.form ?? params
  }
  await runAction({
    schema: props.schema,
    action,
    ctx: callCtx,
    onAgentCall: props.onAgentCall,
  })
}
</script>

<style scoped>
.ui-surface {
  background: var(--m-surface);
  border: 1px solid var(--m-border);
  border-radius: var(--m-radius-lg);
  padding: 14px 16px;
  margin: 4px 0;
}
.fallback { font-size: 12px; color: var(--m-text-secondary); }
.fallback-head { color: var(--m-warning); margin-bottom: 6px; font-weight: 500; }
.fallback pre {
  background: var(--m-bg-soft);
  padding: 10px; border-radius: 6px;
  font-family: 'Roboto Mono', monospace; font-size: 11.5px;
  max-height: 320px; overflow: auto;
}
</style>
