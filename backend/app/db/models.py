from __future__ import annotations
from datetime import datetime
from typing import Any
from sqlalchemy import (
    String, Integer, Boolean, ForeignKey, DateTime, Text, JSON, BigInteger, UniqueConstraint, func,
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


class MCPConnector(Base, TimestampMixin):
    __tablename__ = "mcp_connectors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    transport: Mapped[str] = mapped_column(String(16))  # stdio/sse/http
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


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


class Agent(Base, TimestampMixin):
    __tablename__ = "agents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str | None] = mapped_column(String(256))
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    default_model_id: Mapped[int | None] = mapped_column(ForeignKey("models.id"))
    fallback_model_id: Mapped[int | None] = mapped_column(ForeignKey("models.id"))
    upload_policy_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    max_turns: Mapped[int] = mapped_column(Integer, default=5, server_default="5")
    effort: Mapped[str] = mapped_column(String(16), default="medium", server_default="medium")
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


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[str | None] = mapped_column(String(64))
    detail_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


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
