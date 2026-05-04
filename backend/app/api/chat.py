from __future__ import annotations
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from ..db.session import get_db, SessionLocal
from ..db.models import (
    Agent, AgentSkill, AgentMCP, RoleAgentGrant, Skill, MCPConnector, Model,
    Conversation, Message, User, UploadedFile, CallLog,
)
from ..deps import current_user
from ..schemas import (
    AgentOut, ConversationOut, ConversationCreate, ConversationUpdate,
    MessageOut, ChatIn,
)
from ..runtime.agent_runner import AgentRunner, AgentContext

router = APIRouter(prefix="/api", tags=["chat"])


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
    if a and _user_can_access(user, a, db):
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


def _user_can_access(user: User, agent: Agent, db: AsyncSession) -> bool:
    # Manager roles see all agents; for plain users we don't check here (too eager) — caller may re-validate.
    return True


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

    return {
        "model": _model_brief(model),
        "fallback_model": _model_brief(fb),
        "skills": [
            {"id": s.id, "code": s.code, "name": s.name, "type": s.type,
             "description": s.description, "enabled": s.enabled}
            for s in skills
        ],
        "mcps": [
            {"id": m.id, "name": m.name, "transport": m.transport, "enabled": m.enabled}
            for m in mcps
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


@router.get("/agents", response_model=list[AgentOut])
async def my_agents(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    if user.role.code in ("admin", "operator"):
        rows = (await db.execute(select(Agent).where(Agent.enabled.is_(True)))).scalars().all()
    else:
        sub = select(RoleAgentGrant.agent_id).where(RoleAgentGrant.role_id == user.role_id)
        rows = (await db.execute(
            select(Agent).where(Agent.id.in_(sub), Agent.enabled.is_(True))
        )).scalars().all()
    out: list[AgentOut] = []
    for a in rows:
        skill_ids = [r[0] for r in (await db.execute(select(AgentSkill.skill_id).where(AgentSkill.agent_id == a.id))).all()]
        mcp_ids = [r[0] for r in (await db.execute(select(AgentMCP.mcp_id).where(AgentMCP.agent_id == a.id))).all()]
        v = AgentOut.model_validate(a, from_attributes=True)
        v.skill_ids = skill_ids; v.mcp_ids = mcp_ids
        out.append(v)
    return out


# ---------- Conversations ----------
@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(Conversation).where(Conversation.user_id == user.id).order_by(desc(Conversation.updated_at))
    )).scalars().all()
    return rows


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


@router.get("/conversations/{cid}/messages", response_model=list[MessageOut])
async def list_messages(cid: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    c = (await db.execute(select(Conversation).where(
        Conversation.id == cid, Conversation.user_id == user.id))).scalar_one_or_none()
    if not c:
        raise HTTPException(404, "不存在")
    rows = (await db.execute(
        select(Message).where(Message.conversation_id == cid).order_by(Message.id)
    )).scalars().all()
    return rows


# ---------- Streaming chat ----------
async def _load_agent_context(db: AsyncSession, agent_id: int, conversation_id: int | None = None,
                               history_limit: int = 30) -> AgentContext:
    a = (await db.execute(select(Agent).where(Agent.id == agent_id))).scalar_one()
    skill_ids = [r[0] for r in (await db.execute(select(AgentSkill.skill_id).where(AgentSkill.agent_id == a.id))).all()]
    mcp_ids = [r[0] for r in (await db.execute(select(AgentMCP.mcp_id).where(AgentMCP.agent_id == a.id))).all()]
    skills = list((await db.execute(select(Skill).where(Skill.id.in_(skill_ids), Skill.enabled.is_(True)))).scalars().all())
    mcps = list((await db.execute(select(MCPConnector).where(MCPConnector.id.in_(mcp_ids), MCPConnector.enabled.is_(True)))).scalars().all())
    model = (await db.execute(select(Model).where(Model.id == a.default_model_id))).scalar_one_or_none() if a.default_model_id else None
    fb = (await db.execute(select(Model).where(Model.id == a.fallback_model_id))).scalar_one_or_none() if a.fallback_model_id else None

    # Load prior turns so the model has conversation context. We load the most recent
    # `history_limit` user/assistant messages, in chronological order, EXCLUDING the
    # message currently being sent (caller persists it after this loads).
    history: list[Message] = []
    if conversation_id is not None:
        from sqlalchemy import desc as _desc
        rows = (await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id, Message.role.in_(["user", "assistant"]))
            .order_by(_desc(Message.id))
            .limit(history_limit)
        )).scalars().all()
        history = list(reversed(rows))

    return AgentContext(agent=a, skills=skills, mcps=mcps, model=model, fallback_model=fb, history=history)


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
    hits = scan_user_input(payload.content)
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

    # Load history BEFORE inserting the new user message, so it doesn't appear twice
    # (the current turn is passed separately as user_text into the runner)
    ctx = await _load_agent_context(db, c.agent_id, conversation_id=cid)

    user_msg = Message(conversation_id=cid, role="user",
                       content_json={"text": payload.content, "file_ids": payload.file_ids})
    db.add(user_msg)
    await db.commit()

    # Resolve files
    files = []
    if payload.file_ids:
        rows = (await db.execute(select(UploadedFile).where(UploadedFile.id.in_(payload.file_ids)))).scalars().all()
        files = [{"name": r.name, "path": r.path} for r in rows]

    async def event_stream():
        # Use a fresh session inside the generator (request-scoped one is closed after return)
        import asyncio
        async with SessionLocal() as session:
            runner = AgentRunner(ctx, user_id=user.id)
            assistant_text_parts: list[str] = []
            thinking_parts: list[str] = []
            tool_traces: list[dict] = []
            saved_files: list[dict] = []
            tokens_in = tokens_out = latency = 0
            status_str = "ok"
            err = None
            try:
                async for ev in runner.stream(payload.content, files):
                    payload_json = {"type": ev.type, "data": ev.data}
                    yield f"data: {json.dumps(payload_json, ensure_ascii=False)}\n\n"
                    # cooperative yield so each chunk is flushed to client immediately
                    await asyncio.sleep(0)
                    if ev.type == "text":
                        assistant_text_parts.append(ev.data.get("text", ""))
                    elif ev.type == "thinking":
                        thinking_parts.append(ev.data.get("text", ""))
                    elif ev.type in ("tool_use", "tool_result"):
                        tool_traces.append(payload_json)
                    elif ev.type == "file":
                        saved_files.append(ev.data if isinstance(ev.data, dict) else {})
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

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
