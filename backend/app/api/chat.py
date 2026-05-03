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
async def _load_agent_context(db: AsyncSession, agent_id: int, history_limit: int = 50) -> AgentContext:
    a = (await db.execute(select(Agent).where(Agent.id == agent_id))).scalar_one()
    skill_ids = [r[0] for r in (await db.execute(select(AgentSkill.skill_id).where(AgentSkill.agent_id == a.id))).all()]
    mcp_ids = [r[0] for r in (await db.execute(select(AgentMCP.mcp_id).where(AgentMCP.agent_id == a.id))).all()]
    skills = list((await db.execute(select(Skill).where(Skill.id.in_(skill_ids), Skill.enabled.is_(True)))).scalars().all())
    mcps = list((await db.execute(select(MCPConnector).where(MCPConnector.id.in_(mcp_ids), MCPConnector.enabled.is_(True)))).scalars().all())
    model = (await db.execute(select(Model).where(Model.id == a.default_model_id))).scalar_one_or_none() if a.default_model_id else None
    fb = (await db.execute(select(Model).where(Model.id == a.fallback_model_id))).scalar_one_or_none() if a.fallback_model_id else None
    return AgentContext(agent=a, skills=skills, mcps=mcps, model=model, fallback_model=fb, history=[])


@router.post("/conversations/{cid}/messages")
async def send_message(
    cid: int, payload: ChatIn,
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    c = (await db.execute(select(Conversation).where(
        Conversation.id == cid, Conversation.user_id == user.id))).scalar_one_or_none()
    if not c:
        raise HTTPException(404, "不存在")

    user_msg = Message(conversation_id=cid, role="user",
                       content_json={"text": payload.content, "file_ids": payload.file_ids})
    db.add(user_msg)
    await db.commit()

    # Resolve files
    files = []
    if payload.file_ids:
        rows = (await db.execute(select(UploadedFile).where(UploadedFile.id.in_(payload.file_ids)))).scalars().all()
        files = [{"name": r.name, "path": r.path} for r in rows]

    ctx = await _load_agent_context(db, c.agent_id)

    async def event_stream():
        # Use a fresh session inside the generator (request-scoped one is closed after return)
        import asyncio
        async with SessionLocal() as session:
            runner = AgentRunner(ctx)
            assistant_text_parts: list[str] = []
            thinking_parts: list[str] = []
            tool_traces: list[dict] = []
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
