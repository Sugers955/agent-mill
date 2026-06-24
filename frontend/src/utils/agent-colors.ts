// Agent 颜色轮转 - 用于区分不同 agent 的渐变背景色
export const AGENT_COLORS = [
  '#4285f4', // 蓝
  '#ea4335', // 红
  '#fbbc04', // 黄
  '#34a853', // 绿
  '#9c27b0', // 紫
  '#ff5722', // 橙
] as const

export const DEFAULT_GRADIENT = 'linear-gradient(135deg, #4285f4, #34a853)'

export function agentGradient(agent: { id?: number } | null | undefined): string {
  if (!agent) return DEFAULT_GRADIENT
  const idx = (agent.id || 0) % AGENT_COLORS.length
  return `linear-gradient(135deg, ${AGENT_COLORS[idx]}, ${AGENT_COLORS[(idx + 1) % AGENT_COLORS.length]})`
}
