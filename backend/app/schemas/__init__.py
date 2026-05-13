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


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=128)


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
    email: str | None = None
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
    user_summary: str | None = None
    tool_summaries_json: dict[str, Any] | None = None
    user_summary_updated_at: datetime | None = None


# ---------- Skill ----------
class SkillIn(BaseModel):
    code: str
    name: str
    description: str
    type: Literal["atomic", "composite"]
    source_json: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    # Optional: admin-edited usage summary. When provided we persist it
    # verbatim and skip the auto-summarize task so it isn't overwritten.
    user_summary: str | None = None


class SkillOut(ORM):
    id: int
    code: str
    name: str
    description: str
    type: str
    source_json: dict[str, Any]
    enabled: bool
    version: int
    user_summary: str | None = None
    user_summary_updated_at: datetime | None = None


# ---------- Agent ----------
EffortLevel = Literal["low", "medium", "high", "xhigh", "max"]


class AgentIn(BaseModel):
    code: str
    name: str
    description: str | None = None
    icon: str | None = None
    system_prompt: str = ""
    default_model_id: int | None = None
    fallback_model_id: int | None = None
    upload_policy_json: dict[str, Any] = Field(default_factory=dict)
    max_turns: int = Field(default=15, ge=1, le=100)
    effort: EffortLevel = "medium"
    parsed_content_limit: int | None = Field(default=None, ge=0, le=2_000_000)
    enabled: bool = True
    is_default: bool = False
    skill_ids: list[int] = Field(default_factory=list)
    mcp_ids: list[int] = Field(default_factory=list)
    pack_ids: list[int] = Field(default_factory=list)
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
    max_turns: int = 15
    effort: EffortLevel = "medium"
    parsed_content_limit: int | None = None
    enabled: bool
    is_default: bool = False
    skill_ids: list[int] = []
    mcp_ids: list[int] = []
    pack_ids: list[int] = []
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


# ---------- Solution Pack ----------
class SolutionPackIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=32, default="1.0.0")
    description: str | None = None
    yaml_text: str = Field(min_length=1)
    enabled: bool = True


class SolutionPackOut(ORM):
    id: int
    code: str
    name: str
    version: str
    description: str | None = None
    yaml_text: str
    spec_json: dict[str, Any] = Field(default_factory=dict)
    enabled: bool
    created_at: datetime
    updated_at: datetime


class PackApprovalOut(ORM):
    id: int
    run_id: str
    pack_id: int
    node_id: str
    status: str
    title: str
    message: str | None = None
    detail_json: dict[str, Any] | None = None
    assigned_role: str | None = None
    assigned_user_ids: list[int] | None = None
    decided_by: int | None = None
    decision_reason: str | None = None
    expires_at: datetime | None = None
    created_at: datetime
    decided_at: datetime | None = None


class PackApprovalDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    reason: str | None = None


# ---------- Task / TaskRun / Notification ----------
ScheduleType = Literal["manual", "once", "cron"]
ConcurrencyPolicy = Literal["skip", "queue"]
NotifyChannel = Literal["inapp", "email"]
NotifyOn = Literal["always", "success", "failure"]
TaskRunStatus = Literal["pending", "running", "succeeded", "failed", "cancelled", "timeout", "skipped"]


class TaskIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    agent_id: int
    prompt_text: str = ""
    schedule_type: ScheduleType = "manual"
    schedule_value: str | None = None
    timezone: str = "Asia/Shanghai"
    max_runtime_seconds: int = Field(default=1800, ge=10, le=24 * 3600)
    concurrency_policy: ConcurrencyPolicy = "skip"
    notify_channels: list[NotifyChannel] = Field(default_factory=lambda: ["inapp"])
    notify_email_to: str | None = None
    notify_on: NotifyOn = "always"
    enabled: bool = True


class TaskOut(ORM):
    id: int
    owner_user_id: int
    agent_id: int
    agent_name: str | None = None
    name: str
    description: str | None
    prompt_text: str
    schedule_type: str
    schedule_value: str | None
    timezone: str
    max_runtime_seconds: int
    concurrency_policy: str
    notify_channels: list[str] = Field(default_factory=list)
    notify_email_to: str | None = None
    notify_on: str
    enabled: bool
    last_run_id: int | None = None
    last_run_status: str | None = None
    last_run_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TaskRunOut(ORM):
    id: int
    task_id: int
    run_no: int
    triggered_by: str
    triggered_user_id: int | None
    status: str
    conversation_id: int | None
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int
    tokens_in: int
    tokens_out: int
    summary: str | None
    error_message: str | None
    notified_at: datetime | None
    created_at: datetime


class TaskRunPage(BaseModel):
    items: list[TaskRunOut]
    total: int


class NotificationOut(ORM):
    id: int
    type: str
    title: str
    body: str | None
    link_url: str | None
    detail_json: dict[str, Any] | None
    read_at: datetime | None
    created_at: datetime


class NotificationPage(BaseModel):
    items: list[NotificationOut]
    total: int
    unread: int


class EmailUpdateIn(BaseModel):
    email: str | None = Field(default=None, max_length=256)


# ---------- Favorites (Space) ----------
class FavoriteCreate(BaseModel):
    message_id: int
    note: str | None = Field(default=None, max_length=500)


class FavoriteUpdate(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class FavoriteOut(ORM):
    id: int
    conversation_id: int | None = None
    message_id: int | None = None
    question_text: str
    answer_text: str
    files: list[dict[str, Any]] = Field(default_factory=list)
    agent_id: int | None = None
    agent_name: str | None = None
    model_code: str | None = None
    note: str | None = None
    created_at: datetime


class FavoritePage(BaseModel):
    items: list[FavoriteOut]
    total: int
