<template>
  <div class="mr-wrap" v-if="codes.length">
    <MermaidBlock v-for="(code, i) in codes" :key="i" :code="code" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import MermaidBlock from './MermaidBlock.vue'

const props = defineProps<{ text: string }>()

const codes = computed(() => {
  const result: string[] = []
  const re = /```mermaid\s*\n?([\s\S]*?)```/g
  let m: RegExpExecArray | null
  while ((m = re.exec(props.text)) !== null) result.push(m[1].trim())
  return result
})
</script>
