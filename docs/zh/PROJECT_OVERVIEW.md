# Agent Mill 项目能力手册

> 你的数字员工工厂 — 企业级数字员工平台
> 数据库表: 40 张 | 23 个功能模块

---

## 一、项目定位

Agent Mill 是一个**企业级数字员工平台**，核心目标是让管理员快速配置多种 AI 数字员工，终端用户通过对话界面与数字员工交互，实现工具调用、文件处理、知识检索、多 Agent 协作等能力。

![Agent Mill 应用场景](../images/AgentMill应用场景.png)

**技术栈**：
- 后端: Python 3.11+ / FastAPI / SQLAlchemy 2.0 (async) / MySQL 8.0 / Claude Agent SDK / OpenAI SDK
- 前端: Vue 3 / TypeScript / Vite / Pinia / Element Plus
- 向量检索: ZVec（阿里巴巴，Rust 内核，嵌入式）
- 部署: Docker Compose (api + web) + 本地 MySQL

---

## 二、用户体系与权限

### 2.1 三角色 RBAC

| 角色 | 权限范围 |
|------|----------|
| **admin** | 全部权限：用户/角色/部门管理 + 数字员工/技能/连接器/模型配置 + 日志 + 对话 |
| **operator** | 配置权限：技能/连接器/数字员工/模型配置 + 日志 + 对话，**不能管用户/角色/部门** |
| **user** | 仅对话使用，可见数字员工由 `role_agent_grants` 控制 |

### 2.2 认证机制

- 本地用户名/密码登录（bcrypt 哈希）
- JWT 双 token: access token（12 小时）+ refresh token（2 天）
- SSO/LDAP: LDAP 认证降级 + OIDC 回调流程（state 防 CSRF）
- 48 小时空闲自动登出

### 2.3 部门管理

- 树形部门结构（parent_id 自引用）
- 循环依赖检测、强制删除

---

## 三、数字员工系统

### 3.1 配置能力

每个数字员工包含：
- **基本信息**: 名称、描述、图标、system_prompt
- **模型配置**: 主模型 + 降级模型（自动切换）
- **能力挂载**: 技能（多对多）+ 连接器（多对多）+ 方案包（多对多）
- **知识库**: 关联 ZVec 知识库，对话时自动检索注入
- **上传策略**: 扩展名白名单、大小限制、解析模式
- **推理参数**: max_turns、effort（low/medium/high/xhigh/max）
- **角色可见性**: 通过 role_agent_grants 控制

### 3.2 模板市场

5 个预置多 Agent 协作模板，一键部署：

| 模板 | 场景 |
|------|------|
| hr-support | HR 智能助手（入职/考勤/请假） |
| customer-service | 客服中心（咨询/工单/投诉） |
| marketing | 营销活动（策划/文案/数据分析） |
| onboarding | 员工入职（流程/培训/文档） |
| software-dev | 软件开发团队（需求/代码/测试） |

模板部署后返回 `next_steps` 操作指引（配置技能/连接器/知识库）。

---

## 四、模型管理

### 4.1 支持的供应商

| 供应商 | provider | 协议 |
|--------|----------|------|
| Anthropic (Claude) | `anthropic` | Claude Agent SDK |
| DeepSeek | `deepseek` | OpenAI 兼容 |
| 通义千问 (Qwen) | `qwen` | OpenAI 兼容 |
| 智谱 (GLM) | `glm` | OpenAI 兼容 |
| OpenAI | `openai` | OpenAI 兼容 |
| 任意兼容 | `openai-compatible` | OpenAI 兼容 |

### 4.2 模型配置

- API Key Fernet 加密存储，前端仅显示 `has_api_key`
- 一键测试连通性
- extra_params_json 透传（如 `enable_thinking`）

---

## 五、技能系统

### 5.1 三种技能类型

| 类型 | 形态 | 执行方式 |
|------|------|----------|
| **path 型** | ZIP 上传 → SKILL.md + 资源 | 文件级加载 + Python 脚本执行 |
| **callable 型** | `module.path:func` | 直接 import 调用（仅 admin） |
| **composite 型** | YAML DAG 步骤编排 | DAGExecutor 拓扑分层 + 并行 |

### 5.2 安全扫描

- Shell 注入模式检测（9 条规则）
- Python AST 静态分析（禁止 eval/exec/subprocess 等）
- 上传拦截 + 审计记录

### 5.3 内置工具

| 工具 | 功能 |
|------|------|
| `save_output_file` | 保存生成文件 |
| `_read_skill_file` | 读取技能资源 |
| `run_skill_script` | 执行 Python 脚本 |
| `ask_user_pick` | 弹出选项卡片 |
| `ask_user_form` | 弹出表单 |
| `run_pack__<code>` | 执行方案包 |

---

## 六、MCP 连接器系统

### 6.1 三种传输协议

| 协议 | 说明 |
|------|------|
| **stdio** | 子进程方式 |
| **sse** | Server-Sent Events |
| **http** | Streamable HTTP |

### 6.2 管理能力

- CRUD + 连接测试 + 工具列表获取
- LLM 自动生成中文摘要
- 按数字员工隔离挂载
- 白名单 + 参数注入检测

---

## 七、RAG 知识库

### 7.1 向量检索

- **ZVec**: 阿里巴巴 Rust 内核，嵌入式（pip install），零新容器
- **Embedding**: OpenAI 兼容 API（text-embedding-3-small），未配置时报错提示
- **分块**: 500 字符窗口 + 50 重叠
- **搜索**: 余弦相似度，top_k 可配

### 7.2 文档管道

上传 → 解析（30+ 格式）→ 分块 → Embedding → ZVec 索引

### 7.3 Agent 绑定

- Agent 配置中选择知识库
- 每次对话自动检索知识库，注入 system prompt
- 最后一条用户消息作为 query，top_k=3

### 7.4 前端管理

- 知识库列表 + 新建 + 删除（需审批）
- 文档管理 + 上传 + 源文件在线预览（JWT 鉴权）
- 搜索测试

---

## 八、方案包系统

### 8.1 核心能力

声明式 DAG 业务流程运行时：
- 持久化：每个节点执行后写入数据库
- 可恢复：断点恢复
- 人工审批：暂停等待审批后继续
- 子数字员工：委托给另一个 Agent 执行
- 执行追踪：完整 trace 记录

### 8.2 六种节点类型

| 节点 | 功能 |
|------|------|
| **skill** | 调用技能执行 |
| **parallel_group** | 并行组（all_success/first_success/n_of_m） |
| **aggregator** | 聚合器 |
| **condition** | 条件分支（规则/LLM 判断） |
| **sub_agent** | 子 Agent 委托 |
| **human_approval** | 人工审批 |

### 8.3 可视化工作流编辑器

- Vue Flow 画布，拖拽编排
- 6 种节点类型，连线定义依赖
- 编译为方案包 YAML → 复用 PackEngine
- **立即运行**按钮 + 异步执行 + 状态轮询 + 历史记录

---

## 九、对话与流式系统

### 9.1 双路径流式

| 路径 | 条件 | 实现 |
|------|------|------|
| **Anthropic** | provider == "anthropic" | Claude Agent SDK 真流式 |
| **OpenAI 兼容** | 其他 provider | `/v1/chat/completions` stream + tool_calls 多轮（最多 8 轮） |

### 9.2 SSE 事件类型

`meta` → `thinking` → `text` → `tool_use` → `tool_result` → `file` → `ui` → `error` → `done`

### 9.3 智能增强

- **记忆系统**: 对话结束自动提取偏好/事实，注入 prompt，去重 + 90 天衰减
- **上下文压缩**: 超 30 条自动摘要，保留最近 10 条
- **自学习**: 每小时分析反馈，低满意度 Agent 自动生成 prompt 改进建议
- **对话分支**: 从任意消息创建分支对话
- **消息编辑重发**: 编辑 → 截断 → 重新生成
- **流式 Markdown**: 未闭合代码块自动补全

---

## 十、文件处理系统

### 10.1 文件解析

| 格式 | 方式 |
|------|------|
| TXT/MD/CSV/JSON/HTML/XML/YAML | 直接读取 |
| PDF | MinerU → 回退 pypdf |
| DOCX | MinerU → 回退 python-docx |
| XLSX | MinerU → 回退 openpyxl |
| 图片 | MinerU OCR |

### 10.2 文件预览

- HTML iframe / PDF 原生 / Markdown / 文本代码块 / SVG / 图片
- Word/PPT/Excel 仅下载
- 安全: 一次性 token / 24h 过期 / user_id 校验

---

## 十一、企业特性（全部闭环）

### 11.1 审计合规

- **双表审计**: `audit_logs`（管理操作）+ `call_logs`（对话调用）
- **审计日志脱敏**: 自动脱敏邮箱/手机号
- **操作审批**: 高危操作（删除数字员工/技能/知识库/模型）需审批
- **通知管理员**: 创建审批时自动通知其他管理员

### 11.2 数据脱敏

- `mask_email`: t***t@example.com
- `mask_phone`: 138****5678
- `mask_id_card`: 1101**********1234
- 配置持久化到 SystemConfig 表
- 审计日志返回时自动脱敏

### 11.3 API 限流

- 令牌桶算法，路径匹配
- 默认 5 次/分钟，超限返回 429 + Retry-After
- 白名单路径: /health, /docs, /openapi.json

### 11.4 配额控制

- 用户级月度额度
- 告警阈值通知

### 11.5 SSO/LDAP

- **LDAP**: ldap3 库，bind 搜索 → 验证密码 → 查询组，异步非阻塞
- **OIDC**: 完整回调流程（授权 URL → code 换 token → 获取用户信息 → 角色映射 → JWT）
- **state 验证**: 防 CSRF，内存存储 + 10 分钟过期

### 11.6 告警通知

- **规则引擎**: 4 种指标（token/error_rate/call_count/latency）+ 4 种条件
- **通知渠道**: 站内通知 + 钉钉/企微/飞书 Webhook
- **测试连通性**: 一键测试 Webhook 配置
- **定时评估**: 每分钟自动评估规则

---

## 十二、可观测性

### 12.1 Dashboard

7+3 个 ECharts 图表：
- 总览统计（调用数/用户数/Token 消耗/成功率）
- 按用户/数字员工/模型分布
- 趋势图（7/30 天）
- 延迟趋势 / 错误率趋势 / 系统健康

### 12.2 Token 消耗明细

- 分页查询 + 筛选（用户/数字员工/模型/时间）
- CSV 导出

### 12.3 日志管理

- 审计日志 + 调用日志双标签
- 按用户/数字员工筛选
- 详情 JSON 展开

---

## 十三、多 Agent 协作

### 13.1 Agent 间通信

- 消息发送/接收/完成/回复
- 优先级（普通/高优先级）
- 委托任务

### 13.2 消息自动消费

- 单例轮询 pending 消息（每 5 秒）
- 自动调用目标 Agent 处理
- 每次操作独立 DB session，无连接泄漏

### 13.3 编排调度器

| 工作流 | 说明 |
|--------|------|
| **sequential** | 顺序: Agent1 → Agent2 → ... → AgentN |
| **parallel** | 并行: 所有 Agent 同时处理 |
| **map_reduce** | 各自处理 → 汇总 |

---

## 十四、安全体系（7 层防护）

| 层 | 机制 |
|----|------|
| 1 | 工具白名单（运行时） |
| 2 | system_prompt 安全前缀（模型层） |
| 3 | 输入正则过滤（网关层，12 条规则） |
| 4 | 技能静态扫描（上传时） |
| 5 | 文件 cwd 沙箱（SDK 层） |
| 6 | 下载令牌（出口层） |
| 7 | API Key 加密（Fernet） |

---

## 十五、前端能力

### 15.1 页面架构

![指挥中心 - 数字员工工位看板](../images/智慧中心.png)

*指挥中心界面：实时查看数字员工状态、发起对话、管理任务。*

| 页面 | 功能 |
|------|------|
| Login | Glassmorphism 登录 |
| Layout | 可折叠侧边栏 + 主题切换 |
| Chat | 核心对话（组件化重构后 547 行） |
| CommandCenter | 用户指挥中心 |
| Dashboard | 统计面板 |
| Models | 模型管理 |
| Skills | 技能管理 |
| MCP | 连接器管理 |
| Agents | 数字员工管理 |
| KnowledgeBases | 知识库管理 |
| KnowledgeBaseDetail | 文档管理 + 上传 + 搜索 |
| AgentTemplates | 模板市场 |
| WorkflowList | 工作流列表 |
| WorkflowEditor | Vue Flow 画布编辑器 |
| Approvals | 方案审批 + 操作审批 |
| Logs | 审计日志 + 调用日志 |
| Users/Roles/Departments | 用户管理 |

### 15.2 对话组件

- **WelcomePanel**: 欢迎页 + 数字员工卡片
- **MessageList**: 消息列表（ARIA: role=log）
- **ComposerInput**: 输入区 + 斜杠菜单
- **StepCard**: 工具步骤卡片

### 15.3 用户体验

- 暗色主题（CSS 变量切换 + localStorage）
- 响应式布局（768px 移动端适配）
- ARIA 可访问性（role/aria-label/tabindex）
- 快捷指令（/ 斜杠菜单）

### 15.4 移动端

独立 Vue 应用 `/m.html`，Hash 路由，完全独立的路由/stores/views/样式。

---

## 十六、数据库

### 16.1 38 张表

| 表 | 用途 |
|---|------|
| roles | RBAC 角色 |
| users | 用户账号 |
| departments | 部门树 |
| models | LLM 模型配置 |
| mcp_connectors | MCP 连接器 |
| skills | 技能定义 |
| agents | 数字员工配置 |
| agent_skills / agent_mcps / agent_packs | 多对多关联 |
| agent_knowledge_bases | 数字员工-知识库关联 |
| role_agent_grants | 角色-数字员工可见性 |
| conversations / messages | 对话与消息 |
| uploaded_files / download_tokens | 文件与下载令牌 |
| knowledge_bases / kb_documents / kb_chunks | 知识库 |
| agent_templates | 模板市场 |
| workflow_definitions / workflow_runs | 工作流 |
| solution_packs / pack_runs / pack_approvals | 方案包 |
| tasks / task_runs | 定时任务 |
| notifications / favorites | 通知与收藏 |
| audit_logs / call_logs | 审计与调用日志 |
| operation_approvals | 操作审批 |
| alert_rules / alert_events | 告警 |
| message_feedback / agent_learning | 自学习 |
| agent_memories | 记忆系统 |
| system_config | 系统配置（脱敏/Webhook 等） |
| agent_messages | Agent 间通信 |

### 16.2 迁移策略

- 启动时自动执行 `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE ADD COLUMN IF NOT EXISTS`
- MySQL 8.0.23 兼容（用 information_schema 兜底不支持的语法）
- 所有表和字段必须有中文 COMMENT

---

## 十七、部署

### 17.1 Docker Compose

```bash
cp .env.example .env
make deploy          # 首次部署
make deploy-update   # 增量更新
make deploy-status   # 查看状态
make deploy-down     # 停止
```

### 17.2 本地开发

```bash
make dev             # 后端:8000 + 前端:5173
make stop            # 停止
make logs            # 查看日志
make build           # 前端构建
make typecheck       # TypeScript 检查
```

### 17.3 Docker 部署

```bash
# 首次部署
docker compose up -d

# 查看状态
docker compose ps

# 查看日志
docker compose logs -f api
```

---

## 十八、功能完成度

| 模块 | 状态 | 说明 |
|:-----|:----:|------|
| 核心引擎（双路径流式） | ✅ 100% | Anthropic SDK + OpenAI 兼容 |
| 技能系统（三态） | ✅ 100% | path/callable/composite |
| MCP 连接器（三协议） | ✅ 100% | stdio/sse/http |
| RAG 知识库 | ✅ 100% | ZVec + 自动检索注入 + 30+ 格式 |
| 方案包（DAG 执行） | ✅ 100% | 6 种节点 + 人工审批 |
| 可视化工作流 | ✅ 100% | Vue Flow 画布 + 立即运行 + 状态轮询 |
| 模板市场 | ✅ 100% | 5 个模板 + 完整配置 + next_steps |
| 记忆系统 | ✅ 100% | 提取 + 去重 + 衰减 + 注入 |
| 上下文压缩 | ✅ 100% | LLM 摘要 |
| 自学习 | ✅ 100% | 定时分析 + prompt 改进建议 |
| 多 Agent 协作 | ✅ 100% | 通信 + 自动消费 + 三种编排 |
| RBAC | ✅ 100% | admin/operator/user |
| SSO/LDAP | ✅ 100% | LDAP + OIDC 完整回调 |
| 审计合规 | ✅ 100% | 双表 + 脱敏 + 操作审批 |
| 数据脱敏 | ✅ 100% | 持久化 + email/phone/id_card |
| API 限流 | ✅ 100% | 令牌桶 + 路径匹配 |
| 配额控制 | ✅ 100% | 用户级月度额度 |
| 告警通知 | ✅ 100% | 规则引擎 + 站内/钉钉/企微/飞书 |
| Dashboard | ✅ 100% | 7+3 图表 + CSV 导出 |
| 文件处理 | ✅ 100% | MinerU + 多格式预览 |
| 安全体系 | ✅ 100% | 7 层防护 |
| 前端重构 | ✅ 100% | 组件化 + 暗色主题 + ARIA |
| 移动端 | ✅ 100% | 独立 Vue 应用 |

**23/23 模块全部闭环可用。**

---

## 十九、后续扩展方向

| 方向 | 优先级 | 说明 |
|------|--------|------|
| 嵌入 Chat Widget | 🔥🔥🔥 | JS 片段嵌入第三方网站 |
| 多语言 i18n | 🔥🔥🔥 | 英文/日文界面 |
| 公开 API 网关 | 🔥🔥🔥 | REST API + Key 认证 + 计费 |
| 多租户 SaaS | 🔥🔥🔥 | 组织隔离 + 自助注册 |
| 语音/多模态 | 🔥🔥 | 语音输入输出 + 图片理解 |
| Agent 调试器 | 🔥🔥 | IDE 式逐步执行 + 断点 |
| 成本优化引擎 | 🔥🔥 | 智能模型路由 + 预算 |
