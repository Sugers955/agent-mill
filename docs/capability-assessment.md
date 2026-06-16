# Agent Mill 能力评估与深化路线

> 本文档基于对**实际代码**的核查(非仅文档描述),系统回答三个问题:
> 1. **现在能干什么** —— 当前已落地、可直接使用的业务能力
> 2. **能达到什么效果** —— 具体场景下用户和企业的体感
> 3. **该往哪深化** —— 按「企业 / 用户」两个维度拆解,给出可执行的优先级路线
>
> 与现有文档的分工:
> - [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) —— 功能全景(已实现什么)
> - [agent-mill-roadmap.md](agent-mill-roadmap.md) —— 技术架构升级路线(记忆/多Agent/Agent Loop)
> - **本文档** —— 现状能干什么 + 商业化深化路线(以"能否做企业级数字员工平台"为评判标准)

---

## 一、项目本质定位

Agent Mill 是一个 **「AI 智能体的生产与运行平台」**:

```
管理员(配置)──→ 搭建智能体 ──→ 终端用户(使用)
   │              │                  │
   │   ┌──────────┴──────────┐       │
   │   │ 选模型 + 降级模型     │       │
   │   │ 写 system_prompt     │       │
   │   │ 挂 Skill(能力插件)   │◀─────┤ 用户通过对话使用
   │   │ 挂 MCP(接外部系统)   │       │ 智能体调用工具 / 产出文件
   │   │ 挂 Pack(编排流程)    │       │ 文件预览 / 表单交互
   │   │ 配上传策略 + 可见角色 │       │
   │   └─────────────────────┘       │
```

**一句话**:一套后台,多个智能体;管理员配置,普通用户使用;提供 Skill / MCP / 模型 / 文件 / 安全 / 审计闭环。

**代码规模**:后端约 9,400 行 Python,前端约 12,900 行 Vue/TS,核心 `agent_runner.py` 2,212 行,`pack_engine.py` 780 行。88 个 REST 端点 + 1 个 SSE 流式端点,14 张数据库表。

---

## 二、现在能干什么(已落地能力,无需开发)

> 以下能力均经代码核实,非文档宣称。每项标注实现位置与成熟度。

### 2.1 核心运行时能力(平台地基)

| 能力 | 实现位置 | 成熟度 | 说明 |
|---|---|---|---|
| **双路径流式对话** | `agent_runner.py` | ⭐⭐⭐⭐⭐ | Anthropic 路径(Claude Agent SDK 真流式)+ OpenAI 兼容路径(DeepSeek/Qwen/GLM/OpenAI,8 轮工具循环);支持 DeepSeek-Reasoner 思考过程 |
| **模型降级** | `agent_runner.py` | ⭐⭐⭐⭐ | 主模型失败自动切 fallback_model(仅未流式输出文本时触发) |
| **Effort 分级推理** | `agent_runner.py:132` | ⭐⭐⭐⭐ | low/medium/high/xhigh/max 五级,Anthropic 映射 thinking budget,OpenAI 映射 reasoning_effort |
| **多轮上下文** | `api/chat.py` | ⭐⭐⭐⭐ | 默认保留最近 30 条消息,持久化到 messages 表 |

### 2.2 Skill 三态能力系统(任务插件化)

> Skill 是"能力包",让一个普通 Agent 变成"会做 PPT / 会查数据库 / 会写代码"的专业员工。

| Skill 类型 | 执行方式 | 内置工具支持 |
|---|---|---|
| **path 型 atomic** | ZIP 上传 SKILL.md + 资源,Anthropic 走 cwd 文件级加载,OpenAI 路径 `run_skill_script` 进程内执行 Python | `_read_skill_file`、`save_output_file`、`run_skill_script` |
| **callable 型 atomic** | `module.path:func` 直接 import 调用(仅 admin) | — |
| **composite (YAML DAG)** | `dag_executor.py` 拓扑分层 + 同层并行 | — |

**安全隔离**(`agent_runner.py:1998`):每次请求把选中 Skill symlink 进临时目录 `.claude/skills/`,模型物理上看不到别的 Skill;上传时 AST 级扫描(`skill_scan.py`),禁 eval/exec/subprocess。

### 2.3 MCP 连接器(接企业内部系统)

> MCP 是"对接外部系统的标准接口",让智能体能查 ERP、调 OA、操作数据库。

- **三种 transport**:stdio(子进程)/ sse(HTTP 长连接)/ http(Streamable HTTP)
- **工具列表缓存**:存 `tool_summaries_json`,避免每次连接 MCP 服务器
- **按 Agent 隔离**:每个 Agent 独立挂载,运行时按需注入
- **实时工具列表**:管理端可 ping + 列举工具 + 展示 input_schema

### 2.4 Solution Pack(复杂任务编排)⭐ 关键能力

> Pack 是"声明式 DAG 业务流程",比 composite Skill 更重:支持持久化、断点恢复、人工审批、子 Agent 委托。这是做"复杂任务型智能体"的骨架。

**6 种节点类型**(`pack_engine.py`,780 行,完整实现):

| 节点 | 功能 | 实现位置 |
|---|---|---|
| `skill` | 调用 Skill 执行任务(含 atomic skill 的 LLM mini-loop) | `_exec_skill_node:321` |
| `parallel_group` | 并行组,all_success/first_success/n_of_m 等待策略 | `_exec_parallel_group:459` |
| `aggregator` | 聚合多上游输出,支持计算字段(如 risk_score) | `_exec_aggregator:476` |
| `condition` | 条件分支,rule 模式 + llm_judge 占位 | `_exec_condition:491` |
| `sub_agent` | 委托给另一个 Agent 执行子任务 | `_exec_sub_agent:508` |
| `human_approval` | 创建审批记录并暂停,管理端审批后 resume | `_exec_human_approval:525` |
| `mcp_invoke` | 直接调用 MCP 工具并提取结果 | `_exec_mcp_invoke:549` |

**关键特性**:
- ✅ DAG 拓扑校验 + 环检测(`validate_pack:88`)
- ✅ 断点恢复(`resume:136`,从 `context_snapshot` 重建)
- ✅ 人工审批暂停/恢复(`pack_approvals` 表 + `pack_waiting_approval` 事件)
- ✅ 模板变量 `{{inputs.xxx}}` / `{{node_id.output.field}}` / `{{expr|default(v)}}`
- ✅ 每节点执行后快照持久化到 `pack_runs.context_snapshot`
- ✅ 并发控制(max_parallel)+ 超时(timeout_ms)+ 失败策略(fail_strategy)

### 2.5 定时任务系统(数字员工"自动上班")

> 让智能体按计划自动执行,这是"员工"和"工具"的区别之一。

- **调度类型**:manual / once / cron(asyncio 自实现,无外部依赖,`task_runner.py:312`)
- **执行流程**:新建 Conversation → 加载 Agent 上下文 → 消费 SSE 流 → 持久化 assistant 消息 → 更新 TaskRun
- **并发策略**:skip(跳过上一次还在跑的)/ queue
- **通知**:站内(`notifications` 表)+ 邮件(SMTP),触发条件 always/success/failure
- **交互检测**:任务中触发 `ask_user_pick/form` 自动标记 failed(任务不该等人)

### 2.6 文件处理全链路

| 环节 | 能力 |
|---|---|
| **上传** | 多文件,per-user 物理隔离(`storage/uploads/<user_id>/`),Agent 上传策略(ext 白名单 / 大小 / 单次数) |
| **解析** | MinerU 云端/私有化 → 失败回退本地库(pypdf/python-docx/openpyxl/bs4);截断 head 60% + tail 40%,硬上限 20K |
| **直传模式** | `parse_mode=never`,原文件交工具处理(盖章 PDF / 视觉模型场景),签发 60 分钟短期 token |
| **预览** | HTML iframe / PDF / Markdown / 代码 / SVG / 图片;Word/PPT/Excel 仅下载 |
| **下载** | 一次性 token / 24h 过期 / user_id 校验 / 路径穿越拒绝 |
| **生命周期** | 30 天未引用自动清理(`last_used_at` 跟踪) |

### 2.7 生成式 UI(数字员工能"看懂并操作")

| 类型 | 能力 | 组件 |
|---|---|---|
| **Widget** | LLM 生成 SVG/HTML,iframe 沙箱流式渲染 | `WidgetRenderer.vue` |
| **UI Schema 交互** | 工具结果携带 `__ui__`,渲染交互组件 | CardList / DynamicForm / ConfirmDialog / DataTable / StatusTimeline |
| **主动交互** | `ask_user_pick`(卡片选择)、`ask_user_form`(动态表单) | 强制注入,模型必须用 |

### 2.8 安全与治理(7 层,政企刚需)

| 层 | 机制 | 代码位置 |
|---|---|---|
| 1 工具白名单 | Anthropic 路径禁 Bash/Write/Edit | `agent_runner.py:2059` |
| 2 system_prompt 安全前缀 | 反 prompt injection,硬编码注入 | `security_rules.py` |
| 3 输入正则过滤 | 12 条规则,shell/injection/敏感路径 → 400 + 审计 | `security_rules.py` |
| 4 Skill 静态扫描 | shell pattern + Python AST 黑名单 | `skill_scan.py` |
| 5 文件 cwd 沙箱 | per-agent 临时目录 | `agent_runner.py:1998` |
| 6 下载令牌 | 一次性 / 24h / user_id / 路径穿越 | `services/downloads.py` |
| 7 API Key 加密 | Fernet 对称加密存储 | `crypto.py` |

### 2.9 权限与审计

- **RBAC 三角色**:admin(全部)/ operator(配置,不管用户)/ user(仅对话)
- **部门树**:支持循环依赖检测、强制删除
- **Agent 可见性**:`role_agent_grants` 控制角色能看到哪些 Agent
- **双表审计**:`audit_logs`(管理操作+安全拦截)+ `call_logs`(token/延迟/状态/模型,每次对话一条)

---

## 三、能达到什么效果(具体场景示例)

### 场景 1:HR 助手智能体(岗位型数字员工)

**配置**:建 Agent「HR 助手」,system_prompt 写角色,挂「员工查询」MCP(对接 HR 系统 API)。

**效果**:
- 员工问"张三还剩多少年假"→ Agent 调 MCP 查 → 回答
- 复杂需求挂 Pack「离职流程」:提申请 → `human_approval` 等领导批 → 自动生成交接清单 → 归档
- 全程有 `call_logs` / `audit_logs` 记录

### 场景 2:财务报表自动化(任务型智能体)

**配置**:建 Agent + 挂「Excel 生成」Skill + 配 cron 每天 8:00 跑。

**效果**:
- 任务执行:读 ERP 数据(走 MCP)→ 生成日报 Excel(`save_output_file`)→ 邮件通知财务总监
- 跑出来的对话历史可回溯,失败有 TaskRun 记录 + 通知
- 产物文件登记到 `download_tokens`,过期自动失效

### 场景 3:政务政策问答(知识型智能体)

**配置**:建 Agent,上传政策 PDF(自动 MinerU 解析),配可见角色。

**效果**:
- 群众上传"我的情况是 XXX,能申请什么补贴"→ Agent 读文件 + 推理
- 信息不全时用 `ask_user_form` 收集缺失字段
- 用 Widget 画流程图解释"申请流程",右侧分屏预览

### 场景 4:研发知识助手(多技能组合)

**配置**:建 Agent,挂「代码生成」「文档生成」「架构图」三个 Skill + 「Jira」MCP。

**效果**:
- "帮我画一个微服务架构图"→ 命中架构图 Skill,Widget 流式渲染 SVG
- "把这个需求拆成 Jira 任务"→ 调 Jira MCP 批量建任务
- 产物文件可下载,对话可收藏到个人空间

---

## 四、关键缺失能力(经代码核实)

> 以下能力是"数字员工/复杂任务型智能体平台"的必备项,当前代码库**完全没有**(grep 核实),构成深化的核心方向。

### 4.1 面向「企业」的缺失(平台治理与集成)

| 缺失 | 核查结果 | 影响 | 难度 |
|---|---|---|---|
| **🔴 RAG 知识库** | grep `pgvector/embedding/knowledge_base` 完全为零 | 政企第一需求,政策/制度/FAQ 问答无法实现 | 中高 |
| **🔴 SSO / LDAP / OIDC** | grep `oidc/ldap/sso/saml` 完全为零,仅本地账号密码 | 无法接入企业 AD/统一身份,企业进不来 | 中 |
| **🔴 成本与配额控制** | grep `quota/rate_limit/cost` 为零(仅 `call_logs` 记 token,无聚合拦截) | 无法控制部门/用户 token 消耗 | 中 |
| **🔴 IM 接入** | grep `webhook/dingtalk/wechat_work/lark` 完全为零 | 数字员工无法住进钉钉/企微/飞书 | 中 |
| **🟡 多租户** | grep `tenant/workspace` 为零 | 无法卖给多个企业客户 | 中高 |
| **🟡 对象存储** | 仅本地磁盘,无 S3/MinIO | 大文件、横向扩展、备份受限 | 低 |
| **🟡 监控告警** | 有日志无告警 | 生产运维盲区 | 低 |

### 4.2 面向「智能体」的缺失(让员工更像员工)

| 缺失 | 核查结果 | 影响 | 难度 |
|---|---|---|---|
| **🔴 持久记忆** | grep `memory/memories` 无表无代码 | 数字员工的"灵魂",每次对话从零开始——员工和工具的本质区别 | 高 |
| **🔴 多 Agent 团队协作** | 仅 Pack 内 `sub_agent` 委托,无 Router/Pipeline/Debate/Hierarchical | 复杂任务无法自动分解、多专业无法协同 | 高 |
| **🔴 深度推理循环** | grep `reflect/planning/self_correct` 完全为零 | 当前是"单次 LLM + 被动工具",不是自主多步推理 Agent | 高 |
| **🟡 工作流可视化编辑** | Pack 只能写 YAML | 业务人员搭不了流程,依赖开发 | 中 |
| **🟡 对话分支** | 线性对话,无 parent_id 树 | 探索式工作、回退重试受限 | 中 |
| **🟡 Agent 模板市场** | 无 | 配置门槛高、经验难复用 | 中 |
| **🟡 主动事件触发** | 仅定时 cron | 外部事件无法驱动智能体 | 中 |

> 注:其中记忆 / 多 Agent 协作 / 深度推理循环三项,**在 `agent-mill-roadmap.md` 已有详细技术设计**(P0),说明项目作者已意识到,只是尚未实现。

---

## 五、深化路线(按优先级,可执行)

### 总原则

深化顺序遵循「**先让企业能用 → 再让员工像员工 → 最后让智能体干大事**」。三个阶段的 ROI 递减但价值递增。

```
第一阶段(企业准入)    第二阶段(数字员工灵魂)   第三阶段(复杂任务)     第四阶段(平台化)
   ↓                       ↓                       ↓                      ↓
SSO + RAG + 配额    →   记忆 + IM + 事件    →   多Agent + Loop + 编辑器 →  多租户 + 市场 + 监控
让企业敢用/能用          让员工有记忆/在IM里         让智能体能干大事          让产品能卖
```

---

### 🥇 第一阶段:补齐"企业准入"三件套

> **目标:让企业愿意采购、能用起来。** 这三项是企业 IT 的硬门槛,缺一进不去。

#### 1. SSO / LDAP 对接(1-2 周)

- **现状**:`api/auth.py` 仅本地账号密码 + JWT(bcrypt)
- **补什么**:OIDC / LDAP 认证源,对接企业 Active Directory、Azure AD、钉钉/企微企微身份
- **复用点**:JWT 双 token 机制保留,只在登录入口加一个"外部 IdP 校验"分支;角色映射(IdP group → Agent Mill role)
- **价值**:**企业准入门槛**,不接进不来

#### 2. RAG 知识库(2-3 周)

- **现状**:`grep pgvector/embedding` 完全为零
- **补什么**:
  - pgvector 扩展(复用现有 PostgreSQL,不引入新组件)
  - 数据表:`knowledge_bases` / `kb_documents` / `kb_chunks`(含 embedding)
  - 上传文档 → **复用现有 `file_parser.py` 解析为 Markdown** → 切片 → 向量化(OpenAI / bge)
  - MCP 工具:`search_knowledge` / `list_knowledge_bases`
  - Agent 绑定知识库(`agent_knowledge` 关联表)
  - 前端:知识库管理页(上传 / 切片预览 / 检索测试)
- **复用点**:`file_parser.py` 已有完整解析链路,**RAG 只需在它后面加"切片+向量化"一步**
- **价值**:**政企第一需求**,政策/制度/FAQ 问答

#### 3. 成本与配额统计看板(1-2 周)

- **现状**:`call_logs` 表已存 `tokens_in/tokens_out/latency_ms/status/model_id`(每次对话一条),但无聚合、无拦截
- **补什么**:
  - 配额表:`user_quotas` / `department_quotas`(按月 token 上限)
  - 拦截层:发消息前检查配额,超额返回友好提示
  - 统计看板:按用户/部门/Agent/模型 维度的 token 用量 + 趋势图 + 成本估算(基于模型定价)
- **复用点**:`call_logs` 数据已齐全,纯加聚合查询 + 前端图表
- **价值**:**企业算账、控成本**,敢放开用

---

### 🥈 第二阶段:补齐"数字员工"灵魂

> **目标:从"一次性问答工具"升级为"记得事的员工"。**

#### 4. 持久记忆系统(2-3 周,roadmap P0)

- **现状**:无任何记忆机制,每次对话从零开始
- **补什么**:
  - `memories` 表(user_id / agent_id / type / content / embedding / importance / source)
  - pgvector 语义检索(与 RAG 共用向量基础设施)
  - 记忆类型:fact(事实)/ preference(偏好)/ procedure(流程)/ experience(经验)
  - 内置工具:`save_memory` / `search_memory` / `update_memory` / `delete_memory`
  - Agent Runner 集成:构建上下文时自动检索相关记忆注入 system prompt
- **复用点**:`agent_runner.py` 已有 `_build_*_tools` 内置工具模式(`save_output_file` 等),记忆工具**照搬这套模式**,模型调用方式完全一致
- **价值**:**数字员工的分水岭**——"王总您好,上次您让我跟进的 XX 项目…"vs"请问您是谁"

#### 5. IM 接入(钉钉/企微/飞书,1-2 周)

- **现状**:完全无 IM 接入
- **补什么**:
  - Webhook 网关:IM 消息 → 转发到 Agent Mill 对话 API
  - 回调:Agent 回复 → 推回 IM(支持 markdown / 卡片)
  - 多 IM 适配器(钉钉、企微、飞书,接口各异但模式相同)
- **价值**:**让员工在日常工具里用**,不用单独开系统

#### 6. 主动事件触发(1 周)

- **现状**:仅 cron 定时触发
- **补什么**:事件驱动 —— 外部系统 webhook → 触发指定 Agent / Pack 执行
  - 如:Jira 新建 issue → 触发"需求分析"Agent;GitLab MR → 触发"代码审查"Agent
- **复用点**:定时任务调度框架(`task_runner.py`)可扩展为事件触发器
- **价值**:智能体从"被动应答"到"主动响应业务事件"

---

### 🥉 第三阶段:补齐"复杂任务"能力

> **目标:能处理需要多步骤、多角色、多工具的复杂业务。**

#### 7. 多 Agent 团队协作(3-4 周,roadmap P0)

- **现状**:仅 Pack 内 `sub_agent` 节点委托(静态)
- **补什么**:5 种动态协作模式
  - **Router**:根据任务类型路由到最合适的 Agent
  - **Pipeline**:任务按步骤串行,每步不同 Agent
  - **Parallel**:多 Agent 并行处理子任务,汇总
  - **Debate**:多 Agent 独立分析,交叉验证
  - **Hierarchical**:主 Agent 分解任务,子 Agent 执行,主 Agent 汇总
- **复用点**:`pack_engine._exec_sub_agent` 已实现委托逻辑,可作为积木;`agent_teams` / `team_members` / `team_messages` 表设计见 roadmap
- **价值**:**复杂任务自动分解**,多专业协同

#### 8. Agent Loop 深度推理(2-3 周,roadmap Phase 2)⚠️ 高风险

- **现状**:`agent_runner.py` 是"单次 LLM + 被动工具响应",无反思
- **补什么**:重构为循环 —— `plan → act → observe → reflect → 调整`
  - Planning Phase:先生成执行计划再执行
  - Tool Result Reflection:工具调用后评估结果
  - Self-Correction:失败自动诊断 + 替代方案
  - Progress Tracking:用户可见执行进度
  - Turn Budget:接近上限强制总结
- **⚠️ 风险提示**:`agent_runner.py` 2212 行承载了双路径+工具+Widget+沙箱,**改它牵一发动全身**。必须**先补自动化测试**(当前零测试)再动。建议放第三阶段末、前两阶段稳定后进行。

#### 9. 工作流可视化编辑器(3 周)

- **现状**:Pack 只能写 YAML,门槛高
- **补什么**:Vue Flow 拖拽式 DAG 编辑器
  - 画布拖节点(skill/condition/parallel/sub_agent/human_approval)
  - 连线定义数据流,节点配置面板
  - 实时校验(环路/孤立/必填)
  - 运行状态可视化(执行到哪个节点)
- **价值**:**业务人员自助搭流程**,不依赖开发

---

### 🏅 第四阶段:平台化与商业化

> **目标:从"项目"变成"产品",能卖给多个客户。**

#### 10. 多租户隔离(2-3 周)
- tenant_id 贯穿所有表 + 数据库 schema 分离
- 租户级配置(模型 / Skill / Agent 隔离)

#### 11. Agent 模板市场(2 周)
- 管理员发布模板(预配置 prompt + tools + skills)
- 用户一键从模板创建 Agent
- 分类 / 评分 / 评论

#### 12. 对象存储 + 监控告警(1-2 周)
- S3/MinIO 适配层(替换本地磁盘)
- Prometheus 指标 + 异常告警(token 突增 / 错误率 / 延迟)

---

## 六、深化时的「复用」与「风险」备忘

### 6.1 有现成脚手架可复用的(别从零造)

| 深化方向 | 可复用的现成机制 |
|---|---|
| **RAG 知识库** | `file_parser.py` 完整解析链路,只需加"切片+向量化" |
| **记忆系统** | `agent_runner.py` 的 `_build_*_tools` 内置工具模式,记忆工具照搬 |
| **多 Agent 协作** | `pack_engine._exec_sub_agent` 委托逻辑可作积木 |
| **配额统计** | `call_logs` 数据已齐全,纯加聚合 |
| **事件触发** | `task_runner.py` 调度框架可扩展为事件触发器 |

### 6.2 必须警惕的风险点

| 风险 | 说明 | 应对 |
|---|---|---|
| **`agent_runner.py` 重构** | 2212 行单文件,改它牵一发动全身 | 放第三阶段末,先补测试 |
| **数据库迁移机制** | 用 `IF NOT EXISTS` 而非 Alembic,长期有 schema 漂移风险 | 深化前先接入 Alembic 规范化 |
| **零自动化测试** | 9400 行后端无测试目录 | 深化前补关键路径测试(对话流 / Pack 执行 / Skill 扫描) |
| **`pack_engine.py:709` 有 eval()** | condition 节点表达式求值,虽有 `__builtins__={}` 沙箱 | 安全审计注意,建议替换为受限表达式解析器 |
| **未提交的品牌重命名** | 工作区有 h3c→agent_mill 改动未 commit | 深化前先 commit 干净工作区 |

---

## 七、总评

**Agent Mill 现在是一个「工程完成度很高、但智能深度待补」的智能体应用平台。**

- **它的价值不在"现在能干多复杂的事",而在"它把智能体平台的骨架搭对了"**——Skill / MCP / Pack 三件套 + 7 层安全 + 双模型路径,这是大多数竞品没做扎实的部分。
- **它的短板在"智能深度"**:记忆、多 Agent 协作、深度推理循环这三项构成"智能体"和"工具"的分水岭,目前为零。
- **补齐 RAG / 记忆 / SSO / IM 四件套后,它能成为企业数字员工平台的有力竞争者**。

**建议路径**:第一阶段(企业准入,4-7 周)→ 第二阶段(数字员工灵魂,4-6 周)→ 第三阶段(复杂任务,8-10 周)→ 第四阶段(平台化,5-7 周)。总周期约 5-7 个月,可与商业化并行(第一阶段完成即可开始内测)。

---

> **下一步**:本文档作为深化讨论的基线。建议先就「第一阶段三项(SSO / RAG / 配额)的具体技术方案与排期」展开深入探讨。
