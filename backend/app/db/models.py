from __future__ import annotations
from datetime import datetime
from typing import Any
from sqlalchemy import (
    String, Integer, Boolean, ForeignKey, DateTime, Text, JSON, BigInteger, UniqueConstraint, func, Float,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .session import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Role(Base, TimestampMixin):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)  # admin/operator/user
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(String(256))


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    display_name: Mapped[str | None] = mapped_column(String(128))
    email: Mapped[str | None] = mapped_column(String(256))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active/disabled

    role: Mapped[Role] = relationship(lazy="joined")
    department: Mapped["Department | None"] = relationship("Department", foreign_keys=[department_id], lazy="joined")


class Department(Base, TimestampMixin):
    __tablename__ = "departments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), index=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str | None] = mapped_column(String(256))


class Model(Base, TimestampMixin):
    __tablename__ = "models"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    provider: Mapped[str] = mapped_column(String(32))  # anthropic/openai-compatible
    model_id: Mapped[str] = mapped_column(String(128))
    base_url: Mapped[str | None] = mapped_column(String(256))
    api_key_enc: Mapped[str | None] = mapped_column(Text)
    max_tokens: Mapped[int] = mapped_column(Integer, default=8192)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Provider-specific extra params merged into the API call (e.g. {"enable_thinking": false})
    extra_params_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # 单价：每千 tokens 的计价（单位：分），用于成本统计。0 或 NULL 表示不计费
    unit_price_per_1k_tokens: Mapped[int] = mapped_column(Integer, default=0)


class MCPConnector(Base, TimestampMixin):
    __tablename__ = "mcp_connectors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    transport: Mapped[str] = mapped_column(String(16))  # stdio/sse/http
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    icon_url: Mapped[str | None] = mapped_column(String(512), default=None)
    user_summary: Mapped[str | None] = mapped_column(Text, default=None)
    tool_summaries_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    user_summary_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class Skill(Base, TimestampMixin):
    __tablename__ = "skills"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(16))  # atomic / composite
    # atomic: {"path": ".../skill_dir"}; composite: {"yaml": "..."} (parsed at runtime)
    source_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    icon_url: Mapped[str | None] = mapped_column(String(512), default=None)
    user_summary: Mapped[str | None] = mapped_column(Text, default=None)
    user_summary_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class Agent(Base, TimestampMixin):
    __tablename__ = "agents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str | None] = mapped_column(String(256))
    icon_url: Mapped[str | None] = mapped_column(String(512), default=None)
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    default_model_id: Mapped[int | None] = mapped_column(ForeignKey("models.id"))
    fallback_model_id: Mapped[int | None] = mapped_column(ForeignKey("models.id"))
    upload_policy_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    max_turns: Mapped[int] = mapped_column(Integer, default=15, server_default="15")
    effort: Mapped[str] = mapped_column(String(16), default="medium", server_default="medium")
    # File-parsing length cap fed into the model:
    #   None → use settings.PARSED_MARKDOWN_HARD_LIMIT
    #   0    → no cap (inject the full parsed markdown)
    #   >0   → cap to this many characters (head 60% + tail 40% with omission marker)
    parsed_content_limit: Mapped[int | None] = mapped_column(Integer)
    kb_id: Mapped[int | None] = mapped_column(ForeignKey("kb_knowledge_bases.id", ondelete="SET NULL"), comment="关联知识库")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class AgentSkill(Base):
    __tablename__ = "agent_skills"
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True)


class AgentMCP(Base):
    __tablename__ = "agent_mcps"
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True)
    mcp_id: Mapped[int] = mapped_column(ForeignKey("mcp_connectors.id", ondelete="CASCADE"), primary_key=True)


class RoleAgentGrant(Base):
    __tablename__ = "role_agent_grants"
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True)


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    title: Mapped[str] = mapped_column(String(256), default="新对话")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True, comment="对话历史摘要（压缩后）")


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))  # user/assistant/tool/system
    content_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    tool_calls_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class MessageFeedback(Base, TimestampMixin):
    """用户对助手消息的反馈（点赞/点踩）"""
    __tablename__ = "message_feedback"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id", ondelete="SET NULL"), index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    rating: Mapped[str] = mapped_column(String(16), comment="反馈类型：like=点赞 / dislike=点踩")
    reason: Mapped[str | None] = mapped_column(String(500), comment="点踩原因（可选）")
    # 反馈分析字段
    analyzed: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否已分析")
    analysis_result: Mapped[dict[str, Any] | None] = mapped_column(JSON, comment="分析结果")


class UploadedFile(Base):
    __tablename__ = "uploaded_files"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(256))
    path: Mapped[str] = mapped_column(String(512))
    size: Mapped[int] = mapped_column(BigInteger)
    mime: Mapped[str] = mapped_column(String(128))
    # Parsed text/markdown for LLM consumption
    parse_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/parsing/done/failed
    parse_engine: Mapped[str | None] = mapped_column(String(32))  # text/mineru-cloud/mineru-local/local-lib
    parsed_markdown: Mapped[str | None] = mapped_column(Text)
    parsed_chars: Mapped[int] = mapped_column(Integer, default=0)
    parse_error: Mapped[str | None] = mapped_column(Text)
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CallLog(Base):
    __tablename__ = "call_logs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id", ondelete="SET NULL"))
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id", ondelete="SET NULL"))
    model_id: Mapped[int | None] = mapped_column(ForeignKey("models.id", ondelete="SET NULL"))
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="ok")
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class AuditLog(Base, TimestampMixin):
    """审计日志 — 记录所有敏感操作，满足合规要求。"""
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True, comment="操作类型：login/logout/create/update/delete/export等")
    resource_type: Mapped[str | None] = mapped_column(String(32), comment="资源类型：user/agent/conversation/model等")
    resource_id: Mapped[str | None] = mapped_column(String(64), comment="资源 ID")
    detail_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, comment="操作详情")
    ip_address: Mapped[str | None] = mapped_column(String(45), comment="客户端 IP（支持 IPv6）")
    user_agent: Mapped[str | None] = mapped_column(String(512), comment="User-Agent")
    status: Mapped[str] = mapped_column(String(16), default="success", comment="操作状态：success/failed/denied")
    error_message: Mapped[str | None] = mapped_column(Text, comment="错误信息（失败时）")


# ====================== Quota ======================

class UserQuota(Base, TimestampMixin):
    """用户月度额度管理。每个用户最多一行，user_id 唯一。

    monthly_limit     — 本月 tokens 总量上限（tokens_in + tokens_out），0 表示不限
    alert_threshold   — 占用率百分比（0-100），达到时发送告警通知，默认 80
    last_alert_at     — 上次告警时间（按月去重，每月最多告警一次）
    """
    __tablename__ = "user_quotas"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    monthly_limit: Mapped[int] = mapped_column(Integer, default=0)       # 0 = unlimited
    alert_threshold: Mapped[int] = mapped_column(Integer, default=80)      # 0-100
    last_alert_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class DownloadToken(Base):
    """One-time / time-limited URL token for serving files (skill outputs, uploads).

    Path is stored absolute and validated against allowed roots on each fetch to
    prevent path-traversal. Owner check ensures cross-user access is blocked.
    """
    __tablename__ = "download_tokens"
    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    file_path: Mapped[str] = mapped_column(String(1024))
    file_name: Mapped[str] = mapped_column(String(256))
    mime: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    size: Mapped[int] = mapped_column(BigInteger, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    download_count: Mapped[int] = mapped_column(Integer, default=0)
    max_downloads: Mapped[int] = mapped_column(Integer, default=0)  # 0 = unlimited within expiry
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ====================== Solution Packs ======================

class SolutionPack(Base, TimestampMixin):
    """Declarative business workflow packaged as a YAML DAG of nodes.

    Each Pack is registered against an agent in `agent_packs` and shows up to
    the LLM as a single tool `run_pack__<code>(inputs)`. Calling that tool
    spins up a `PackRun` and streams progress via SSE pack_progress/pack_done.
    """
    __tablename__ = "solution_packs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # snake_case, == pack_id
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    yaml_text: Mapped[str] = mapped_column(Text)  # source-of-truth YAML
    spec_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # parsed cache
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class AgentPack(Base):
    __tablename__ = "agent_packs"
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True)
    pack_id: Mapped[int] = mapped_column(ForeignKey("solution_packs.id", ondelete="CASCADE"), primary_key=True)


class PackRun(Base):
    """Execution snapshot of a Pack. Persisted so human_approval can pause+resume."""
    __tablename__ = "pack_runs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # uuid hex
    pack_id: Mapped[int] = mapped_column(ForeignKey("solution_packs.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id", ondelete="SET NULL"))
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="running", index=True)
    # ^ running / success / failed / aborted / waiting_approval
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    context_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    outputs: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    trace: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PackApproval(Base):
    """One row per human_approval node hit. Inbox + decision audit."""
    __tablename__ = "pack_approvals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    pack_id: Mapped[int] = mapped_column(ForeignKey("solution_packs.id", ondelete="CASCADE"))
    node_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)  # pending/approved/rejected/timeout
    title: Mapped[str] = mapped_column(String(256))
    message: Mapped[str | None] = mapped_column(Text)
    detail_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)  # context highlights for the approver
    assigned_role: Mapped[str | None] = mapped_column(String(32))
    assigned_user_ids: Mapped[list[int] | None] = mapped_column(JSON)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decision_reason: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------- Scheduled Tasks ----------
class Task(Base, TimestampMixin):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    prompt_text: Mapped[str] = mapped_column(Text, default="")

    schedule_type: Mapped[str] = mapped_column(String(16), default="manual")  # manual / once / cron
    schedule_value: Mapped[str | None] = mapped_column(String(128))           # cron expr or ISO datetime
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai")

    max_runtime_seconds: Mapped[int] = mapped_column(Integer, default=1800)
    concurrency_policy: Mapped[str] = mapped_column(String(16), default="skip")  # skip / queue
    notify_channels_json: Mapped[list[str]] = mapped_column(JSON, default=list)  # ["inapp","email"]
    notify_email_to: Mapped[str | None] = mapped_column(String(256))
    notify_on: Mapped[str] = mapped_column(String(16), default="always")        # always / success / failure
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    last_run_id: Mapped[int | None] = mapped_column(BigInteger)
    last_run_status: Mapped[str | None] = mapped_column(String(16))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TaskRun(Base):
    __tablename__ = "task_runs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    run_no: Mapped[int] = mapped_column(Integer, default=1)
    triggered_by: Mapped[str] = mapped_column(String(16), default="manual")     # manual / cron
    triggered_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    # pending / running / succeeded / failed / cancelled / timeout / skipped

    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id", ondelete="SET NULL"))

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)

    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)

    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notify_status_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class Notification(Base):
    """Generic in-app notification record."""
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(32), default="task_run")  # task_run / system
    title: Mapped[str] = mapped_column(String(256))
    body: Mapped[str | None] = mapped_column(Text)
    link_url: Mapped[str | None] = mapped_column(String(512))
    detail_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)



class Favorite(Base):
    """User-curated Q&A bookmark stored in the personal "Space".

    Holds full text snapshots of the question + answer so deleting the source
    conversation/message still leaves the favorite readable. The FK columns
    are soft references (SET NULL) used for the optional "jump back to
    original conversation" button.
    """
    __tablename__ = "favorites"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id", ondelete="SET NULL"))
    message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"))

    question_text: Mapped[str] = mapped_column(Text)
    answer_text: Mapped[str] = mapped_column(Text)
    # Snapshot of assistant-generated file cards (download_url + output_path so
    # the FileCard component can keep refreshing expired tokens forever).
    files_json: Mapped[list[Any] | None] = mapped_column(JSON)

    # snapshots — survive even after the agent/model is deleted
    agent_id: Mapped[int | None] = mapped_column(Integer)
    agent_name: Mapped[str | None] = mapped_column(String(128))
    model_code: Mapped[str | None] = mapped_column(String(64))

    note: Mapped[str | None] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        UniqueConstraint("user_id", "message_id", name="uq_favorites_user_message"),
    )


class AgentMemory(Base, TimestampMixin):
    """Agent 持久记忆 — 记住用户偏好、历史决策、项目上下文。"""
    __tablename__ = "agent_memories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    memory_type: Mapped[str] = mapped_column(String(32), nullable=False)  # preference/fact/decision/context
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id", ondelete="SET NULL"))
    importance: Mapped[float] = mapped_column(Float, default=0.5)  # 0-1
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class TaskTemplate(Base, TimestampMixin):
    """任务模板 — 复用任务配置，快速创建同类任务。"""
    __tablename__ = "task_templates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"))
    prompt_template: Mapped[str] = mapped_column(Text, nullable=False)  # 支持 {{变量}} 替换
    variables_json: Mapped[list] = mapped_column(JSON, default=list)  # [{name, label, type, default}]
    schedule_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)  # 默认调度配置
    notify_config_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)  # 默认通知配置
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class AgentMessage(Base, TimestampMixin):
    """Agent 间消息 — 支持多 Agent 协作和委托。"""
    __tablename__ = "agent_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    from_agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    to_agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id", ondelete="SET NULL"))
    message_type: Mapped[str] = mapped_column(String(32), comment="请求类型：delegate=委托 / query=查询 / notify=通知")
    content: Mapped[str] = mapped_column(Text, comment="消息内容")
    context_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, comment="传递的上下文数据")
    status: Mapped[str] = mapped_column(String(16), default="pending", comment="状态：pending/processing/completed/failed")
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, comment="执行结果")
    priority: Mapped[int] = mapped_column(Integer, default=0, comment="优先级（0=普通，1=高优先级）")
    reply_to_id: Mapped[int | None] = mapped_column(ForeignKey("agent_messages.id"), comment="回复的消息 ID")


class WebhookConfig(Base, TimestampMixin):
    """Webhook 配置 — 外部系统通过 Webhook 触发数字员工。"""
    __tablename__ = "webhook_configs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    secret: Mapped[str] = mapped_column(String(128), nullable=False)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str | None] = mapped_column(Text)


class SystemConfig(Base, TimestampMixin):
    """系统配置 — 存储全局配置项（JSON 格式）。"""
    __tablename__ = "system_configs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String(128), unique=True, index=True, comment="配置键")
    value: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, comment="配置值（JSON）")
    description: Mapped[str | None] = mapped_column(String(256), comment="配置说明")


# ====================== Alerts ======================

class AlertRule(Base, TimestampMixin):
    """告警规则 — 定义触发条件和通知配置。"""
    __tablename__ = "alert_rules"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), comment="规则名称")
    description: Mapped[str | None] = mapped_column(Text, comment="规则描述")
    metric: Mapped[str] = mapped_column(String(32), comment="指标类型：token_consumption/error_rate/latency_p50/latency_p99/call_count/quota_usage")
    condition: Mapped[str] = mapped_column(String(8), comment="条件：gte/gt/lte/lt")
    threshold: Mapped[float] = mapped_column(Float, comment="阈值")
    window_minutes: Mapped[int] = mapped_column(Integer, default=5, comment="评估窗口（分钟）")
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=30, comment="冷却期（分钟）")
    notification_channels: Mapped[dict[str, Any] | None] = mapped_column(JSON, default={"in_app": True}, comment="通知渠道")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), comment="创建者")


class AlertEvent(Base, TimestampMixin):
    """告警事件 — 记录规则触发历史。"""
    __tablename__ = "alert_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("alert_rules.id", ondelete="CASCADE"), index=True, comment="关联规则")
    triggered_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="触发时间")
    metric_value: Mapped[float] = mapped_column(Float, comment="触发时的指标值")
    metric_detail: Mapped[dict[str, Any] | None] = mapped_column(JSON, comment="触发详情")
    status: Mapped[str] = mapped_column(String(16), default="firing", comment="状态：firing/resolved")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, comment="解决时间")


# ====================== Operation Approval ======================

class OperationApproval(Base, TimestampMixin):
    """通用操作审批 — 高危操作需审批。"""
    __tablename__ = "operation_approvals"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    operation_type: Mapped[str] = mapped_column(String(64), index=True, comment="操作类型：delete_agent/delete_user/update_model等")
    target_id: Mapped[int | None] = mapped_column(Integer, comment="目标资源 ID")
    target_name: Mapped[str | None] = mapped_column(String(256), comment="目标资源名称")
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"), comment="请求人 ID")
    reason: Mapped[str | None] = mapped_column(Text, comment="操作原因")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True, comment="状态：pending/approved/rejected")
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    decision_reason: Mapped[str | None] = mapped_column(Text, comment="审批意见")
    detail_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, comment="操作详情")


# ====================== Agent Template Marketplace ======================

class AgentTemplate(Base, TimestampMixin):
    """Agent 模板 — 预置多 Agent 协作方案包。"""
    __tablename__ = "agent_templates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(32), comment="hr/sales/marketing/finance/admin/it/support/general")
    icon: Mapped[str | None] = mapped_column(String(64), comment="emoji 图标")
    yaml_text: Mapped[str] = mapped_column(Text, comment="方案包 YAML 定义")
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    agent_count: Mapped[int] = mapped_column(Integer, default=0, comment="包含的 Agent 数")

class KnowledgeBase(Base, TimestampMixin):
    """知识库 — 文档集合，供数字员工检索问答。"""
    __tablename__ = "kb_knowledge_bases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(256), comment="知识库名称")
    description: Mapped[str | None] = mapped_column(Text, comment="描述")
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), comment="创建者")
    status: Mapped[str] = mapped_column(String(16), default="active")
    document_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)


class KBDocument(Base, TimestampMixin):
    """知识库文档 — 已解析的文件。"""
    __tablename__ = "kb_documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kb_id: Mapped[int] = mapped_column(ForeignKey("kb_knowledge_bases.id", ondelete="CASCADE"), index=True)
    file_id: Mapped[int | None] = mapped_column(ForeignKey("uploaded_files.id", ondelete="SET NULL"))
    title: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)


class KBChunk(Base, TimestampMixin):
    """知识库分块 — 含向量嵌入。"""
    __tablename__ = "kb_chunks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("kb_documents.id", ondelete="CASCADE"), index=True)
    kb_id: Mapped[int] = mapped_column(ForeignKey("kb_knowledge_bases.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Mapped[str | None] = mapped_column(Text, comment="向量嵌入（JSON 数组）")


# ====================== Workflow ======================

class WorkflowDefinition(Base, TimestampMixin):
    """可视化工作流 — 拖拽编排的流程定义。"""
    __tablename__ = "workflow_definitions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), comment="工作流名称")
    description: Mapped[str | None] = mapped_column(Text, comment="描述")
    category: Mapped[str | None] = mapped_column(String(32), comment="分类")
    definition_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, comment="可视化画布数据 {nodes[], edges[]}")
    compiled_yaml: Mapped[str | None] = mapped_column(Text, comment="编译后的方案包 YAML")
    status: Mapped[str] = mapped_column(String(16), default="draft", comment="draft/published")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    run_count: Mapped[int] = mapped_column(Integer, default=0)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class WorkflowRun(Base):
    """工作流运行记录 — 跟踪每次执行的状态和结果。"""
    __tablename__ = "workflow_runs"
    __table_args__ = {"comment": "工作流运行记录"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="工作流ID")
    status: Mapped[str] = mapped_column(String(20), default="running", comment="状态: running/success/failed")
    input_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True, comment="输入参数")
    output_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True, comment="输出结果")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误信息")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="开始时间")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="完成时间")
