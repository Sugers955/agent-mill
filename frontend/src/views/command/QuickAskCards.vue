<template>
  <div class="quick-ask">
    <div class="qa-header">
      <svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="8" cy="8" r="6"/><path d="M8 11V8M8 5.5"/></svg>
      快捷操作
    </div>
    <div class="qa-grid">
      <button v-for="(q, i) in questions" :key="i" class="qa-btn" @click="$emit('select', q)">
        <span class="qa-btn-icon" :style="{ background: iconColors[i % iconColors.length] }">
          <svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="#fff" stroke-width="1.5" stroke-linecap="round">
            <path v-if="i === 0" d="M3 8h10M8 3v10" />
            <path v-else-if="i === 1" d="M2 8l4-4 4 8 4-4" />
            <path v-else-if="i === 2" d="M3 5l3-3h4l3 3-5 8z" />
            <path v-else d="M3 3h10v6a2 2 0 01-2 2H5a2 2 0 01-2-2V3z" />
          </svg>
        </span>
        {{ q }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ questions: string[] }>()
defineEmits<{ select: [q: string] }>()

const iconColors = ['#667eea', '#f59e0b', '#22c55e', '#ef4444']
</script>

<style scoped>
.quick-ask { display: flex; flex-direction: column; gap: 8px; }
.qa-header { display: flex; align-items: center; gap: 5px; font-size: 11px; font-weight: 500; color: var(--m-text-tertiary); text-transform: uppercase; letter-spacing: 0.5px; }
.qa-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.qa-btn {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 10px;
  background: var(--m-surface); border: 1px solid var(--m-border);
  border-radius: 8px; font-size: 12px; color: var(--m-text); text-align: left;
  cursor: pointer; transition: all 0.2s;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.qa-btn:hover { border-color: var(--m-primary); box-shadow: 0 2px 8px rgba(0,0,0,0.04); }
.qa-btn:active { transform: scale(0.98); }
.qa-btn-icon {
  width: 22px; height: 22px; border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
</style>
