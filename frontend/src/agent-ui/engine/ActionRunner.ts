/**
 * ActionRunner — handle user gestures on a rendered UI Schema.
 *
 *  - agent_call=false                    → noop (caller updates local state directly via filters/sort)
 *  - agent_call=true,  submit_as='tool'  → confirm? → POST [UI_ACTION] tool=... params=...
 *                                          (default; backend bypasses LLM and calls tool)
 *  - agent_call=true,  submit_as='message' → confirm? → render message_template with params
 *                                          → POST [UI_MSG] <text>  (backend strips prefix,
 *                                          marks the user bubble hidden, runs the LLM normally)
 */
import { ElMessageBox } from 'element-plus'
import type { ActionDef, UIMessage } from '../types/schema'
import { buildActionParams } from './SchemaParser'

export type AgentCall = (text: string) => Promise<void> | void

export interface RunActionOpts {
  schema: UIMessage
  action: ActionDef
  ctx?: { index?: number; row?: any; form?: Record<string, any> }
  onAgentCall: AgentCall
}

function renderTemplate(tpl: string, params: any): string {
  if (!tpl) return ''
  const obj = (params && typeof params === 'object') ? params : {}
  return tpl.replace(/\{\{\s*([^}]+?)\s*\}\}/g, (_m, key) => {
    const path = String(key).split('.').map((s) => s.trim()).filter(Boolean)
    let v: any = obj
    for (const p of path) {
      if (v == null) { v = undefined; break }
      v = v[p]
    }
    if (v == null) return ''
    if (Array.isArray(v)) return v.map((x) => (x == null ? '' : String(x))).join('、')
    if (typeof v === 'object') return JSON.stringify(v)
    return String(v)
  })
}

export async function runAction(opts: RunActionOpts): Promise<void> {
  const { schema, action, ctx = {}, onAgentCall } = opts

  if (action.confirm) {
    try {
      await ElMessageBox.confirm(action.confirm, '确认', {
        type: 'warning',
        confirmButtonText: action.label || '确认',
        cancelButtonText: '取消',
      })
    } catch {
      return
    }
  }

  if (!action.agent_call) {
    // Local-only action. Caller is expected to mutate state directly.
    return
  }

  const params = buildActionParams(schema, action, ctx)
  const submitAs = action.submit_as || 'tool'

  if (submitAs === 'message') {
    // Synthetic-user-message route: let the LLM decide what to do next.
    // Template is required; if absent or rendered to empty, fall back to JSON.
    let text = renderTemplate(action.message_template || '', params)
    if (!text.trim()) {
      text = JSON.stringify(params ?? {})
    }
    await onAgentCall(`[UI_MSG] ${text}`)
    return
  }

  // Default 'tool' route — bypass LLM, call tool directly.
  if (!action.tool) {
    console.warn('[ui-action] agent_call=true but no tool specified', action)
    return
  }
  const text = `[UI_ACTION] tool=${action.tool} params=${JSON.stringify(params ?? {})}`
  await onAgentCall(text)
}
