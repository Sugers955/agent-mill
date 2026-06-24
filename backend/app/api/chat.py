from __future__ import annotations
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from ..db.session import get_db, SessionLocal
from ..db.models import (
    Agent, AgentSkill, AgentMCP, AgentPack, RoleAgentGrant, Skill, MCPConnector, Model, SolutionPack,
    Conversation, Message, User, UploadedFile, CallLog,
)
from ..deps import current_user
from ..schemas import (
    AgentOut, ConversationOut, ConversationCreate, ConversationUpdate,
    MessageOut, ChatIn,
)
from ..runtime.agent_runner import AgentRunner, AgentContext
from ..services.agent_context_service import build_agent_context
from ..services.export_service import ExportService

router = APIRouter(prefix="/api", tags=["chat"])

logger = logging.getLogger(__name__)

# Large fields that bloat tool_result history — replace with a byte-count summary.
# word_base64 / content_b64 are base64-encoded binaries; markdown_content /
# content are full document text. Neither is needed for conversation replay;
# the model only needs to know the tool succeeded and which files were produced.
_LARGE_RESULT_FIELDS = frozenset({
    "word_base64", "content_b64", "markdown_content", "markdown",
    "content", "audit",
})
_RESULT_CONTENT_CHAR_LIMIT = 4000  # keep at most this many chars of tool_result content


def _slim_trace_event(event: dict) -> dict:
    """Strip large inline fields from tool_result trace entries before
    persisting to the DB. The trimmed version is still sufficient for the
    model to understand what tools were called and what they produced."""
    if not isinstance(event, dict) or event.get("type") != "tool_result":
        return event
    data = event.get("data")
    if not isinstance(data, dict):
        return event
    content_str = data.get("content")
    if not isinstance(content_str, str):
        return event
    try:
        parsed = json.loads(content_str)
    except Exception:
        # Plain text result — just cap length
        if len(content_str) > _RESULT_CONTENT_CHAR_LIMIT:
            slimmed = content_str[:_RESULT_CONTENT_CHAR_LIMIT] + f"…[已截断, 共 {len(content_str)} 字符]"
            return {**event, "data": {**data, "content": slimmed}}
        return event
    if not isinstance(parsed, dict):
        return event
    changed = False
    for key in list(parsed.keys()):
        if key in _LARGE_RESULT_FIELDS:
            val = parsed[key]
            size = len(val) if isinstance(val, str) else len(json.dumps(val, ensure_ascii=False))
            parsed[key] = f"[已省略, {size} 字符]"
            changed = True
    if not changed:
        # Even if no known large fields, cap total length
        slim_str = json.dumps(parsed, ensure_ascii=False)
        if len(slim_str) <= _RESULT_CONTENT_CHAR_LIMIT:
            return event
        return {**event, "data": {**data, "content": slim_str[:_RESULT_CONTENT_CHAR_LIMIT] + "…[截断]"}}
    return {**event, "data": {**data, "content": json.dumps(parsed, ensure_ascii=False)}}


@router.get("/agents/default", response_model=AgentOut | None)
async def my_default_agent(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Resolve the default agent visible to the current user.

    Priority: explicit is_default flag → first enabled agent visible to the user.
    Returns null if none.
    """
    agent = await _resolve_default_agent(db, user)
    if not agent:
        return None
    skill_ids = [r[0] for r in (await db.execute(select(AgentSkill.skill_id).where(AgentSkill.agent_id == agent.id))).all()]
    mcp_ids = [r[0] for r in (await db.execute(select(AgentMCP.mcp_id).where(AgentMCP.agent_id == agent.id))).all()]
    out = AgentOut.model_validate(agent, from_attributes=True)
    out.skill_ids = skill_ids; out.mcp_ids = mcp_ids
    return out


async def _resolve_default_agent(db: AsyncSession, user: User) -> Agent | None:
    # explicit default
    a = (await db.execute(
        select(Agent).where(Agent.is_default.is_(True), Agent.enabled.is_(True))
    )).scalar_one_or_none()
    if a and await _user_can_access(user, a, db):
        return a
    # fallback: first enabled visible agent
    if user.role.code in ("admin", "operator"):
        return (await db.execute(
            select(Agent).where(Agent.enabled.is_(True)).order_by(Agent.id).limit(1)
        )).scalar_one_or_none()
    sub = select(RoleAgentGrant.agent_id).where(RoleAgentGrant.role_id == user.role_id)
    return (await db.execute(
        select(Agent).where(Agent.id.in_(sub), Agent.enabled.is_(True)).order_by(Agent.id).limit(1)
    )).scalar_one_or_none()


async def _user_can_access(user: User, agent: Agent, db: AsyncSession) -> bool:
    """Check if user can access the given agent. Admins/operators see all; plain users need a grant."""
    if user.role.code in ("admin", "operator"):
        return True
    granted = (await db.execute(
        select(RoleAgentGrant.agent_id).where(
            RoleAgentGrant.role_id == user.role_id,
            RoleAgentGrant.agent_id == agent.id,
        )
    )).scalar_one_or_none()
    return granted is not None


async def _ensure_agent_visible(db: AsyncSession, user: User, agent_id: int) -> Agent:
    a = (await db.execute(select(Agent).where(Agent.id == agent_id))).scalar_one_or_none()
    if not a or not a.enabled:
        raise HTTPException(404, "agent 不存在")
    if user.role.code in ("admin", "operator"):
        return a
    granted = (await db.execute(
        select(RoleAgentGrant.agent_id).where(
            RoleAgentGrant.role_id == user.role_id,
            RoleAgentGrant.agent_id == agent_id,
        )
    )).scalar_one_or_none()
    if granted is None:
        raise HTTPException(403, "无权访问该智能体")
    return a


@router.get("/agents/{agent_id}/capabilities")
async def agent_capabilities(
    agent_id: int,
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    """Return the model + skills + mcps wired into an agent (without live MCP tools).

    Visible to any user who can access this agent.
    """
    a = await _ensure_agent_visible(db, user, agent_id)

    def _model_brief(m: Model | None) -> dict | None:
        if not m:
            return None
        return {"id": m.id, "code": m.code, "model_id": m.model_id, "provider": m.provider}

    model = (await db.execute(select(Model).where(Model.id == a.default_model_id))).scalar_one_or_none() if a.default_model_id else None
    fb = (await db.execute(select(Model).where(Model.id == a.fallback_model_id))).scalar_one_or_none() if a.fallback_model_id else None

    skill_ids = [r[0] for r in (await db.execute(select(AgentSkill.skill_id).where(AgentSkill.agent_id == a.id))).all()]
    skills = list((await db.execute(
        select(Skill).where(Skill.id.in_(skill_ids))
    )).scalars().all()) if skill_ids else []

    mcp_ids = [r[0] for r in (await db.execute(select(AgentMCP.mcp_id).where(AgentMCP.agent_id == a.id))).all()]
    mcps = list((await db.execute(
        select(MCPConnector).where(MCPConnector.id.in_(mcp_ids))
    )).scalars().all()) if mcp_ids else []

    pack_ids = [r[0] for r in (await db.execute(select(AgentPack.pack_id).where(AgentPack.agent_id == a.id))).all()]
    packs = list((await db.execute(
        select(SolutionPack).where(SolutionPack.id.in_(pack_ids))
    )).scalars().all()) if pack_ids else []

    return {
        "agent": {
            "id": a.id, "code": a.code, "name": a.name,
            "description": a.description,
            "icon": a.icon,
        },
        "model": _model_brief(model),
        "fallback_model": _model_brief(fb),
        "skills": [
            {"id": s.id, "code": s.code, "name": s.name, "type": s.type,
             "description": s.description,
             "user_summary": s.user_summary,
             "enabled": s.enabled}
            for s in skills
        ],
        "mcps": [
            {"id": m.id, "name": m.name, "transport": m.transport,
             "user_summary": m.user_summary,
             "tool_summaries": (m.tool_summaries_json or {}).get("items") or [],
             "enabled": m.enabled}
            for m in mcps
        ],
        "packs": [
            {"id": p.id, "code": p.code, "name": p.name, "version": p.version,
             "description": p.description, "enabled": p.enabled}
            for p in packs
        ],
    }


@router.get("/agents/{agent_id}/mcps/{mid}/tools")
async def agent_mcp_tools(
    agent_id: int, mid: int,
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    """Live-fetch tool list for one MCP server bound to an agent the user can access."""
    await _ensure_agent_visible(db, user, agent_id)
    bound = (await db.execute(
        select(AgentMCP).where(AgentMCP.agent_id == agent_id, AgentMCP.mcp_id == mid)
    )).scalar_one_or_none()
    if bound is None:
        raise HTTPException(404, "该智能体未挂载此 MCP")
    m = (await db.execute(select(MCPConnector).where(MCPConnector.id == mid))).scalar_one_or_none()
    if not m:
        raise HTTPException(404, "MCP 不存在")
    try:
        from ..runtime.mcp_manager import list_mcp_tools
        return await list_mcp_tools(m, timeout=20.0)
    except Exception as e:
        raise HTTPException(400, f"连接失败: {e}")


@router.get("/agents")
async def my_agents(
    limit: int = 100,
    offset: int = 0,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role.code in ("admin", "operator"):
        base = select(Agent).where(Agent.enabled.is_(True))
    else:
        sub = select(RoleAgentGrant.agent_id).where(RoleAgentGrant.role_id == user.role_id)
        base = select(Agent).where(Agent.id.in_(sub), Agent.enabled.is_(True))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (await db.execute(base.order_by(Agent.id).limit(limit).offset(offset))).scalars().all()

    out: list[AgentOut] = []
    for a in rows:
        skill_ids = [r[0] for r in (await db.execute(select(AgentSkill.skill_id).where(AgentSkill.agent_id == a.id))).all()]
        mcp_ids = [r[0] for r in (await db.execute(select(AgentMCP.mcp_id).where(AgentMCP.agent_id == a.id))).all()]
        v = AgentOut.model_validate(a, from_attributes=True)
        v.skill_ids = skill_ids; v.mcp_ids = mcp_ids
        out.append(v)
    return {"items": out, "total": total}


# ---------- Conversations ----------
@router.get("/conversations")
async def list_conversations(
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    total = (await db.execute(
        select(func.count(Conversation.id)).where(Conversation.user_id == user.id)
    )).scalar_one()
    rows = (await db.execute(
        select(Conversation).where(Conversation.user_id == user.id)
        .order_by(desc(Conversation.updated_at)).limit(limit).offset(offset)
    )).scalars().all()
    return {"items": rows, "total": total}


@router.get("/conversations/search")
async def search_conversations(
    q: str = "",
    agent_id: int | None = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    """搜索对话 — 按标题和消息内容模糊匹配。"""
    if not q or len(q.strip()) < 1:
        return []
    
    # 搜索标题匹配
    stmt = (
        select(Conversation)
        .where(
            Conversation.user_id == user.id,
            Conversation.title.ilike(f"%{q}%"),
        )
        .order_by(desc(Conversation.updated_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    conv_by_title = {c.id: c for c in result.scalars().all()}
    
    # 搜索消息内容匹配 — 跨数据库兼容
    from ..db.init_db import is_mysql
    if is_mysql():
        # MySQL: 使用 JSON_UNQUOTE + JSON_EXTRACT
        from sqlalchemy import text
        msg_stmt = (
            select(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(
                Conversation.user_id == user.id,
                text("JSON_UNQUOTE(JSON_EXTRACT(messages.content_json, '$.text')) LIKE :pattern"),
            )
            .params(pattern=f"%{q}%")
            .order_by(desc(Message.created_at))
            .limit(limit * 2)
        )
    else:
        # PostgreSQL: 使用 ->> 操作符
        msg_stmt = (
            select(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(
                Conversation.user_id == user.id,
                Message.content_json["text"].astext.ilike(f"%{q}%"),
            )
            .order_by(desc(Message.created_at))
            .limit(limit * 2)
        )
    
    msg_result = await db.execute(msg_stmt)
    conv_ids_from_msg = set()
    for msg in msg_result.scalars().all():
        conv_ids_from_msg.add(msg.conversation_id)
    
    # 合并结果
    all_conv_ids = list(conv_by_title.keys()) + [cid for cid in conv_ids_from_msg if cid not in conv_by_title]
    all_conv_ids = all_conv_ids[:limit]
    
    if not all_conv_ids:
        return []
    
    conv_stmt = (
        select(Conversation)
        .where(Conversation.id.in_(all_conv_ids))
        .order_by(desc(Conversation.updated_at))
    )
    conv_result = await db.execute(conv_stmt)
    conversations = conv_result.scalars().all()
    
    return [
        {
            "id": c.id,
            "title": c.title,
            "agent_id": c.agent_id,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in conversations
    ]


@router.post("/conversations", response_model=ConversationOut)
async def create_conversation(
    payload: ConversationCreate,
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    if payload.agent_id:
        a = (await db.execute(select(Agent).where(Agent.id == payload.agent_id))).scalar_one_or_none()
        if not a or not a.enabled:
            raise HTTPException(404, "agent 不存在")
    else:
        a = await _resolve_default_agent(db, user)
        if not a:
            raise HTTPException(400, "尚未配置默认智能体,请联系管理员")
    c = Conversation(user_id=user.id, agent_id=a.id, title=payload.title or "新对话")
    db.add(c); await db.commit(); await db.refresh(c)
    return c


@router.patch("/conversations/{cid}", response_model=ConversationOut)
async def rename_conversation(
    cid: int, payload: ConversationUpdate,
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    c = (await db.execute(select(Conversation).where(
        Conversation.id == cid, Conversation.user_id == user.id))).scalar_one_or_none()
    if not c:
        raise HTTPException(404, "不存在")
    c.title = payload.title
    await db.commit(); await db.refresh(c)
    return c


@router.delete("/conversations/{cid}")
async def delete_conversation(
    cid: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    c = (await db.execute(select(Conversation).where(
        Conversation.id == cid, Conversation.user_id == user.id))).scalar_one_or_none()
    if not c:
        raise HTTPException(404, "不存在")
    await db.delete(c); await db.commit()
    return {"ok": True}


@router.get("/conversations/{cid}/export")
async def export_conversation(
    cid: int,
    format: str = "markdown",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    """导出对话为 Markdown/HTML/JSON 格式。"""
    if format not in ("markdown", "html", "json"):
        raise HTTPException(400, "format 必须是 markdown/html/json")

    c = (await db.execute(select(Conversation).where(
        Conversation.id == cid, Conversation.user_id == user.id))).scalar_one_or_none()
    if not c:
        raise HTTPException(404, "不存在")

    service = ExportService(db)

    if format == "markdown":
        content = await service.to_markdown(cid)
        media_type = "text/markdown"
        ext = "md"
    elif format == "html":
        content = await service.to_html(cid)
        media_type = "text/html"
        ext = "html"
    else:
        import json as _json
        data = await service.to_json(cid)
        content = _json.dumps(data, ensure_ascii=False, indent=2)
        media_type = "application/json"
        ext = "json"

    return Response(
        content=content.encode("utf-8"),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename=conversation-{cid}.{ext}"},
    )


@router.get("/conversations/{cid}/messages")
async def list_messages(
    cid: int,
    limit: int = 100,
    offset: int = 0,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    c = (await db.execute(select(Conversation).where(
        Conversation.id == cid, Conversation.user_id == user.id))).scalar_one_or_none()
    if not c:
        raise HTTPException(404, "不存在")

    total = (await db.execute(
        select(func.count(Message.id)).where(Message.conversation_id == cid)
    )).scalar_one()

    rows = (await db.execute(
        select(Message).where(Message.conversation_id == cid)
        .order_by(Message.id).limit(limit).offset(offset)
    )).scalars().all()

    # Hydrate user-message file briefs from UploadedFile (we only persist file_ids on send)
    file_id_set: set[int] = set()
    for r in rows:
        if r.role == "user":
            ids = (r.content_json or {}).get("file_ids") if isinstance(r.content_json, dict) else None
            if isinstance(ids, list):
                for x in ids:
                    if isinstance(x, int):
                        file_id_set.add(x)
    file_briefs: dict[int, dict] = {}
    if file_id_set:
        ufs = (await db.execute(
            select(UploadedFile).where(UploadedFile.id.in_(file_id_set))
        )).scalars().all()
        import os as _os
        for u in ufs:
            file_briefs[u.id] = {
                "id": u.id, "name": u.name, "size": u.size, "mime": u.mime,
                "ext": _os.path.splitext(u.name or "")[1].lower(),
                "parse_status": u.parse_status, "parsed_chars": u.parsed_chars or 0,
                "download_url": f"/api/files/{u.id}/raw",
            }
    out = []
    for r in rows:
        item = MessageOut.model_validate(r, from_attributes=True)
        if r.role == "user" and isinstance(r.content_json, dict):
            ids = r.content_json.get("file_ids") or []
            if ids:
                # rebuild on a *copy* so we don't mutate the ORM-tracked dict
                cj = dict(r.content_json)
                cj["files"] = [file_briefs[i] for i in ids if i in file_briefs]
                item.content_json = cj
        out.append(item)
    return {"items": out, "total": total}


# ---------- Streaming chat ----------
# _load_agent_context replaced by shared build_agent_context service


@router.post("/conversations/{cid}/messages")
async def send_message(
    cid: int, payload: ChatIn,
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    c = (await db.execute(select(Conversation).where(
        Conversation.id == cid, Conversation.user_id == user.id))).scalar_one_or_none()
    if not c:
        raise HTTPException(404, "不存在")

    # ---- Security: input filter ----
    from ..core.security_rules import scan_user_input
    from ..db.models import AuditLog
    # [UI_ACTION] route: structured user action from a rendered UI Schema → tool call.
    # [UI_MSG]    route: synthetic user message from a UI Schema button → normal LLM turn,
    #                    but hidden from the chat transcript (no user bubble shown).
    # Both bypass scan_user_input because we authored them.
    is_ui_action = payload.content.startswith("[UI_ACTION]")
    is_ui_msg = payload.content.startswith("[UI_MSG]")
    # The clean text the LLM should actually see for [UI_MSG]
    if is_ui_msg:
        clean_text = payload.content[len("[UI_MSG]"):].lstrip()
    else:
        clean_text = payload.content
    hits = [] if (is_ui_action or is_ui_msg) else scan_user_input(payload.content)
    if hits:
        # Persist a high-signal audit record so admins can review attempted attacks
        db.add(AuditLog(
            user_id=user.id,
            action="input_filter_blocked",
            target_type="conversation",
            target_id=str(cid),
            detail_json={
                "patterns": [h.pattern for h in hits],
                "snippets": [h.snippet for h in hits],
                "raw_preview": payload.content[:300],
            },
        ))
        await db.commit()
        raise HTTPException(400, f"输入包含被禁用的模式: {', '.join(h.pattern for h in hits)}")

    # ---- Per-send file count cap (Agent upload policy) ----
    if payload.file_ids:
        a = (await db.execute(select(Agent).where(Agent.id == c.agent_id))).scalar_one()
        policy = a.upload_policy_json or {}
        max_per_send = int(policy.get("max_files_per_send") or 0)
        if max_per_send > 0 and len(payload.file_ids) > max_per_send:
            raise HTTPException(400,
                f"单次发送最多 {max_per_send} 个文件,本次提交 {len(payload.file_ids)} 个")

    # Load history BEFORE inserting the new user message, so it doesn't appear twice
    # (the current turn is passed separately as user_text into the runner)
    ctx = await build_agent_context(db, agent_id=c.agent_id, conversation_id=cid, user_id=user.id)

    # ---- Quota check (admin exempt) ----
    from ..services.quota_service import check_quota
    await check_quota(db, user)

    user_msg = Message(
        conversation_id=cid, role="user",
        content_json={
            "text": clean_text,
            "file_ids": payload.file_ids,
            **({"hidden": True} if is_ui_msg else {}),
        },
    )
    db.add(user_msg)
    await db.commit()

    # Resolve files: include parsed markdown so the model actually reads contents
    files = []
    if payload.file_ids:
        from datetime import datetime as _dt, timezone as _tz
        rows = (await db.execute(
            select(UploadedFile).where(
                UploadedFile.id.in_(payload.file_ids),
                UploadedFile.user_id == user.id,  # cross-user safeguard
            )
        )).scalars().all()
        for r in rows:
            file_entry = {
                "name": r.name,
                "path": r.path,
                "mime": r.mime,
                "size": r.size,
                "parse_status": r.parse_status,
                "parsed_markdown": r.parsed_markdown if r.parse_status == "done" else None,
                "parse_error": r.parse_error,
            }
            # For files uploaded with parse_mode="never", expose a signed URL
            # so MCP tools (which can't read local paths) can pull raw bytes.
            if r.parse_status == "skipped":
                from ..core.security import create_file_token
                from ..core.config import settings as _s
                base = (_s.BACKEND_BASE_URL or _s.APP_BASE_URL or "").rstrip("/")
                tok = create_file_token(r.id, user.id, minutes=60)
                file_entry["raw_url"] = f"{base}/api/files/{r.id}/raw?t={tok}"
                file_entry["id"] = r.id
            files.append(file_entry)
            # Mark last_used_at so the cleanup task knows this file is still referenced
            r.last_used_at = _dt.now(_tz.utc)
        if rows:
            await db.commit()

    async def event_stream():
        # Use a fresh session inside the generator (request-scoped one is closed after return)
        import asyncio
        async with SessionLocal() as session:
            runner = AgentRunner(ctx, user_id=user.id)
            assistant_text_parts: list[str] = []
            thinking_parts: list[str] = []
            tool_traces: list[dict] = []
            saved_files: list[dict] = []
            saved_uis: list[dict] = []
            tokens_in = tokens_out = latency = 0
            status_str = "ok"
            err = None
            try:
                # [UI_ACTION] short-circuit: parse + validate against this agent's
                # tool whitelist, then call directly without LLM.
                if is_ui_action:
                    from ..ui_schema.types import whitelist_tool_names
                    import re as _re
                    m = _re.match(r"\[UI_ACTION\]\s*tool=([^\s]+)\s+params=(.*)$",
                                  payload.content, _re.DOTALL)
                    if not m:
                        yield f"data: {json.dumps({'type':'error','data':{'message':'UI_ACTION 格式错误'}}, ensure_ascii=False)}\n\n"
                    else:
                        ui_tool = m.group(1).strip()
                        try:
                            ui_params = json.loads(m.group(2))
                            if not isinstance(ui_params, dict):
                                ui_params = {"value": ui_params}
                        except Exception:
                            ui_params = {"raw": m.group(2)}
                        # Build whitelist: skill codes + mcp__<server>__* prefixes + builtins
                        allowed = whitelist_tool_names(ctx.skills, mcp_tool_routes={})
                        is_allowed = (
                            ui_tool in allowed
                            or any(ui_tool.startswith(f"mcp__{mcp.name}__") for mcp in ctx.mcps)
                        )
                        if not is_allowed:
                            yield f"data: {json.dumps({'type':'error','data':{'message':f'工具 {ui_tool} 不在该智能体的允许列表'}}, ensure_ascii=False)}\n\n"
                        else:
                            async for ev in runner.exec_ui_action(ui_tool, ui_params):
                                payload_json = {"type": ev.type, "data": ev.data}
                                yield f"data: {json.dumps(payload_json, ensure_ascii=False)}\n\n"
                                await asyncio.sleep(0)
                                if ev.type == "ui":
                                    saved_uis.append(ev.data if isinstance(ev.data, dict) else {})
                                elif ev.type in ("tool_use", "tool_result"):
                                    slim = _slim_trace_event(payload_json)
                                    if ev.type == "tool_use":
                                        tool_traces = [t for t in tool_traces
                                                       if not (t.get("type") == "tool_use"
                                                               and t.get("data", {}).get("id") == slim.get("data", {}).get("id"))]
                                    tool_traces.append(slim)
                                elif ev.type == "file":
                                    saved_files.append(ev.data if isinstance(ev.data, dict) else {})
                                elif ev.type == "done":
                                    tokens_in = ev.data.get("tokens_in", 0)
                                    tokens_out = ev.data.get("tokens_out", 0)
                                    latency = ev.data.get("latency_ms", 0)
                else:
                    async for ev in runner.stream(clean_text, files):
                        payload_json = {"type": ev.type, "data": ev.data}
                        yield f"data: {json.dumps(payload_json, ensure_ascii=False)}\n\n"
                        # cooperative yield so each chunk is flushed to client immediately
                        await asyncio.sleep(0)
                        if ev.type == "text":
                            assistant_text_parts.append(ev.data.get("text", ""))
                        elif ev.type == "thinking":
                            thinking_parts.append(ev.data.get("text", ""))
                        elif ev.type in ("tool_use", "tool_result"):
                            slim = _slim_trace_event(payload_json)
                            # Dedup tool_use by id: keep the later one (with full input)
                            if ev.type == "tool_use":
                                tool_traces = [t for t in tool_traces
                                               if not (t.get("type") == "tool_use"
                                                       and t.get("data", {}).get("id") == slim.get("data", {}).get("id"))]
                            tool_traces.append(slim)
                        elif ev.type == "file":
                            saved_files.append(ev.data if isinstance(ev.data, dict) else {})
                        elif ev.type == "ui":
                            saved_uis.append(ev.data if isinstance(ev.data, dict) else {})
                        elif ev.type == "done":
                            tokens_in = ev.data.get("tokens_in", 0)
                            tokens_out = ev.data.get("tokens_out", 0)
                            latency = ev.data.get("latency_ms", 0)
                        elif ev.type == "error":
                            status_str = "error"
                            err = ev.data.get("message")
            finally:
                # Persist assistant message + call log
                content_payload = {"text": "".join(assistant_text_parts)}
                if thinking_parts:
                    content_payload["thinking"] = "".join(thinking_parts)
                if saved_files:
                    content_payload["files"] = saved_files
                if saved_uis:
                    content_payload["uis"] = saved_uis
                am = Message(
                    conversation_id=cid, role="assistant",
                    content_json=content_payload,
                    tool_calls_json={"trace": tool_traces} if tool_traces else None,
                    tokens_in=tokens_in, tokens_out=tokens_out,
                )
                session.add(am)
                session.add(CallLog(
                    user_id=user.id, agent_id=c.agent_id, conversation_id=cid,
                    model_id=ctx.model.id if ctx.model else None,
                    tokens_in=tokens_in, tokens_out=tokens_out, latency_ms=latency,
                    status=status_str, error=err,
                ))
                await session.commit()

                # ---- Quota alert (fire-and-forget) ----
                try:
                    from ..services.quota_service import check_and_alert
                    usage = tokens_in + tokens_out
                    # 查询额度记录
                    from ..db.models import UserQuota
                    quota = (await session.execute(
                        select(UserQuota).where(UserQuota.user_id == user.id)
                    )).scalar_one_or_none()
                    if quota and quota.monthly_limit > 0:
                        await check_and_alert(
                            session, user.id, usage, quota.monthly_limit, quota.alert_threshold
                        )
                except Exception as e:
                    # 告警失败不应影响对话
                    logger.warning("quota alert check failed: %s", e)

                # ---- Memory extraction (fire-and-forget) ----
                try:
                    from ..services.memory_extractor import extract_memories_from_conversation
                    # 获取对话历史用于记忆提取
                    history_msgs = (await session.execute(
                        select(Message)
                        .where(Message.conversation_id == cid)
                        .order_by(Message.id)
                        .limit(20)
                    )).scalars().all()
                    msgs_for_extraction = [
                        {"role": m.role, "content_json": m.content_json}
                        for m in history_msgs
                    ]
                    # 异步提取记忆，不阻塞响应
                    import asyncio
                    asyncio.create_task(extract_memories_from_conversation(
                        session, agent_id=c.agent_id, user_id=user.id,
                        conversation_id=cid, messages=msgs_for_extraction,
                        model_id=ctx.model.id if ctx.model else None,
                    ))
                except Exception as e:
                    # 记忆提取失败不应影响对话
                    logger.warning("memory extraction failed: %s", e)

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/conversations/{conv_id}/branch")
async def branch_conversation(
    conv_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    """从指定消息创建分支对话。"""
    message_id = payload.get("message_id")
    if not message_id:
        raise HTTPException(400, "需要 message_id")

    msg = (await db.execute(
        select(Message).where(Message.id == message_id, Message.conversation_id == conv_id)
    )).scalar_one_or_none()
    if not msg:
        raise HTTPException(404, "消息不存在")

    # agent_id 从对话获取
    orig_conv = (await db.execute(
        select(Conversation).where(Conversation.id == conv_id)
    )).scalar_one_or_none()

    new_conv = Conversation(
        user_id=user.id,
        agent_id=orig_conv.agent_id if orig_conv else 1,
        title=f"分支: {(msg.content_json.get('text') or '')[:30]}",
    )
    db.add(new_conv)
    await db.flush()

    old_msgs = (await db.execute(
        select(Message).where(
            Message.conversation_id == conv_id,
            Message.id <= message_id,
        ).order_by(Message.id)
    )).scalars().all()

    for old in old_msgs:
        new_msg = Message(
            conversation_id=new_conv.id,
            role=old.role,
            content_json=old.content_json,
        )
        db.add(new_msg)

    await db.commit()
    await db.refresh(new_conv)
    return {"id": new_conv.id, "title": new_conv.title}
