# API 文档

本文档提供 Agent Mill REST API 端点参考。

---

## 目录

- [基础信息](#基础信息)
- [认证方式](#认证方式)
- [API 端点](#api-端点)
  - [认证](#认证)
  - [用户管理](#用户管理)
  - [模型管理](#模型管理)
  - [数字员工](#数字员工)
  - [技能管理](#技能管理)
  - [连接器管理](#连接器管理)
  - [知识库](#知识库)
  - [对话](#对话)
  - [工作流](#工作流)
  - [审计日志](#审计日志)
- [错误码](#错误码)

---

## 基础信息

| 项目 | 值 |
|------|-----|
| 基础路径 | `/api/v1` |
| 内容类型 | `application/json` |
| 认证方式 | Bearer Token (JWT) |
| API 版本 | 1.0 |

### 请求格式

所有请求需要在 Header 中携带 JWT Token：

```
Authorization: Bearer <access_token>
```

### 响应格式

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| code | integer | 状态码，0 表示成功 |
| message | string | 状态信息 |
| data | object | 响应数据 |

---

## 认证方式

### 本地登录

**POST** `/api/v1/auth/login`

**请求体**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 是 | 用户名 |
| password | string | 是 | 密码 |

**响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "user": {
      "id": 1,
      "username": "admin",
      "role": "admin"
    }
  }
}
```

### 刷新 Token

**POST** `/api/v1/auth/refresh`

**请求头**：

```
Authorization: Bearer <refresh_token>
```

**响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer"
  }
}
```

### SSO 登录

**GET** `/api/v1/auth/sso/authorize`

**响应**：重定向到 SSO 提供商的授权页面

**GET** `/api/v1/auth/sso/callback`

**查询参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| code | string | 授权码 |
| state | string | CSRF 防护状态 |

---

## 用户管理

### 获取用户列表

**GET** `/api/v1/admin/users`

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | integer | 否 | 页码，默认 1 |
| page_size | integer | 否 | 每页数量，默认 20 |
| role | string | 否 | 筛选角色 |
| keyword | string | 否 | 搜索关键词 |

**响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": 1,
        "username": "admin",
        "display_name": "管理员",
        "role": "admin",
        "department": "技术部",
        "created_at": "2026-01-01T00:00:00Z"
      }
    ],
    "total": 100,
    "page": 1,
    "page_size": 20
  }
}
```

### 创建用户

**POST** `/api/v1/admin/users`

**请求体**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 是 | 用户名 |
| password | string | 是 | 密码 |
| display_name | string | 否 | 显示名称 |
| role | string | 是 | 角色：admin/operator/user |
| department_id | integer | 否 | 部门 ID |

### 更新用户

**PUT** `/api/v1/admin/users/{user_id}`

### 删除用户

**DELETE** `/api/v1/admin/users/{user_id}`

---

## 模型管理

### 获取模型列表

**GET** `/api/v1/admin/models`

**响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "id": 1,
      "name": "Claude 3.5 Sonnet",
      "provider": "anthropic",
      "model_id": "claude-3-5-sonnet-20241022",
      "has_api_key": true,
      "is_active": true,
      "created_at": "2026-01-01T00:00:00Z"
    }
  ]
}
```

### 创建模型配置

**POST** `/api/v1/admin/models`

**请求体**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 显示名称 |
| provider | string | 是 | 供应商：anthropic/openai/deepseek/qwen/glm |
| model_id | string | 是 | 模型 ID |
| api_key | string | 是 | API Key |
| base_url | string | 否 | 自定义端点 |
| extra_params_json | string | 否 | 额外参数 JSON |

### 测试模型连通性

**POST** `/api/v1/admin/models/{model_id}/test`

**响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "success": true,
    "latency_ms": 523,
    "response_preview": "Hello, I'm Claude..."
  }
}
```

---

## 数字员工

### 获取数字员工列表

**GET** `/api/v1/admin/agents`

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | integer | 否 | 页码 |
| page_size | integer | 否 | 每页数量 |
| keyword | string | 否 | 搜索关键词 |

### 创建数字员工

**POST** `/api/v1/admin/agents`

**请求体**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 名称 |
| code | string | 是 | 唯一标识 |
| description | string | 否 | 描述 |
| system_prompt | string | 否 | 系统提示词 |
| model_id | integer | 是 | 主模型 ID |
| fallback_model_id | integer | 否 | 降级模型 ID |
| max_turns | integer | 否 | 最大对话轮次 |
| effort | string | 否 | 推理努力度：low/medium/high/xhigh/max |
| skill_ids | array | 否 | 关联技能 ID 列表 |
| mcp_ids | array | 否 | 关联连接器 ID 列表 |
| knowledge_base_ids | array | 否 | 关联知识库 ID 列表 |

### 更新数字员工

**PUT** `/api/v1/admin/agents/{agent_id}`

### 删除数字员工

**DELETE** `/api/v1/admin/agents/{agent_id}`

**注意**：此操作需要审批。

### 获取用户可见的数字员工

**GET** `/api/v1/chat/agents`

**响应**：返回当前用户有权限使用的数字员工列表。

---

## 技能管理

### 获取技能列表

**GET** `/api/v1/admin/skills`

**响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "id": 1,
      "name": "代码执行",
      "code": "code_executor",
      "type": "callable",
      "description": "执行 Python 代码",
      "is_active": true
    }
  ]
}
```

### 创建技能

**POST** `/api/v1/admin/skills`

**path 型技能**（ZIP 上传）：

```
Content-Type: multipart/form-data

file: <zip_file>
name: 技能名称
code: skill_code
description: 技能描述
```

**callable 型技能**：

```json
{
  "name": "技能名称",
  "code": "skill_code",
  "type": "callable",
  "callable_path": "module.path:function",
  "description": "技能描述"
}
```

### 上传技能文件

**POST** `/api/v1/admin/skills/upload`

```
Content-Type: multipart/form-data

file: <zip_file>
```

**ZIP 文件结构**：

```
skill.zip
├── SKILL.md          # 技能说明文档（必需）
├── main.py           # 入口脚本（可选）
├── requirements.txt  # 依赖（可选）
└── resources/        # 资源文件（可选）
```

---

## 连接器管理

### 获取连接器列表

**GET** `/api/v1/admin/mcp-connectors`

### 创建连接器

**POST** `/api/v1/admin/mcp-connectors`

**请求体**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 名称 |
| code | string | 是 | 唯一标识 |
| transport_type | string | 是 | 传输协议：stdio/sse/http |
| config_json | string | 是 | 配置 JSON |

**stdio 配置示例**：

```json
{
  "command": "python",
  "args": ["-m", "my_mcp_server"],
  "env": {}
}
```

**sse 配置示例**：

```json
{
  "url": "http://localhost:8080/sse"
}
```

**http 配置示例**：

```json
{
  "url": "http://localhost:8080/mcp"
}
```

### 测试连接器

**POST** `/api/v1/admin/mcp-connectors/{connector_id}/test`

### 获取工具列表

**POST** `/api/v1/admin/mcp-connectors/{connector_id}/tools`

---

## 知识库

### 获取知识库列表

**GET** `/api/v1/admin/knowledge-bases`

### 创建知识库

**POST** `/api/v1/admin/knowledge-bases`

**请求体**：

```json
{
  "name": "产品文档",
  "description": "产品帮助文档和常见问题"
}
```

### 上传文档

**POST** `/api/v1/admin/knowledge-bases/{kb_id}/documents`

```
Content-Type: multipart/form-data

files: <file1>, <file2>, ...
```

**支持格式**：

- 文本：TXT、MD、CSV、JSON、HTML、XML、YAML
- 文档：PDF、DOCX、PPTX、XLSX
- 图片：JPG、PNG（OCR 识别）

### 搜索知识库

**POST** `/api/v1/admin/knowledge-bases/{kb_id}/search`

**请求体**：

```json
{
  "query": "如何重置密码？",
  "top_k": 5
}
```

**响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "results": [
      {
        "content": "重置密码的步骤...",
        "score": 0.89,
        "document": "帮助文档.pdf",
        "page": 12
      }
    ]
  }
}
```

---

## 对话

### 创建对话

**POST** `/api/v1/chat/conversations`

**请求体**：

```json
{
  "agent_id": 1
}
```

### 获取对话列表

**GET** `/api/v1/chat/conversations`

### 获取对话详情

**GET** `/api/v1/chat/conversations/{conversation_id}`

### 发送消息

**POST** `/api/v1/chat/conversations/{conversation_id}/messages`

**请求体**：

```json
{
  "content": "帮我分析这份数据",
  "files": ["file_id_1", "file_id_2"]
}
```

**响应**（SSE 流式）：

```
event: meta
data: {"agent_id": 1, "model": "claude-3-5-sonnet"}

event: thinking
data: {"content": "用户想要分析数据..."}

event: text
data: {"content": "好的，我来帮你分析这份数据..."}

event: tool_use
data: {"name": "code_executor", "arguments": {"code": "..."}}

event: tool_result
data: {"name": "code_executor", "result": "..."}

event: file
data: {"file_id": "xxx", "filename": "analysis.pdf", "url": "..."}

event: done
data: {"message_id": 123}
```

### 获取消息历史

**GET** `/api/v1/chat/conversations/{conversation_id}/messages`

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | integer | 否 | 页码 |
| page_size | integer | 否 | 每页数量 |

---

## 工作流

### 获取工作流列表

**GET** `/api/v1/admin/workflows`

### 创建工作流

**POST** `/api/v1/admin/workflows`

**请求体**：

```json
{
  "name": "数据处理流程",
  "description": "自动处理和分析数据",
  "nodes": [
    {
      "id": "node_1",
      "type": "skill",
      "name": "数据清洗",
      "skill_code": "data_cleaner",
      "position": {"x": 100, "y": 100}
    },
    {
      "id": "node_2",
      "type": "skill",
      "name": "数据分析",
      "skill_code": "data_analyzer",
      "position": {"x": 300, "y": 100}
    }
  ],
  "edges": [
    {
      "source": "node_1",
      "target": "node_2"
    }
  ]
}
```

### 运行工作流

**POST** `/api/v1/admin/workflows/{workflow_id}/run`

**请求体**：

```json
{
  "input": {
    "data_url": "https://example.com/data.csv"
  }
}
```

### 获取运行状态

**GET** `/api/v1/admin/workflows/{workflow_id}/runs/{run_id}`

### 获取运行历史

**GET** `/api/v1/admin/workflows/{workflow_id}/runs`

---

## 审计日志

### 获取审计日志

**GET** `/api/v1/admin/audit-logs`

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | integer | 否 | 页码 |
| page_size | integer | 否 | 每页数量 |
| user_id | integer | 否 | 筛选用户 |
| action | string | 否 | 筛选操作类型 |
| start_date | string | 否 | 开始日期 (ISO 8601) |
| end_date | string | 否 | 结束日期 (ISO 8601) |

**响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": 1,
        "user_id": 1,
        "username": "admin",
        "action": "create_agent",
        "resource_type": "agent",
        "resource_id": 1,
        "details": {"name": "HR 助手"},
        "ip_address": "192.168.1.100",
        "created_at": "2026-01-01T10:00:00Z"
      }
    ],
    "total": 1000
  }
}
```

### 获取调用日志

**GET** `/api/v1/admin/call-logs`

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | integer | 否 | 页码 |
| page_size | integer | 否 | 每页数量 |
| user_id | integer | 否 | 筛选用户 |
| agent_id | integer | 否 | 筛选数字员工 |
| model | string | 否 | 筛选模型 |

---

## 错误码

| 错误码 | HTTP 状态码 | 说明 |
|--------|-------------|------|
| 0 | 200 | 成功 |
| 40001 | 400 | 请求参数错误 |
| 40002 | 400 | 数据格式错误 |
| 40101 | 401 | 未认证 |
| 40102 | 401 | Token 已过期 |
| 40103 | 401 | Token 无效 |
| 40301 | 403 | 权限不足 |
| 40401 | 404 | 资源不存在 |
| 40901 | 409 | 资源已存在 |
| 41301 | 413 | 文件过大 |
| 42901 | 429 | 请求过于频繁 |
| 50001 | 500 | 服务器内部错误 |
| 50002 | 500 | 数据库错误 |
| 50003 | 500 | 外部服务错误 |

### 错误响应示例

```json
{
  "code": 40102,
  "message": "Token 已过期",
  "data": null
}
```

---

## 限流说明

API 采用令牌桶算法进行限流：

| 路径 | 限制 |
|------|------|
| 默认 | 5 次/分钟 |
| /health | 不限流 |
| /docs | 不限流 |

超限响应：

```json
{
  "code": 42901,
  "message": "请求过于频繁，请稍后重试",
  "data": {
    "retry_after": 30
  }
}
```

响应头：

```
Retry-After: 30
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1717200000
```

---

## 相关文档

- [项目能力手册](PROJECT_OVERVIEW.md) — 完整功能模块说明
- [架构说明](ARCHITECTURE.md) — 模块关系与数据流
- [部署指南](DEPLOYMENT.md) — Docker + 生产环境配置
