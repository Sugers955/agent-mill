from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Auth ----------
class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshIn(BaseModel):
    refresh_token: str


# ---------- User / Role ----------
class RoleOut(ORM):
    id: int
    code: str
    name: str
    description: str | None = None


class RoleIn(BaseModel):
    code: str = Field(min_length=2, max_length=32)
    name: str = Field(min_length=1, max_length=64)
    description: str | None = None


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


# ---------- Department ----------
class DepartmentIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    parent_id: int | None = None
    sort: int = 0
    description: str | None = None


class DepartmentUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    parent_id: int | None = None
    sort: int | None = None
    description: str | None = None


class DepartmentOut(ORM):
    id: int
    code: str
    name: str
    parent_id: int | None = None
    sort: int = 0
    description: str | None = None


class DepartmentNode(DepartmentOut):
    children: list["DepartmentNode"] = Field(default_factory=list)
    user_count: int = 0


class DepartmentBrief(BaseModel):
    id: int
    name: str


class UserOut(ORM):
    id: int
    username: str
    display_name: str | None = None
    role: RoleOut
    department_id: int | None = None
    department: DepartmentBrief | None = None
    status: str
    created_at: datetime


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6)
    display_name: str | None = None
    role_id: int
    department_id: int | None = None


class UserUpdate(BaseModel):
    display_name: str | None = None
    role_id: int | None = None
    department_id: int | None = None
    status: Literal["active", "disabled"] | None = None
    password: str | None = Field(default=None, min_length=6)


class UserPage(BaseModel):
    items: list[UserOut]
    total: int


# ---------- Model ----------
class ModelIn(BaseModel):
    code: str
    provider: Literal["anthropic", "openai-compatible", "deepseek", "qwen", "glm", "openai"]
    model_id: str
    base_url: str | None = None
    api_key: str | None = None
    max_tokens: int = 8192
    enabled: bool = True
    extra_params: dict[str, Any] = Field(default_factory=dict)


class ModelOut(ORM):
    id: int
    code: str
    provider: str
    model_id: str
    base_url: str | None = None
    max_tokens: int
    enabled: bool
    has_api_key: bool
    extra_params: dict[str, Any] = Field(default_factory=dict)


# ---------- MCP ----------
class MCPIn(BaseModel):
    name: str
    transport: Literal["stdio", "sse", "http"]
    config_json: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class MCPOut(ORM):
    id: int
    name: str
    transport: str
    config_json: dict[str, Any]
    enabled: bool


# ---------- Skill ----------
class SkillIn(BaseModel):
    code: str
    name: str
    description: str
    type: Literal["atomic", "composite"]
    source_json: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class SkillOut(ORM):
    id: int
    code: str
    name: str
    description: str
    type: str
    source_json: dict[str, Any]
    enabled: bool
    version: int


# ---------- Agent ----------
class AgentIn(BaseModel):
    code: str
    name: str
    description: str | None = None
    icon: str | None = None
    system_prompt: str = ""
    default_model_id: int | None = None
    fallback_model_id: int | None = None
    upload_policy_json: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    is_default: bool = False
    skill_ids: list[int] = Field(default_factory=list)
    mcp_ids: list[int] = Field(default_factory=list)
    role_ids: list[int] = Field(default_factory=list)


class AgentOut(ORM):
    id: int
    code: str
    name: str
    description: str | None
    icon: str | None
    system_prompt: str
    default_model_id: int | None
    fallback_model_id: int | None
    upload_policy_json: dict[str, Any]
    enabled: bool
    is_default: bool = False
    skill_ids: list[int] = []
    mcp_ids: list[int] = []
    role_ids: list[int] = []


# ---------- Conversation / Message ----------
class ConversationOut(ORM):
    id: int
    agent_id: int
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationCreate(BaseModel):
    agent_id: int | None = None
    title: str | None = None


class ConversationUpdate(BaseModel):
    title: str


class MessageOut(ORM):
    id: int
    role: str
    content_json: dict[str, Any]
    tool_calls_json: dict[str, Any] | None = None
    created_at: datetime


class ChatIn(BaseModel):
    content: str
    file_ids: list[int] = Field(default_factory=list)


# ---------- Logs ----------
class CallLogOut(ORM):
    id: int
    user_id: int | None
    user_name: str | None = None
    agent_id: int | None
    agent_name: str | None = None
    conversation_id: int | None
    model_id: int | None
    model_name: str | None = None
    model_provider: str | None = None
    tokens_in: int
    tokens_out: int
    latency_ms: int
    status: str
    error: str | None
    created_at: datetime


class AuditLogOut(ORM):
    id: int
    user_id: int | None
    user_name: str | None = None
    action: str
    target_type: str | None
    target_id: str | None
    detail_json: dict[str, Any] | None
    created_at: datetime


class CallLogPage(BaseModel):
    items: list[CallLogOut]
    total: int


class AuditLogPage(BaseModel):
    items: list[AuditLogOut]
    total: int
