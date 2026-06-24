# API Reference

This document provides the Agent Mill REST API endpoint reference.

---

## Table of Contents

- [Base Information](#base-information)
- [Authentication](#authentication)
- [API Endpoints](#api-endpoints)
  - [Auth](#auth)
  - [User Management](#user-management)
  - [Model Management](#model-management)
  - [Digital Workforce](#digital-workforce)
  - [Skill Management](#skill-management)
  - [Connector Management](#connector-management)
  - [Knowledge Base](#knowledge-base)
  - [Conversation](#conversation)
  - [Workflow](#workflow)
  - [Audit Logs](#audit-logs)
- [Error Codes](#error-codes)

---

## Base Information

| Item | Value |
|------|-------|
| Base Path | `/api/v1` |
| Content Type | `application/json` |
| Authentication | Bearer Token (JWT) |
| API Version | 1.0 |

### Request Format

All requests require a JWT Token in the Header:

```
Authorization: Bearer <access_token>
```

### Response Format

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

| Field | Type | Description |
|-------|------|-------------|
| code | integer | Status code, 0 indicates success |
| message | string | Status message |
| data | object | Response data |

---

## Authentication

### Local Login

**POST** `/api/v1/auth/login`

**Request Body**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| username | string | Yes | Username |
| password | string | Yes | Password |

**Response**:

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

### Refresh Token

**POST** `/api/v1/auth/refresh`

**Request Header**:

```
Authorization: Bearer <refresh_token>
```

**Response**:

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

### SSO Login

**GET** `/api/v1/auth/sso/authorize`

**Response**: Redirect to SSO provider's authorization page

**GET** `/api/v1/auth/sso/callback`

**Query Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| code | string | Authorization code |
| state | string | CSRF protection state |

---

## User Management

### List Users

**GET** `/api/v1/admin/users`

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| page | integer | No | Page number, default 1 |
| page_size | integer | No | Items per page, default 20 |
| role | string | No | Filter by role |
| keyword | string | No | Search keyword |

**Response**:

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": 1,
        "username": "admin",
        "display_name": "Admin",
        "role": "admin",
        "department": "Engineering",
        "created_at": "2026-01-01T00:00:00Z"
      }
    ],
    "total": 100,
    "page": 1,
    "page_size": 20
  }
}
```

### Create User

**POST** `/api/v1/admin/users`

**Request Body**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| username | string | Yes | Username |
| password | string | Yes | Password |
| display_name | string | No | Display name |
| role | string | Yes | Role: admin/operator/user |
| department_id | integer | No | Department ID |

### Update User

**PUT** `/api/v1/admin/users/{user_id}`

### Delete User

**DELETE** `/api/v1/admin/users/{user_id}`

---

## Model Management

### List Models

**GET** `/api/v1/admin/models`

**Response**:

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

### Create Model Config

**POST** `/api/v1/admin/models`

**Request Body**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| name | string | Yes | Display name |
| provider | string | Yes | Provider: anthropic/openai/deepseek/qwen/glm |
| model_id | string | Yes | Model ID |
| api_key | string | Yes | API Key |
| base_url | string | No | Custom endpoint |
| extra_params_json | string | No | Extra parameters JSON |

### Test Model Connectivity

**POST** `/api/v1/admin/models/{model_id}/test`

**Response**:

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

## Digital Workforce

### List Digital Workforces

**GET** `/api/v1/admin/agents`

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| page | integer | No | Page number |
| page_size | integer | No | Items per page |
| keyword | string | No | Search keyword |

### Create Digital Workforce

**POST** `/api/v1/admin/agents`

**Request Body**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| name | string | Yes | Name |
| code | string | Yes | Unique identifier |
| description | string | No | Description |
| system_prompt | string | No | System prompt |
| model_id | integer | Yes | Primary model ID |
| fallback_model_id | integer | No | Fallback model ID |
| max_turns | integer | No | Max conversation turns |
| effort | string | No | Reasoning effort: low/medium/high/xhigh/max |
| skill_ids | array | No | Associated skill IDs |
| mcp_ids | array | No | Associated connector IDs |
| knowledge_base_ids | array | No | Associated knowledge base IDs |

### Update Digital Workforce

**PUT** `/api/v1/admin/agents/{agent_id}`

### Delete Digital Workforce

**DELETE** `/api/v1/admin/agents/{agent_id}`

**Note**: This operation requires approval.

### Get User-Visible Digital Workforces

**GET** `/api/v1/chat/agents`

**Response**: Returns the list of digital workforces the current user has permission to use.

---

## Skill Management

### List Skills

**GET** `/api/v1/admin/skills`

**Response**:

```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "id": 1,
      "name": "Code Executor",
      "code": "code_executor",
      "type": "callable",
      "description": "Execute Python code",
      "is_active": true
    }
  ]
}
```

### Create Skill

**POST** `/api/v1/admin/skills`

**path-type skill** (ZIP upload):

```
Content-Type: multipart/form-data

file: <zip_file>
name: Skill name
code: skill_code
description: Skill description
```

**callable-type skill**:

```json
{
  "name": "Skill name",
  "code": "skill_code",
  "type": "callable",
  "callable_path": "module.path:function",
  "description": "Skill description"
}
```

### Upload Skill File

**POST** `/api/v1/admin/skills/upload`

```
Content-Type: multipart/form-data

file: <zip_file>
```

**ZIP File Structure**:

```
skill.zip
├── SKILL.md          # Skill documentation (required)
├── main.py           # Entry script (optional)
├── requirements.txt  # Dependencies (optional)
└── resources/        # Resource files (optional)
```

---

## Connector Management

### List Connectors

**GET** `/api/v1/admin/mcp-connectors`

### Create Connector

**POST** `/api/v1/admin/mcp-connectors`

**Request Body**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| name | string | Yes | Name |
| code | string | Yes | Unique identifier |
| transport_type | string | Yes | Transport protocol: stdio/sse/http |
| config_json | string | Yes | Configuration JSON |

**stdio Config Example**:

```json
{
  "command": "python",
  "args": ["-m", "my_mcp_server"],
  "env": {}
}
```

**sse Config Example**:

```json
{
  "url": "http://localhost:8080/sse"
}
```

**http Config Example**:

```json
{
  "url": "http://localhost:8080/mcp"
}
```

### Test Connector

**POST** `/api/v1/admin/mcp-connectors/{connector_id}/test`

### List Tools

**POST** `/api/v1/admin/mcp-connectors/{connector_id}/tools`

---

## Knowledge Base

### List Knowledge Bases

**GET** `/api/v1/admin/knowledge-bases`

### Create Knowledge Base

**POST** `/api/v1/admin/knowledge-bases`

**Request Body**:

```json
{
  "name": "Product Documentation",
  "description": "Product help docs and FAQs"
}
```

### Upload Documents

**POST** `/api/v1/admin/knowledge-bases/{kb_id}/documents`

```
Content-Type: multipart/form-data

files: <file1>, <file2>, ...
```

**Supported Formats**:

- Text: TXT, MD, CSV, JSON, HTML, XML, YAML
- Documents: PDF, DOCX, PPTX, XLSX
- Images: JPG, PNG (OCR recognition)

### Search Knowledge Base

**POST** `/api/v1/admin/knowledge-bases/{kb_id}/search`

**Request Body**:

```json
{
  "query": "How to reset password?",
  "top_k": 5
}
```

**Response**:

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "results": [
      {
        "content": "Steps to reset password...",
        "score": 0.89,
        "document": "help_doc.pdf",
        "page": 12
      }
    ]
  }
}
```

---

## Conversation

### Create Conversation

**POST** `/api/v1/chat/conversations`

**Request Body**:

```json
{
  "agent_id": 1
}
```

### List Conversations

**GET** `/api/v1/chat/conversations`

### Get Conversation Detail

**GET** `/api/v1/chat/conversations/{conversation_id}`

### Send Message

**POST** `/api/v1/chat/conversations/{conversation_id}/messages`

**Request Body**:

```json
{
  "content": "Help me analyze this data",
  "files": ["file_id_1", "file_id_2"]
}
```

**Response** (SSE streaming):

```
event: meta
data: {"agent_id": 1, "model": "claude-3-5-sonnet"}

event: thinking
data: {"content": "The user wants to analyze data..."}

event: text
data: {"content": "Sure, let me help you analyze this data..."}

event: tool_use
data: {"name": "code_executor", "arguments": {"code": "..."}}

event: tool_result
data: {"name": "code_executor", "result": "..."}

event: file
data: {"file_id": "xxx", "filename": "analysis.pdf", "url": "..."}

event: done
data: {"message_id": 123}
```

### Get Message History

**GET** `/api/v1/chat/conversations/{conversation_id}/messages`

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| page | integer | No | Page number |
| page_size | integer | No | Items per page |

---

## Workflow

### List Workflows

**GET** `/api/v1/admin/workflows`

### Create Workflow

**POST** `/api/v1/admin/workflows`

**Request Body**:

```json
{
  "name": "Data Processing Pipeline",
  "description": "Automated data processing and analysis",
  "nodes": [
    {
      "id": "node_1",
      "type": "skill",
      "name": "Data Cleaning",
      "skill_code": "data_cleaner",
      "position": {"x": 100, "y": 100}
    },
    {
      "id": "node_2",
      "type": "skill",
      "name": "Data Analysis",
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

### Run Workflow

**POST** `/api/v1/admin/workflows/{workflow_id}/run`

**Request Body**:

```json
{
  "input": {
    "data_url": "https://example.com/data.csv"
  }
}
```

### Get Run Status

**GET** `/api/v1/admin/workflows/{workflow_id}/runs/{run_id}`

### Get Run History

**GET** `/api/v1/admin/workflows/{workflow_id}/runs`

---

## Audit Logs

### Get Audit Logs

**GET** `/api/v1/admin/audit-logs`

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| page | integer | No | Page number |
| page_size | integer | No | Items per page |
| user_id | integer | No | Filter by user |
| action | string | No | Filter by action type |
| start_date | string | No | Start date (ISO 8601) |
| end_date | string | No | End date (ISO 8601) |

**Response**:

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
        "details": {"name": "HR Assistant"},
        "ip_address": "192.168.1.100",
        "created_at": "2026-01-01T10:00:00Z"
      }
    ],
    "total": 1000
  }
}
```

### Get Call Logs

**GET** `/api/v1/admin/call-logs`

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| page | integer | No | Page number |
| page_size | integer | No | Items per page |
| user_id | integer | No | Filter by user |
| agent_id | integer | No | Filter by digital workforce |
| model | string | No | Filter by model |

---

## Error Codes

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| 0 | 200 | Success |
| 40001 | 400 | Invalid request parameter |
| 40002 | 400 | Invalid data format |
| 40101 | 401 | Unauthenticated |
| 40102 | 401 | Token expired |
| 40103 | 401 | Invalid token |
| 40301 | 403 | Insufficient permissions |
| 40401 | 404 | Resource not found |
| 40901 | 409 | Resource already exists |
| 41301 | 413 | File too large |
| 42901 | 429 | Too many requests |
| 50001 | 500 | Internal server error |
| 50002 | 500 | Database error |
| 50003 | 500 | External service error |

### Error Response Example

```json
{
  "code": 40102,
  "message": "Token expired",
  "data": null
}
```

---

## Rate Limiting

The API uses a token bucket algorithm for rate limiting:

| Path | Limit |
|------|-------|
| Default | 5 req/min |
| /health | No limit |
| /docs | No limit |

Exceeded response:

```json
{
  "code": 42901,
  "message": "Too many requests, please retry later",
  "data": {
    "retry_after": 30
  }
}
```

Response headers:

```
Retry-After: 30
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1717200000
```

---

## Related Documentation

- [Project Overview](PROJECT_OVERVIEW.md) — Complete feature documentation
- [Architecture](ARCHITECTURE.md) — Module structure and data flow
- [Deployment Guide](DEPLOYMENT.md) — Docker and production setup
