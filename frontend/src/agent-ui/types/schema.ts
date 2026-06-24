/**
 * Agent UI Schema — types shared between Dispatcher / Parser / Components.
 *
 * Mirror of backend `app/ui_schema/types.py` shape.
 */

export type ComponentType =
  | 'CardList'
  | 'DynamicForm'
  | 'ConfirmDialog'
  | 'DataTable'
  | 'StatusTimeline'

export type ActionTrigger =
  | 'button_click'
  | 'card_click'
  | 'row_click'
  | 'form_submit'
  | 'select_change'

export interface ActionDef {
  name: string
  label: string
  trigger: ActionTrigger
  agent_call: boolean
  /** How the action's payload is delivered to the backend.
   *   - undefined / 'tool' (legacy): when agent_call=true, route via [UI_ACTION]
   *     directly to the tool, bypassing the LLM.
   *   - 'message': render `message_template` with the resolved params and post
   *     it as a normal user turn (LLM decides what to do next). The transcript
   *     hides this synthetic user bubble.
   */
  submit_as?: 'tool' | 'message'
  /** Template for submit_as='message'. Supports `{{key}}` placeholders that
   *  resolve from the action's params (after params_from / params_map). Missing
   *  keys collapse to empty string. */
  message_template?: string
  tool?: string
  params_from?: string  // JSON pointer-ish: "/items/{index}/id" or "/" for whole data_model
  /** Field-name remapping applied AFTER params_from resolves to an object.
   *  Key = target param name (matches the tool's signature),
   *  Value = JSON pointer into the resolved object (e.g. "/id" or "/items/{index}/id"). */
  params_map?: Record<string, string>
  confirm?: string
  style?: 'primary' | 'default' | 'danger'
}

export interface FilterDef {
  field: string
  label: string
  type: 'sort' | 'select' | 'range' | 'search'
  options?: { label: string; value: any }[]
  agent_call: boolean
}

export interface ComponentDef {
  id: string
  type: string
  binds?: string
  props?: Record<string, any>
  children?: string[]
  action_ref?: string
}

export interface PaginationDef {
  page: number
  page_size: number
  total: number
  agent_call: boolean
}

export interface UIMessage {
  message_type: 'ui'
  surface_id: string
  component_type: ComponentType | string
  title?: string
  data_model: Record<string, any>
  components?: ComponentDef[]
  actions?: ActionDef[]
  pagination?: PaginationDef
  filters?: FilterDef[]
}

export interface UIComponentProps {
  schema: UIMessage
  onAction: (action: ActionDef, params: any, ctx?: { index?: number }) => void
}
