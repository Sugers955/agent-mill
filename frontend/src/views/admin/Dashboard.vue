<template>
  <div class="db">
    <!-- 顶栏 -->
    <div class="db-hd">
      <div class="db-hd-l">
        <div class="db-hd-icon">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="4" rx="1" />
            <rect x="14" y="10" width="7" height="11" rx="1" /><rect x="3" y="13" width="7" height="8" rx="1" />
          </svg>
        </div>
        <div><h2 class="db-hd-t">数据面板</h2><p class="db-hd-s">平台运行状态与数据洞察</p></div>
      </div>
      <el-radio-group v-model="trendDays" size="small">
        <el-radio-button :value="7">7天</el-radio-button>
        <el-radio-button :value="30">30天</el-radio-button>
        <el-radio-button :value="90">90天</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 统计卡片 -->
    <div class="db-cards">
      <div class="dc" v-for="s in statItems" :key="s.label" :style="{ '--c': s.color, '--b': s.bg }">
        <div class="dc-i"><el-icon :size="18"><component :is="s.icon" /></el-icon></div>
        <div class="dc-v">{{ s.value }}</div>
        <div class="dc-l">{{ s.label }}</div>
      </div>
    </div>

    <!-- Tab 导航 -->
    <div class="db-tabs">
      <button v-for="t in tabs" :key="t.key" :class="['db-t', { a: activeTab === t.key }]" @click="activeTab = t.key">
        <span class="db-t-i">{{ t.icon }}</span>
        <span>{{ t.label }}</span>
      </button>
    </div>

    <!-- 概览 -->
    <div class="db-b" v-show="activeTab === 'overview'">
      <div class="db-row-2">
        <div class="box">
          <div class="box-h"><span class="box-t">Token 用量趋势</span><span class="box-badge">{{ trendDays }}天</span></div>
          <div ref="trendChartRef" class="box-c" />
        </div>
        <div class="box">
          <div class="box-h"><span class="box-t">系统健康</span></div>
          <div class="box-health" v-if="health">
            <div v-for="h in healthItems" :key="h.label" class="bh">
              <div class="bh-top"><span class="bh-l">{{ h.label }}</span><span class="bh-v" :class="h.cls">{{ h.val }}</span></div>
              <div class="bh-bar"><div class="bh-fill" :class="h.cls" :style="{ width: h.pct + '%' }" /></div>
            </div>
          </div>
          <div v-else class="box-e">加载中…</div>
        </div>
      </div>
    </div>

    <!-- 用户 -->
    <div class="db-b" v-show="activeTab === 'users'">
      <div class="db-row-3">
        <div class="box"><div class="box-h"><span class="box-t">用户用量 TOP10</span></div><div ref="userChartRef" class="box-c" /></div>
        <div class="box"><div class="box-h"><span class="box-t">员工分布</span></div><div ref="agentChartRef" class="box-c" /></div>
        <div class="box"><div class="box-h"><span class="box-t">部门统计</span></div><div ref="departmentChartRef" class="box-c" /></div>
      </div>
    </div>

    <!-- 成本 -->
    <div class="db-b" v-show="activeTab === 'cost'">
      <div class="db-row-2">
        <div class="box"><div class="box-h"><span class="box-t">模型成本对比</span></div><div ref="modelChartRef" class="box-c" /></div>
        <div class="box">
          <div class="box-h"><span class="box-t">Token 消耗明细</span></div>
          <div class="box-tk" v-if="tokenDetails.length">
            <table><thead><tr><th>用户</th><th>模型</th><th class="r">输入</th><th class="r">输出</th><th>时间</th></tr></thead>
              <tbody>
                <tr v-for="t in tokenDetails" :key="t.id">
                  <td class="tk-u">{{ t.user_name }}</td>
                  <td><code>{{ t.model_code }}</code></td>
                  <td class="r">{{ t.tokens_in }}</td>
                  <td class="r">{{ t.tokens_out }}</td>
                  <td class="tk-t">{{ relTime(t.created_at) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="box-e">加载中…</div>
        </div>
      </div>
    </div>

    <!-- 性能 -->
    <div class="db-b" v-show="activeTab === 'perf'">
      <div class="db-row-3">
        <div class="box"><div class="box-h"><span class="box-t">延迟趋势 (ms)</span></div><div ref="latencyChartRef" class="box-c" /></div>
        <div class="box"><div class="box-h"><span class="box-t">错误率趋势</span></div><div ref="errorChartRef" class="box-c" /></div>
        <div class="box"><div class="box-h"><span class="box-t">员工效果</span></div><div ref="effectivenessChartRef" class="box-c" /></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import { api } from '@/api'
import { Coin, Wallet, User, ChatLineRound } from '@element-plus/icons-vue'

const activeTab = ref('overview')
const trendDays = ref(30)
const overview = reactive({ total_tokens: 0, total_cost: 0, active_users: 0, total_conversations: 0 })
const health = ref<any>(null)
const tokenDetails = ref<any[]>([])

const tabs = [
  { key: 'overview', icon: '📊', label: '概览' },
  { key: 'users', icon: '👥', label: '用户' },
  { key: 'cost', icon: '💰', label: '成本' },
  { key: 'perf', icon: '⚡', label: '性能' },
]

const R: Record<string, any> = {
  trend: ref<HTMLElement>(), user: ref<HTMLElement>(), agent: ref<HTMLElement>(),
  model: ref<HTMLElement>(), dept: ref<HTMLElement>(), latency: ref<HTMLElement>(),
  error: ref<HTMLElement>(), effect: ref<HTMLElement>(),
}
const C: Record<string, echarts.ECharts | null> = {}
const inited: Record<string, boolean> = {}

const trendChartRef = R.trend
const userChartRef = R.user
const agentChartRef = R.agent
const modelChartRef = R.model
const departmentChartRef = R.dept
const latencyChartRef = R.latency
const errorChartRef = R.error
const effectivenessChartRef = R.effect

const MAX_PCT = 100

const healthItems = computed(() => {
  const h = health.value
  if (!h) return []
  const items = [
    { label: '平均延迟', val: `${h.avg_latency || 0}ms`, pct: Math.min(((h.avg_latency || 0) / 500) * 100, 100), cls: '' },
    { label: '错误率(1h)', val: `${h.error_rate || 0}%`, pct: Math.min((h.error_rate || 0) * 10, 100), cls: (h.error_rate || 0) > 5 ? 'd' : '' },
    { label: '活跃员工', val: h.active_agents || 0, pct: Math.min(((h.active_agents || 0) / 20) * 100, 100), cls: '' },
    { label: '活跃对话', val: h.active_conversations || 0, pct: Math.min(((h.active_conversations || 0) / 50) * 100, 100), cls: '' },
    { label: '1h 调用量', val: h.total_calls_1h || 0, pct: Math.min(((h.total_calls_1h || 0) / 100) * 100, 100), cls: '' },
  ]
  return items
})

const statItems = computed(() => [
  { label: '本月 Token 消耗', value: fmtTokens(overview.total_tokens), icon: Coin, color: '#3b82f6', bg: '#eff6ff' },
  { label: '本月成本', value: `¥${overview.total_cost.toFixed(2)}`, icon: Wallet, color: '#f59e0b', bg: '#fffbeb' },
  { label: '活跃用户', value: overview.active_users, icon: User, color: '#22c55e', bg: '#f0fdf4' },
  { label: '对话总数', value: overview.total_conversations, icon: ChatLineRound, color: '#8b5cf6', bg: '#f5f3ff' },
])

function fmtTokens(n: number) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}

function relTime(date: string | null) {
  if (!date) return '--'
  const diff = Date.now() - new Date(date).getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}时前`
  return `${Math.floor(diff / 86400000)}天前`
}

function css(k: string) { return getComputedStyle(document.documentElement).getPropertyValue(k).trim() }

function colors() {
  return {
    text: css('--m-text') || '#1e293b', t2: css('--m-text-secondary') || '#64748b',
    border: css('--m-border') || '#e2e8f0', primary: css('--m-primary') || '#3b82f6',
  }
}

function init(key: string) {
  const el = R[key]?.value
  if (!el || inited[key]) return
  inited[key] = true
  const c = echarts.init(el)
  C[key] = c
  const clr = colors()
  c.setOption({
    textStyle: { color: clr.text }, grid: { top: 28, left: 46, right: 10, bottom: 20 },
    xAxis: { axisLine: { lineStyle: { color: clr.border } }, axisLabel: { color: clr.t2, fontSize: 11 }, axisTick: { lineStyle: { color: clr.border } } },
    yAxis: { axisLine: { show: false }, axisLabel: { color: clr.t2, fontSize: 11 }, splitLine: { lineStyle: { color: clr.border, type: 'dashed' } } },
    tooltip: { trigger: 'axis', backgroundColor: css('--m-surface') || '#fff', borderColor: clr.border, textStyle: { color: clr.text, fontSize: 12 } },
  })
}

function setD(key: string, type: string, raw: any) {
  const el = R[key]?.value
  if (!el) return
  let chart = C[key]
  if (!chart) { init(key); chart = C[key] }
  if (!chart) return
  const clr = colors()
  const data = raw?.items || raw || []
  const labels = data.map((d: any) => d.name || d.date || d.model_code || d.agent_name || d.user_name || '')
  const values = data.map((d: any) => d.value || d.total_tokens || d.total_cost || d.count || d.calls || 0)

  if (type === 'pie') {
    chart.setOption({
      series: [{
        type: 'pie', radius: ['32%', '60%'], center: ['50%', '55%'],
        label: { color: clr.t2, fontSize: 11, formatter: '{b}\n{d}%' },
        labelLine: { lineStyle: { color: clr.border } },
        data: data.map((d: any) => ({ name: d.name || d.agent_name || '', value: d.value || d.count || d.calls || 1 })),
        itemStyle: { borderRadius: 4, borderColor: css('--m-surface') || '#fff', borderWidth: 2 },
        emphasis: { scaleSize: 4 },
      }],
    })
  } else {
    chart.setOption({
      xAxis: { type: 'category', data: labels },
      yAxis: { type: 'value' },
      series: [{
        type: type as any, data: values, smooth: type === 'line',
        lineStyle: { color: clr.primary, width: 2.5 },
        itemStyle: { color: clr.primary, borderRadius: type === 'bar' ? [4, 4, 0, 0] : undefined },
        areaStyle: type === 'line' ? { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(59,130,246,0.2)' }, { offset: 1, color: 'rgba(59,130,246,0)' }] } } : undefined,
        barMaxWidth: 32, barGap: '30%', symbol: type === 'line' ? 'circle' : 'none', symbolSize: 5,
      }],
    })
  }
}

const tabMap: Record<string, Array<{ k: string; t: string }>> = {
  overview: [{ k: 'trend', t: 'line' }],
  users: [{ k: 'user', t: 'bar' }, { k: 'agent', t: 'pie' }, { k: 'dept', t: 'bar' }],
  cost: [{ k: 'model', t: 'bar' }],
  perf: [{ k: 'latency', t: 'line' }, { k: 'error', t: 'line' }, { k: 'effect', t: 'bar' }],
}

watch(activeTab, async () => {
  await nextTick()
  for (const { k } of tabMap[activeTab.value] || []) {
    if (R[k]?.value && !inited[k]) init(k)
    await nextTick()
    C[k]?.resize()
  }
})

onMounted(async () => {
  try {
    const [ov, h, td] = await Promise.all([
      api.statsOverview().catch(() => ({})), api.statsSystemHealth().catch(() => null),
      api.statsTokenDetail({ limit: 20, offset: 0 }).catch(() => ({ items: [] })),
    ])
    Object.assign(overview, ov); health.value = h; tokenDetails.value = td.items || td || []
  } catch {}
  try {
    const [trend, usr, agt, mdl, dept, eff, lat, err] = await Promise.all([
      api.statsTrend(trendDays.value), api.statsByUser(), api.statsByAgent(), api.statsByModel(),
      api.statsByDepartment(), api.statsAgentEffectiveness(),
      api.statsLatencyTrend(trendDays.value), api.statsErrorTrend(trendDays.value),
    ])
    await nextTick(); init('trend')
    setD('trend', 'line', trend); setD('user', 'bar', usr); setD('agent', 'pie', agt)
    setD('model', 'bar', mdl); setD('dept', 'bar', dept); setD('latency', 'line', lat)
    setD('error', 'line', err); setD('effect', 'bar', eff)
  } catch {}
})

watch(trendDays, async () => {
  try {
    const [trend, lat, err] = await Promise.all([
      api.statsTrend(trendDays.value), api.statsLatencyTrend(trendDays.value), api.statsErrorTrend(trendDays.value),
    ])
    setD('trend', 'line', trend); setD('latency', 'line', lat); setD('error', 'line', err)
  } catch {}
})

onUnmounted(() => { for (const c of Object.values(C)) c?.dispose() })
</script>

<style scoped>
.db { height: 100%; display: flex; flex-direction: column; }

/* header */
.db-hd { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; flex-shrink: 0; }
.db-hd-l { display: flex; align-items: center; gap: 12px; }
.db-hd-icon { width: 38px; height: 38px; border-radius: 10px; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, var(--m-primary), var(--m-primary-hover)); color: #fff; flex-shrink: 0; }
.db-hd-t { margin: 0; font-size: 17px; font-weight: 700; color: var(--m-text); }
.db-hd-s { margin: 1px 0 0; font-size: 12px; color: var(--m-text-secondary); }

/* stat cards */
.db-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 18px; flex-shrink: 0; }
.dc { padding: 16px; border-radius: 12px; background: var(--m-surface); border: 1px solid var(--m-border); display: flex; flex-direction: column; gap: 4px; transition: transform .2s; }
.dc:hover { transform: translateY(-2px); }
.dc-i { width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; background: var(--b); color: var(--c); }
.dc-v { font-size: 20px; font-weight: 700; color: var(--m-text); line-height: 1.2; letter-spacing: -.3px; }
.dc-l { font-size: 12px; color: var(--m-text-secondary); }

/* tabs */
.db-tabs { display: flex; gap: 2px; margin-bottom: 14px; flex-shrink: 0; border-bottom: 1px solid var(--m-border); }
.db-t { display: flex; align-items: center; gap: 5px; padding: 7px 16px 9px; background: transparent; border: none; font-size: 13px; font-weight: 500; color: var(--m-text-secondary); cursor: pointer; border-bottom: 2.5px solid transparent; margin-bottom: -1px; transition: color .2s; }
.db-t:hover { color: var(--m-text); }
.db-t.a { color: var(--m-primary); font-weight: 600; border-bottom-color: var(--m-primary); }
.db-t-i { font-size: 14px; }

/* body */
.db-b { flex: 1; overflow-y: auto; }
.db-b::-webkit-scrollbar { width: 4px; }
.db-b::-webkit-scrollbar-thumb { background: var(--m-border); border-radius: 4px; }

/* row layouts */
.db-row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; height: 100%; min-height: 320px; }
.db-row-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; height: 100%; min-height: 320px; }

/* card */
.box { background: var(--m-surface); border: 1px solid var(--m-border); border-radius: 12px; overflow: hidden; display: flex; flex-direction: column; }
.box-h { display: flex; align-items: center; justify-content: space-between; padding: 14px 16px 0; flex-shrink: 0; }
.box-t { font-size: 13px; font-weight: 600; color: var(--m-text); }
.box-badge { font-size: 10px; font-weight: 500; color: var(--m-text-tertiary); background: var(--m-bg-soft); padding: 1px 7px; border-radius: 5px; }
.box-c { flex: 1; min-height: 0; padding: 4px 0; }
.box-e { display: flex; align-items: center; justify-content: center; flex: 1; color: var(--m-text-secondary); font-size: 13px; }

/* health */
.box-health { flex: 1; padding: 12px 16px 16px; display: flex; flex-direction: column; justify-content: center; gap: 10px; }
.bh { display: flex; flex-direction: column; gap: 3px; }
.bh-top { display: flex; justify-content: space-between; align-items: center; }
.bh-l { font-size: 12px; color: var(--m-text-secondary); }
.bh-v { font-size: 15px; font-weight: 600; color: var(--m-text); }
.bh-v.d { color: var(--m-danger); }
.bh-bar { height: 4px; background: var(--m-border); border-radius: 2px; overflow: hidden; }
.bh-fill { height: 100%; border-radius: 2px; background: var(--m-primary); transition: width .6s ease; }
.bh-fill.d { background: var(--m-danger); }

/* token table */
.box-tk { flex: 1; min-height: 0; overflow-y: auto; }
.box-tk table { width: 100%; border-collapse: collapse; font-size: 12px; }
.box-tk th { text-align: left; padding: 7px 12px; font-weight: 600; color: var(--m-text-secondary); background: var(--m-bg-soft); position: sticky; top: 0; border-bottom: 1px solid var(--m-border); }
.box-tk th.r, .r { text-align: right; }
.box-tk td { padding: 7px 12px; border-bottom: 1px solid var(--m-border); color: var(--m-text); }
.box-tk tbody tr:hover td { background: var(--m-bg-soft); }
.tk-u { max-width: 100px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tk-t { color: var(--m-text-tertiary); font-size: 11px; white-space: nowrap; }
.box-tk code { font-size: 10px; background: var(--m-bg-soft); padding: 1px 5px; border-radius: 3px; color: var(--m-primary); }

/* responsive */
@media (max-width: 900px) {
  .db-cards { grid-template-columns: repeat(2, 1fr); }
  .db-row-2, .db-row-3 { grid-template-columns: 1fr; min-height: auto; }
}
</style>
