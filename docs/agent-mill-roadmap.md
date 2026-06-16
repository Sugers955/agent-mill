# Agent Mill 平台升级路线图

> 从「提示词型 AI 应用平台」升级为「企业级智能体管理平台」

## 现状评估

### 已有基础（20 个完整模块）

Agent Management, Model Management (多供应商), MCP Connector (stdio/sse/http),
Skill Management (atomic/composite), Solution Pack (YAML DAG), Chat Core (SSE + 工具调用),
Widget System (SVG/HTML 渲染), 文件上传/解析/下载, 定时任务调度, 审批流,
审计日志, 用户/角色/部门 RBAC, 通知系统, 收藏/空间, 移动端

### 核心差距

Agent Mill 目前的 Agent Runner 本质是 **「system prompt + 工具调用的 LLM wrapper」**，
不是真正的智能体。缺三个核心能力：

1. **记忆** — 没有跨对话持久记忆，没有用户画像，没有经验积累
2. **多智能体协作** — 没有Agent间通信，没有任务分解和分配，没有团队编排
3. **深度推理循环** — 当前是单次 LLM 调用 + 被动工具响应，不是自主的多步推理

---

## 升级目标：真正的智能体平台

### 智能体执行循环（目标架构）

```
用户输入 query (text + files)
  ↓
┌─ Agent 启动 ─────────────────────────────────────────────┐
│ 1. 加载身份 (soul.md / identity.md / user.md)            │
│ 2. 加载可用能力 (tools / skills / MCPs / packs)           │
│ 3. 加载记忆 (memory.md / memory_search 语义检索)          │
│ 4. 构建上下文 (identity + capabilities + memory + query)  │
│                                                           │
│ ┌─ Agent Loop ──────────────────────────────────────┐    │
│ │ 5. LLM 推理 (thinking + planning)                  │    │
│ │ 6. 决策: 回复用户 / 调用工具 / 委派子任务 / 请求帮助  │    │
│ │ 7. 执行工具 (MCP / Skill / 子Agent / 代码)          │    │
│ │ 8. 观察结果 (成功 / 失败 / 部分完成)                 │    │
│ │ 9. 反思: 任务完成? 需要调整策略? 需要更多工具?       │    │
│ │    → 未完成: 回到步骤 5                              │    │
│ │    → 完成: 退出循环                                  │    │
│ └────────────────────────────────────────────────────┘    │
│                                                           │
│ 10. 保存记忆 (本次经验 / 用户偏好 / 关键事实)             │
│ 11. 交付结果 (Artifacts / 文件 / 结构化数据)              │
└───────────────────────────────────────────────────────────┘
```

---

## 功能模块规划（按优先级排列）

### P0 — 核心智能体能力（让 Agent 真正「智能」）

#### 1. 记忆系统 (Memory System)

**目标**: Agent 能记住跨对话的知识、用户偏好、历史经验

```
Memory 架构:
├── 工作记忆 (Working Memory)    — 当前对话上下文，自动管理
├── 短期记忆 (Short-term)        — 最近 N 条对话摘要，会话级
├── 长期记忆 (Long-term)         — 持久化事实/规则/偏好，用户级
└── 语义记忆 (Semantic Memory)   — 向量化知识库，语义检索
```

**数据模型:**

```sql
-- 长期记忆
CREATE TABLE memories (
  id            UUID PRIMARY KEY,
  user_id       INT REFERENCES users(id),
  agent_id      INT REFERENCES agents(id),
  memory_type   VARCHAR(32),   -- fact / preference / procedure / experience
  content       TEXT,           -- 记忆内容
  summary       TEXT,           -- 摘要
  embedding     VECTOR(1536),   -- 语义向量 (pgvector)
  source        VARCHAR(64),    -- conversation / user_input / skill_output / system
  source_id     VARCHAR(128),   -- 来源 ID
  importance    FLOAT DEFAULT 0.5,
  access_count  INT DEFAULT 0,
  last_accessed TIMESTAMP,
  created_at    TIMESTAMP DEFAULT NOW(),
  expires_at    TIMESTAMP,      -- 可选过期
  is_archived   BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_memories_user_agent ON memories(user_id, agent_id);
CREATE INDEX idx_memories_embedding ON memories USING ivfflat (embedding vector_cosine_ops);
```

**Agent Runner 集成:**

```python
# 在 agent_runner.py 的上下文构建阶段
async def build_context(self, agent, user, query):
    # 1. 加载身份
    identity = load_identity_files(agent)  # soul.md, identity.md

    # 2. 加载相关记忆
    memories = await memory_service.search(
        user_id=user.id,
        agent_id=agent.id,
        query=query,
        limit=10,
        min_importance=0.3
    )

    # 3. 加载工具描述
    tools = load_agent_tools(agent)  # MCP tools + Skill descriptions

    # 4. 组装 system prompt
    system_prompt = f"""
    {identity}

    ## 你记得的关于用户的信息
    {format_memories(memories)}

    ## 可用工具
    {format_tools(tools)}

    ## 记忆管理指令
    - 对话中发现重要事实/偏好时，调用 save_memory 保存
    - 不确定的信息，调用 search_memory 查找
    - 过时的信息，调用 update_memory 更新
    """

    return system_prompt
```

**MCP 工具:**

| 工具 | 参数 | 说明 |
|------|------|------|
| `save_memory` | content, type, importance | 保存新记忆 |
| `search_memory` | query, limit | 语义搜索记忆 |
| `update_memory` | memory_id, content | 更新已有记忆 |
| `delete_memory` | memory_id | 删除记忆 |
| `list_memories` | type?, limit | 列出记忆 |

---

#### 2. 多智能体协作 (Multi-Agent Orchestration)

**目标**: 复杂任务自动分解，多个专业 Agent 协同完成

```
协作模式:
├── Router  (路由模式)    — 根据任务类型分发给最合适的 Agent
├── Pipeline (流水线模式) — 任务按步骤串行传递，每步由不同 Agent 处理
├── Parallel (并行模式)   — 多个 Agent 同时处理子任务，汇总结果
├── Debate  (辩论模式)    — 多个 Agent 独立分析同一问题，交叉验证
└── Hierarchical (层级模式) — 主 Agent 分解任务，子 Agent 执行，主 Agent 汇总
```

**数据模型:**

```sql
-- Agent Team (团队)
CREATE TABLE agent_teams (
  id          UUID PRIMARY KEY,
  name        VARCHAR(128),
  description TEXT,
  mode        VARCHAR(32),    -- router / pipeline / parallel / debate / hierarchical
  config      JSONB,          -- 模式特定配置
  created_by  INT REFERENCES users(id),
  created_at  TIMESTAMP DEFAULT NOW()
);

-- Team Member
CREATE TABLE team_members (
  id          UUID PRIMARY KEY,
  team_id     UUID REFERENCES agent_teams(id),
  agent_id    INT REFERENCES agents(id),
  role        VARCHAR(64),    -- leader / worker / reviewer / specialist
  config      JSONB,          -- 角色特定配置 (如: 专长领域、工具权限)
  sort_order  INT DEFAULT 0
);

-- Team Session (协作会话)
CREATE TABLE team_sessions (
  id          UUID PRIMARY KEY,
  team_id     UUID REFERENCES agent_teams(id),
  user_id     INT REFERENCES users(id),
  task        TEXT,            -- 原始任务描述
  status      VARCHAR(32),    -- planning / executing / reviewing / completed / failed
  result      TEXT,            -- 最终结果
  created_at  TIMESTAMP DEFAULT NOW()
);

-- Team Message (Agent间通信)
CREATE TABLE team_messages (
  id          UUID PRIMARY KEY,
  session_id  UUID REFERENCES team_sessions(id),
  from_agent  INT REFERENCES agents(id),
  to_agent    INT REFERENCES agents(id),  -- NULL = 广播
  message_type VARCHAR(32),   -- task_assign / result / question / feedback / handoff
  content     TEXT,
  created_at  TIMESTAMP DEFAULT NOW()
);
```

**核心 API:**

```
POST   /api/teams                     创建团队
GET    /api/teams                     列表
GET    /api/teams/:id                 详情
PUT    /api/teams/:id                 更新
DELETE /api/teams/:id                 删除
POST   /api/teams/:id/execute        执行团队任务 (SSE)
GET    /api/teams/:id/sessions       历史会话
GET    /api/teams/:id/sessions/:sid  会话详情 (含 Agent 间通信)
```

---

#### 3. Agent Loop 增强 (深度推理循环)

**目标**: Agent 能自主规划、执行、反思、调整策略

当前 Agent Runner 的逻辑是:
```
用户消息 → 构建 context → LLM 调用 → 工具调用 → 返回
```

升级为:
```
用户消息 → 构建 context →
  ┌─────────────────────────────────┐
  │ Loop (max_turns):               │
  │   LLM 推理 (含 thinking)        │
  │   if 需要工具 → 调用 → 观察     │
  │   if 需要子任务 → 委派 → 等待   │
  │   if 需要用户输入 → 询问 → 等待 │
  │   if 任务完成 → break            │
  │   反思: 评估进度，调整策略       │
  └─────────────────────────────────┘
→ 保存记忆 → 交付结果
```

**关键改进:**

1. **Planning Phase** — Agent 先分析任务，生成执行计划，再逐步执行
2. **Tool Result Reflection** — 工具调用后，Agent 评估结果是否符合预期，决定下一步
3. **Self-Correction** — 工具调用失败时，Agent 自动诊断原因并尝试替代方案
4. **Progress Tracking** — 用户可见 Agent 的执行进度（正在做什么，完成了什么）
5. **Turn Budget** — Agent 有最大轮次限制，接近上限时强制总结

**实现方式 (在 agent_runner.py 中):**

```python
async def run_agent_loop(self, context, max_turns=20):
    turn = 0
    plan = None

    while turn < max_turns:
        turn += 1

        # 1. LLM 推理
        response = await self.llm_call(context)

        # 2. 检查是否需要工具调用
        if response.has_tool_calls:
            for tool_call in response.tool_calls:
                # 执行工具
                result = await self.execute_tool(tool_call)

                # 反思结果
                reflection = await self.reflect(result, context)

                if reflection.needs_correction:
                    # 自动修正并重试
                    result = await self.retry_with_correction(tool_call, reflection)

                context.add_observation(result)

        # 3. 检查是否需要委派子任务
        elif response.has_delegation:
            sub_result = await self.delegate_to_agent(response.delegation)
            context.add_observation(sub_result)

        # 4. 检查是否完成
        elif response.is_final:
            return response

        # 5. 生成进度更新
        await self.emit_progress(turn, max_turns, response.status)

    # 超过轮次限制，强制总结
    return await self.force_summarize(context)
```

---

### P1 — 增强现有模块

#### 4. RAG / 知识库

```
知识库架构:
├── Knowledge Base (知识库)       — 按主题/项目组织文档集
├── Document (文档)               — 上传的文件/PDF/网页
├── Chunk (文档切片)              — 按段落/章节切片
├── Embedding (向量化)            -- 文本 → 向量 (OpenAI/bge/etc)
└── Retrieval (检索)              — 查询 → 相似度匹配 → 返回 TopK
```

```sql
CREATE TABLE knowledge_bases (
  id          UUID PRIMARY KEY,
  name        VARCHAR(128),
  description TEXT,
  embedding_model VARCHAR(64),   -- text-embedding-3-small / bge-large-zh
  chunk_strategy  VARCHAR(32),   -- fixed / sentence / semantic
  chunk_size      INT DEFAULT 512,
  chunk_overlap   INT DEFAULT 64,
  created_by  INT REFERENCES users(id),
  created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE kb_documents (
  id          UUID PRIMARY KEY,
  kb_id       UUID REFERENCES knowledge_bases(id),
  title       VARCHAR(256),
  source_type VARCHAR(32),       -- upload / url / api
  source_url  TEXT,
  file_path   TEXT,
  status      VARCHAR(32),       -- pending / processing / ready / failed
  chunk_count INT DEFAULT 0,
  created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE kb_chunks (
  id          UUID PRIMARY KEY,
  doc_id      UUID REFERENCES kb_documents(id),
  kb_id       UUID REFERENCES knowledge_bases(id),
  content     TEXT,
  metadata    JSONB,             -- {page, section, title, ...}
  embedding   VECTOR(1536),
  created_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_chunks_kb_embedding ON kb_chunks
  USING ivfflat (embedding vector_cosine_ops);
```

**Agent 绑定知识库:**

```sql
CREATE TABLE agent_knowledge (
  agent_id    INT REFERENCES agents(id),
  kb_id       UUID REFERENCES knowledge_bases(id),
  PRIMARY KEY (agent_id, kb_id)
);
```

**MCP 工具:**

| 工具 | 说明 |
|------|------|
| `search_knowledge` | 语义搜索知识库 |
| `list_knowledge_bases` | 列出可用知识库 |

#### 5. 工作流可视化编辑器

当前 Solution Pack 是纯 YAML 编辑。升级为拖拽式 DAG 编辑器：

```
编辑器功能:
├── 画布拖拽节点 (skill / condition / parallel / sub_agent / human_approval)
├── 连线定义数据流
├── 节点配置面板 (参数、模板变量、超时、失败策略)
├── 实时校验 (环路检测、孤立节点、必填字段)
├── 预览生成 YAML
└── 运行状态可视化 (执行到哪个节点、成功/失败/进行中)
```

前端实现: Vue 3 + Vue Flow (或 @antv/x6)

#### 6. Skill 执行引擎增强

当前 atomic skill 的 `path` 模式只是返回 SKILL.md 让 LLM 自行理解。
增强为可编程执行:

```
Skill 类型体系:
├── prompt    — 纯提示词注入 (当前 path 模式) [已有]
├── callable  — 执行 Python 脚本 [已有但待完善]
├── composite — YAML DAG 工作流 [已有]
├── agent     — 启动独立子Agent执行 [新增]
└── workflow  — 可视化工作流节点 [新增]
```

新增 `agent` 类型 Skill:
- Skill 定义中指定用哪个 Agent 执行
- 主 Agent 调用此 Skill 时，启动子 Agent 对话
- 子 Agent 有自己的 system prompt、工具集、记忆
- 子 Agent 完成后返回结果给主 Agent

---

### P2 — 平台增强

#### 7. 对话分支 (Conversation Branching)

```sql
-- 消息增加 parent_id
ALTER TABLE messages ADD COLUMN parent_id UUID REFERENCES messages(id);

-- 对话变为树结构
-- 用户可以回到任意消息，编辑后重新发送，产生新分支
```

#### 8. Token 用量统计面板

```
统计维度:
├── 按用户 (谁用得多)
├── 按 Agent (哪个 Agent 消耗最大)
├── 按模型 (不同模型成本)
├── 按时间 (趋势图)
└── 成本估算 (基于模型定价)
```

#### 9. Agent 模板市场

```
市场功能:
├── 管理员发布 Agent 模板 (预配置 prompt + tools + skills)
├── 用户从模板创建 Agent (一键部署)
├── 模板分类 (客服 / 写作 / 编程 / 分析 / 翻译 ...)
└── 模板评分和评论
```

#### 10. 商户 SKILL+MCP 体系 (之前的 commerce-demo 方案)

在上述核心能力到位后，商户体系作为垂直应用场景接入。

---

## 实施路线 (Phase)

### Phase 1 — 记忆系统 (2-3 周)
- 集成 pgvector 到 PostgreSQL
- 实现 Memory CRUD API
- 实现 embedding 生成 (OpenAI / bge)
- Agent Runner 集成记忆加载和保存
- 前端: 记忆管理面板

### Phase 2 — Agent Loop 增强 (2 周)
- 重构 agent_runner.py 为多轮循环
- 加入 planning / reflection / self-correction
- 加入进度追踪和 SSE 进度事件
- 前端: 执行进度展示

### Phase 3 — 多智能体协作 (3-4 周)
- Agent Team 数据模型和 API
- 5 种协作模式实现 (Router → Pipeline → Parallel → Debate → Hierarchical)
- Agent 间通信机制
- 前端: 团队管理 + 协作可视化

### Phase 4 — RAG 知识库 (2-3 周)
- 知识库 CRUD
- 文档上传 → 切片 → 向量化管道
- 语义检索 API
- Agent 绑定知识库
- 前端: 知识库管理

### Phase 5 — 工作流编辑器 + Skill 增强 (3 周)
- Vue Flow / @antv/x6 集成
- DAG 拖拽编辑器
- 运行状态可视化
- Skill agent 类型实现

### Phase 6 — 平台增强 (持续)
- 对话分支
- Token 统计面板
- Agent 模板市场
- 商户 SKILL+MCP 体系

---

## 技术选型

| 需求 | 选型 | 理由 |
|------|------|------|
| 向量数据库 | pgvector (PostgreSQL 扩展) | 不引入新组件，复用现有 PG |
| Embedding | OpenAI text-embedding-3-small + bge-large-zh | 中英文双语支持 |
| 工作流编辑器 | Vue Flow | Vue 3 生态，轻量，DAG 场景成熟 |
| Agent 间通信 | PostgreSQL + SSE | 不引入消息队列，保持简单 |
| 记忆过期清理 | 定时任务 (已有调度器) | 复用现有基础设施 |

## 文件变更预估

| Phase | 后端新增/修改 | 前端新增/修改 |
|-------|-------------|-------------|
| Phase 1 | ~15 文件 | ~5 文件 |
| Phase 2 | ~5 文件 (核心重构) | ~3 文件 |
| Phase 3 | ~20 文件 | ~10 文件 |
| Phase 4 | ~15 文件 | ~8 文件 |
| Phase 5 | ~5 文件 | ~15 文件 |
