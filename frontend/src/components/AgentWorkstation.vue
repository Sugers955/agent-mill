<template>
  <div class="ws" :class="{ cur: isCurrent }" @click="$emit('click', $event)">
    <div class="ws-header">
      <span class="ws-state" :class="state">
        <i class="ws-dot" />
        {{ state === 'idle' ? '待命中' : state === 'thinking' ? '思考中' : state === 'working' ? '工作中' : '异常' }}
      </span>
      <span class="ws-badge" v-if="isCurrent">当前</span>
    </div>

    <div class="ws-desk">
      <div class="ws-wall" />
      <div class="ws-table">
        <div class="mon mon-l">
          <div class="mon-scr">
            <div class="mon-scr-inner">
              <span v-if="state === 'idle'" class="m-time">{{ time }}</span>
              <span v-else-if="state === 'thinking'" class="m-dots"><i /><i /><i /></span>
              <span v-else-if="state === 'working'" class="m-bars"><i style="height:12px" /><i style="height:18px" /><i style="height:10px" /><i style="height:14px" /></span>
              <span v-else class="m-err">!</span>
            </div>
          </div>
          <div class="mon-st" />
        </div>
        <div class="mon mon-r">
          <div class="mon-scr">
            <div class="mon-scr-inner">
              <span class="m-ava" :style="as">{{ name[0] }}</span>
            </div>
          </div>
          <div class="mon-st" />
        </div>
        <div class="ws-items">
          <span>☕</span>
          <span>🌱</span>
        </div>
      </div>
    </div>

    <div class="ws-foot">
      <div class="ws-name">{{ name }}</div>
      <div class="ws-role">{{ role }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  name: string
  role: string
  state: 'idle' | 'thinking' | 'working' | 'error'
  color?: string
  isCurrent?: boolean
  progress?: number
  tasks?: number
  lastActive?: string
  taskLabel?: string
}>()

defineEmits(['click'])

const as = computed(() => ({ background: props.color || 'linear-gradient(135deg, #667eea, #764ba2)' }))

const d = new Date()
const time = `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
</script>

<style scoped>
.ws {
  border-radius: 12px;
  background: var(--m-surface);
  border: 1px solid var(--m-border);
  overflow: hidden;
  cursor: pointer;
  transition: transform .2s, border-color .2s;
}
.ws:hover { transform: translateY(-2px); border-color: var(--m-primary); }
.ws.cur { border-color: var(--m-primary); box-shadow: 0 0 0 1px var(--m-primary), 0 4px 16px var(--m-primary-soft); }

.ws-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid var(--m-border);
}
.ws-state { display: flex; align-items: center; gap: 5px; font-size: 11px; font-weight: 500; color: var(--m-text-secondary); }
.ws-dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
.ws-state.idle .ws-dot { background: var(--m-text-tertiary); }
.ws-state.thinking .ws-dot { background: #fbbf24; }
.ws-state.working .ws-dot { background: #22c55e; }
.ws-state.error .ws-dot { background: #ef4444; }
.ws-badge { font-size: 10px; font-weight: 600; padding: 2px 7px; border-radius: 5px; background: var(--m-primary); color: #fff; }

.ws-desk {
  position: relative;
  height: 150px;
  background: linear-gradient(180deg, var(--m-bg), var(--m-bg-soft));
}
.ws-wall {
  position: absolute; left: 0; right: 0; bottom: 60px; top: 0;
  border-bottom: 1px solid var(--m-border);
}
.ws-table {
  position: absolute; left: 0; right: 0; bottom: 0; height: 60px;
  background: linear-gradient(180deg, #c8a87c, #b8956a);
  display: flex; justify-content: center; gap: 30px;
  padding-top: 0;
}

.mon {
  display: flex; flex-direction: column; align-items: center;
  margin-top: -40px;
}
.mon-scr {
  width: 72px; height: 46px;
  background: #1a1a2e;
  border-radius: 4px 4px 2px 2px;
  padding: 3px;
  box-shadow: 0 2px 8px rgba(0,0,0,.12);
}
.mon-scr-inner {
  width: 100%; height: 100%;
  background: linear-gradient(135deg, #16213e, #0f3460);
  border-radius: 2px;
  display: flex; align-items: center; justify-content: center;
}
.mon-st {
  width: 10px; height: 8px;
  background: linear-gradient(180deg, #94a3b8, #64748b);
  border-radius: 0 0 1px 1px;
}

.m-time { font-size: 14px; font-weight: 700; color: rgba(255,255,255,.85); letter-spacing: 1px; }
.m-dots { display: flex; gap: 3px; }
.m-dots i { width: 5px; height: 5px; border-radius: 50%; background: #fbbf24; }
.m-bars { display: flex; align-items: flex-end; gap: 2px; height: 24px; }
.m-bars i { width: 6px; background: linear-gradient(to top, #60a5fa, #3b82f6); border-radius: 2px 2px 0 0; }
.m-err { color: #ef4444; font-size: 16px; font-weight: 700; }
.m-ava { width: 20px; height: 20px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 9px; font-weight: 600; }

.ws-items { position: absolute; bottom: 8px; right: 14px; display: flex; gap: 6px; font-size: 13px; }

.ws-foot { text-align: center; padding: 10px 12px 12px; border-top: 1px solid var(--m-border); }
.ws-name { font-size: 14px; font-weight: 600; color: var(--m-text); }
.ws-role { font-size: 11px; color: var(--m-text-secondary); margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
