<template>
  <div class="data-table">
    <h3 v-if="schema.title" class="title">{{ schema.title }}</h3>
    <el-table :data="rows" stripe @row-click="onRow">
      <el-table-column v-for="col in columns" :key="col.id"
        :prop="col.binds?.replace(/^\//, '') || col.id"
        :label="col.props?.label || col.id"
        :sortable="col.props?.sortable !== false"
      />
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ActionDef, ComponentDef, UIMessage } from '../types/schema'

const props = defineProps<{ schema: UIMessage; onAction: (a: ActionDef, params: any, ctx: any) => void }>()

const columns = computed<ComponentDef[]>(() =>
  (props.schema.components || []).filter(c => c.type === 'Column'))
const rows = computed(() => props.schema.data_model.rows || props.schema.data_model.items || [])

const rowAction = computed<ActionDef | undefined>(() =>
  (props.schema.actions || []).find(a => a.trigger === 'row_click'))

function onRow(row: any, _col: any, _ev: any) {
  if (!rowAction.value) return
  const idx = rows.value.indexOf(row)
  props.onAction(rowAction.value, null, { index: idx, row })
}
</script>

<style scoped>
.data-table { display:flex; flex-direction: column; gap: 8px; }
.title { margin: 0; font-size: 16px; font-weight: 600; }
</style>
