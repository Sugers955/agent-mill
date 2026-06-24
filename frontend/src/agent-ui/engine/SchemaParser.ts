/**
 * SchemaParser — validation + safe path resolution.
 *
 * Validation is permissive: missing fields don't throw, the dispatcher will
 * fall back to a JSON pre-block. This keeps the UX never-break.
 */
import type { UIMessage } from '../types/schema'

export function isValidSchema(s: any): s is UIMessage {
  return (
    s && typeof s === 'object'
    && s.message_type === 'ui'
    && typeof s.surface_id === 'string'
    && typeof s.component_type === 'string'
    && typeof s.data_model === 'object'
  )
}

/**
 * Resolve a JSON-pointer-ish path against the data_model.
 * Supports `{index}` substitution (for list rows).
 *
 *   "/" → entire data_model
 *   "/_self" → entire ctx (used by some adapters; falls back to data_model)
 *   "/items/0/name"
 *   "/items/{index}" with ctx.index=2 → /items/2
 */
export function resolvePath(
  dataModel: Record<string, any>,
  path: string | undefined,
  ctx: { index?: number; row?: any; form?: Record<string, any> } = {},
): any {
  if (!path) return dataModel
  if (path === '/_self') return ctx.row ?? ctx.form ?? dataModel
  if (path === '/') return dataModel
  let p = path
  if (p.includes('{index}') && ctx.index != null) p = p.replace('{index}', String(ctx.index))
  const parts = p.replace(/^\//, '').split('/').filter(Boolean)
  let cur: any = dataModel
  for (const seg of parts) {
    if (cur == null) return undefined
    cur = cur[seg]
  }
  return cur
}

/**
 * Build the params payload to send to the Agent for a given action.
 *
 * Order of resolution:
 *   1. Resolve `params_from` to a "source object" (a row, a form snapshot,
 *      or the whole data_model).
 *   2. If `params_map` is provided, build `{ targetKey: sourceObj[path...] }`
 *      for each entry. Paths in params_map are JSON-pointer style RELATIVE
 *      to the source object — `"/id"` means `sourceObj.id`.
 *   3. Otherwise return the source object as-is (form_submit / card_click).
 */
export function buildActionParams(
  schema: UIMessage,
  action: { params_from?: string; params_map?: Record<string, string> },
  ctx: { index?: number; row?: any; form?: Record<string, any> } = {},
): any {
  // Resolve the source object the map paths apply to.
  let sourceObj: any
  if (action.params_from === '/' || !action.params_from) {
    sourceObj = ctx.form ?? ctx.row ?? schema.data_model
  } else {
    sourceObj = resolvePath(schema.data_model, action.params_from, ctx)
  }

  if (action.params_map && Object.keys(action.params_map).length) {
    const out: Record<string, any> = {}
    for (const [targetKey, srcPath] of Object.entries(action.params_map)) {
      let value: any
      if (typeof srcPath === 'string') {
        // Treat all paths as relative to sourceObj. JSON-pointer style:
        //   "/id"   → sourceObj.id
        //   "/a/b"  → sourceObj.a.b
        //   "id"    → sourceObj.id (lenient: bare field name)
        value = resolvePath(sourceObj || {}, srcPath.startsWith('/') ? srcPath : '/' + srcPath, ctx)
      } else {
        value = srcPath  // literal value
      }
      out[targetKey] = value
    }
    return out
  }

  // No map → fall back to source object.
  if (action.params_from === '/' && ctx.form) return ctx.form
  return sourceObj
}
