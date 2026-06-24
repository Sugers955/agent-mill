/**
 * 工具调用名称的中文语义映射。
 *
 * 原始英文 tool id 仍保留在 step-card 的展开区供调试，
 * 这里只负责给 summary 行提供可读标签。
 */

// 内置工具固定映射
const BUILTIN_LABELS: Record<string, string> = {
  // 文件 / 输出
  save_output_file: '保存输出文件',
  _read_skill_file: '读取Skill技能文件',
  run_skill_script: '执行Skill技能脚本',

  // 用户交互
  ask_user_form: '向用户请求表单输入',
  ask_user_pick: '向用户请求选择',

  // Widget / 渲染
  load_widget_guidelines: '使用界面来动态渲染',
  render_widget: '渲染界面组件',

  // Claude Agent SDK 内置
  Read: '读取文件',
  Glob: '搜索文件路径',
  Grep: '搜索文件内容',
  Bash: '执行 Shell 命令',
  Edit: '编辑文件',
  Write: '写入文件',
  WebFetch: '抓取网页',
  WebSearch: '搜索网络',
  Skill: '调用技能',
  NotebookEdit: '编辑 Notebook',

  // Pack
  run_pack: '执行流程包',
}

// MCP 工具的末段名称映射（通用语义词汇）
const MCP_SUFFIX_LABELS: Record<string, string> = {
  // 报告生成
  generate_report: '生成报告',
  import_template: '导入模板',
  list_templates: '列出模板',
  get_tool_list: '获取工具列表',
  generate_blank_excel: '生成空白 Excel 模板',

  // 通用 CRUD
  list: '列表查询',
  get: '查询详情',
  create: '创建',
  update: '更新',
  delete: '删除',
  search: '搜索',
  upload: '上传',
  download: '下载',
}

/**
 * 解析原始工具名，返回 { label, kind, serverName }
 *
 * 命名约定：
 *   mcp__<server>__<tool>   → kind=MCP, serverName=<server>
 *   mcp_<server>__<tool>    → 同上（旧格式兼容）
 *   run_pack__<code>        → kind=PACK
 *   其余                    → kind=TOOL
 */
export interface ToolMeta {
  label: string     // 中文语义名
  kind: string      // 大写分类：MCP / TOOL / PACK
  serverName: string // MCP server 名，非 MCP 时为空串
  rawName: string   // 原始英文 id，供展开区显示
}

export function resolveToolMeta(rawName: string): ToolMeta {
  if (!rawName) return { label: '(unknown)', kind: 'TOOL', serverName: '', rawName }

  // ---- PACK ----
  if (rawName.startsWith('run_pack__')) {
    const code = rawName.slice('run_pack__'.length)
    return { label: `执行流程包 · ${code}`, kind: 'PACK', serverName: '', rawName }
  }

  // ---- MCP (mcp__server__tool 或 mcp_server__tool) ----
  const mcpMatch = rawName.match(/^mcp_{1,2}([^_][^_]*)(?:__|_)(.+)$/i)
    ?? rawName.match(/^mcp__(.+?)__(.+)$/)
  if (mcpMatch) {
    const server = mcpMatch[1]
    const tool = mcpMatch[2]
    const suffix = tool.split('__').pop() ?? tool  // 取最后一段
    const label = MCP_SUFFIX_LABELS[suffix] ?? MCP_SUFFIX_LABELS[tool] ?? formatFallback(tool)
    return {
      label,
      kind: 'MCP',
      serverName: server,
      rawName,
    }
  }

  // ---- 内置工具 ----
  const builtinLabel = BUILTIN_LABELS[rawName]
  if (builtinLabel) {
    return { label: builtinLabel, kind: 'TOOL', serverName: '', rawName }
  }

  // ---- 兜底：snake_case → 中文化失败，格式化英文 ----
  return { label: formatFallback(rawName), kind: 'TOOL', serverName: '', rawName }
}

/** snake_case / camelCase 转可读英文（实在没有中文映射时的兜底） */
function formatFallback(name: string): string {
  return name.replace(/_/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2')
}
