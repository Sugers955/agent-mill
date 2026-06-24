<template>
  <div class="dyn-form">
    <h3 v-if="schema.title" class="title">{{ schema.title }}</h3>
    <el-form :model="form" label-position="top" @submit.prevent>
      <el-form-item
        v-for="c in schema.components"
        :key="c.id"
        :label="c.props?.label || c.id"
      >
        <el-input v-if="c.type === 'Input'" v-model="form[c.id]" :placeholder="c.props?.placeholder" />
        <el-input v-else-if="c.type === 'Textarea'" v-model="form[c.id]" type="textarea" :rows="c.props?.rows || 3" />
        <el-input-number v-else-if="c.type === 'InputNumber'" v-model="form[c.id]" :min="c.props?.min ?? 0" :max="c.props?.max" />
        <el-select v-else-if="c.type === 'Select'" v-model="form[c.id]" style="width:100%">
          <el-option v-for="o in (c.props?.options || [])" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
        <el-date-picker v-else-if="c.type === 'DatePicker'" v-model="form[c.id]" type="date" style="width:100%" />
        <el-date-picker v-else-if="c.type === 'RangePicker'" v-model="form[c.id]" type="daterange" style="width:100%" />
        <el-radio-group v-else-if="c.type === 'Radio'" v-model="form[c.id]">
          <el-radio v-for="o in (c.props?.options || [])" :key="o.value" :value="o.value">{{ o.label }}</el-radio>
        </el-radio-group>
        <el-checkbox-group v-else-if="c.type === 'Checkbox'" v-model="form[c.id]">
          <el-checkbox v-for="o in (c.props?.options || [])" :key="o.value" :value="o.value">{{ o.label }}</el-checkbox>
        </el-checkbox-group>
        <span v-else class="muted">未知字段类型: {{ c.type }}</span>
      </el-form-item>
      <div class="form-actions">
        <el-button
          v-for="a in submitActions"
          :key="a.name"
          :type="a.style === 'primary' ? 'primary' : 'default'"
          @click="fire(a)"
        >{{ a.label }}</el-button>
      </div>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive } from 'vue'
import type { ActionDef, UIMessage } from '../types/schema'

const props = defineProps<{ schema: UIMessage; onAction: (a: ActionDef, params: any, ctx: any) => void }>()

// Initialize form fields with defaults
const init: Record<string, any> = { ...(props.schema.data_model || {}) }
for (const c of (props.schema.components || [])) {
  if (init[c.id] !== undefined) continue
  if (c.props?.default !== undefined) {
    init[c.id] = c.props.default
  } else if (c.type === 'Checkbox') {
    // el-checkbox-group requires its v-model to be an array.
    init[c.id] = []
  } else if (c.type === 'InputNumber') {
    init[c.id] = null
  } else {
    init[c.id] = ''
  }
}
const form = reactive(init)

const submitActions = computed<ActionDef[]>(() =>
  (props.schema.actions || []).filter(a => a.trigger === 'form_submit' || a.trigger === 'button_click'))

function fire(a: ActionDef) {
  props.onAction(a, { ...form }, { form: { ...form } })
}
</script>

<style scoped>
.dyn-form { display: flex; flex-direction: column; gap: 8px; }
.title { margin: 0 0 6px; font-size: 16px; font-weight: 600; }
.form-actions { display:flex; gap: 8px; justify-content: flex-end; margin-top: 4px; }
.muted { color: var(--m-text-secondary); font-size: 12px; }
</style>
