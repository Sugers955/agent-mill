export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  agent_name?: string
  agent_avatar?: string
  model_id?: number
  model_provider?: string
  created_at: string
  steps?: ToolStep[]
  files?: FileInfo[]
  widgets?: string
  ui_schema?: unknown
  favorite?: boolean
  feedback?: 'like' | 'dislike' | null
  thinking?: string
  trace?: unknown
}

export interface ToolStep {
  tool: string
  tool_name?: string
  input: Record<string, unknown>
  output?: unknown
  result?: string
  status: 'running' | 'success' | 'error'
  duration_ms?: number
}

export interface UploadFile {
  id: string
  name: string
  size: number
  status: 'uploading' | 'parsing' | 'ready' | 'error'
  url?: string
  parse_status?: string
  error?: string
}

export interface StarterItem {
  label: string
  query: string
  icon?: string
}

export interface AgentInfo {
  id: number
  name: string
  description?: string
  avatar_url?: string
}

export interface FileInfo {
  id: string
  name: string
  size?: number
  url?: string
  type?: string
}
