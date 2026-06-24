<template>
  <div class="conversation-search">
    <el-input
      v-model="keyword"
      placeholder="搜索对话..."
      prefix-icon="Search"
      clearable
      :loading="loading"
      @input="debounceSearch"
      @clear="results = []"
    />
    <div v-if="results.length" class="search-results">
      <div
        v-for="r in results"
        :key="r.id"
        class="search-item"
        @click="$emit('select', r)"
      >
        <div class="item-title">{{ r.title }}</div>
        <div class="item-time">{{ formatTime(r.updated_at) }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { api } from '@/api'

defineEmits<{ select: [conv: any] }>()

const keyword = ref('')
const results = ref<any[]>([])
const loading = ref(false)

let timer: ReturnType<typeof setTimeout>
function debounceSearch() {
  clearTimeout(timer)
  timer = setTimeout(() => search(), 300)
}

async function search() {
  if (!keyword.value.trim()) {
    results.value = []
    return
  }
  loading.value = true
  try {
    results.value = await api.searchConversations(keyword.value)
  } finally {
    loading.value = false
  }
}

function formatTime(iso: string) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('zh-CN')
}
</script>

<style scoped>
.conversation-search { position: relative; }
.search-results {
  position: absolute; top: 100%; left: 0; right: 0; z-index: 100;
  background: white; border: 1px solid #e2e8f0; border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,.1); max-height: 300px; overflow-y: auto;
  margin-top: 4px;
}
.search-item {
  padding: 10px 14px; cursor: pointer; border-bottom: 1px solid #f1f5f9;
}
.search-item:hover { background: #f8fafc; }
.search-item:last-child { border-bottom: none; }
.item-title { font-size: 14px; color: #1e293b; }
.item-time { font-size: 12px; color: #94a3b8; margin-top: 2px; }
</style>
