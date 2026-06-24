"""Shared service for building AgentContext — eliminates duplication across chat.py, im.py, incoming.py, task_runner.py."""
from __future__ import annotations

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import (
    Agent, AgentSkill, AgentMCP, AgentPack,
    Skill, MCPConnector, SolutionPack, Model, Message, Conversation,
)
from ..runtime.agent_runner import AgentContext


# 压缩阈值：消息数超过此值时触发压缩
_COMPRESSION_THRESHOLD = 30
# 保留最近消息数（不压缩）
_RECENT_MESSAGES_KEEP = 10


async def build_agent_context(
    db: AsyncSession,
    *,
    agent: Agent | None = None,
    agent_id: int | None = None,
    conversation_id: int | None = None,
    user_id: int | None = None,
    history_limit: int = 30,
) -> AgentContext:
    """Build an AgentContext by loading skills, MCPs, packs, models, and conversation history.

    Pass either ``agent`` (already loaded) or ``agent_id`` (will query DB).
    """
    if agent is None:
        if agent_id is None:
            raise ValueError("Must provide either agent or agent_id")
        agent = (await db.execute(select(Agent).where(Agent.id == agent_id))).scalar_one()

    skill_ids = [r[0] for r in (await db.execute(
        select(AgentSkill.skill_id).where(AgentSkill.agent_id == agent.id)
    )).all()]
    mcp_ids = [r[0] for r in (await db.execute(
        select(AgentMCP.mcp_id).where(AgentMCP.agent_id == agent.id)
    )).all()]
    pack_ids = [r[0] for r in (await db.execute(
        select(AgentPack.pack_id).where(AgentPack.agent_id == agent.id)
    )).all()]

    skills = list((await db.execute(
        select(Skill).where(Skill.id.in_(skill_ids), Skill.enabled.is_(True))
    )).scalars().all()) if skill_ids else []
    mcps = list((await db.execute(
        select(MCPConnector).where(MCPConnector.id.in_(mcp_ids), MCPConnector.enabled.is_(True))
    )).scalars().all()) if mcp_ids else []
    packs = list((await db.execute(
        select(SolutionPack).where(SolutionPack.id.in_(pack_ids), SolutionPack.enabled.is_(True))
    )).scalars().all()) if pack_ids else []

    model = (await db.execute(
        select(Model).where(Model.id == agent.default_model_id)
    )).scalar_one_or_none() if agent.default_model_id else None
    fb = (await db.execute(
        select(Model).where(Model.id == agent.fallback_model_id)
    )).scalar_one_or_none() if agent.fallback_model_id else None

    history: list[Message] = []
    conversation_summary = ""
    
    if conversation_id is not None:
        # 获取消息总数
        msg_count = (await db.execute(
            select(Message.id).where(Message.conversation_id == conversation_id)
        )).all()
        total_messages = len(msg_count)
        
        if total_messages > _COMPRESSION_THRESHOLD:
            # 消息数超过阈值，使用压缩策略
            # 1. 获取对话摘要（如果有）
            conv = (await db.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )).scalar_one_or_none()
            
            # 2. 如果没有摘要，尝试生成
            if conv and not getattr(conv, 'summary', None):
                from .conversation_compressor import compress_conversation_history
                summary = await compress_conversation_history(
                    db, conversation_id=conversation_id,
                    model_id=model.id if model else None,
                )
                if summary:
                    # 保存摘要到对话
                    conv.summary = summary
                    await db.commit()
                    conversation_summary = summary
            
            # 3. 加载最近的消息（不压缩）
            rows = (await db.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id, Message.role.in_(["user", "assistant"]))
                .order_by(desc(Message.id))
                .limit(_RECENT_MESSAGES_KEEP)
            )).scalars().all()
            history = list(reversed(rows))
        else:
            # 消息数未超过阈值，正常加载
            rows = (await db.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id, Message.role.in_(["user", "assistant"]))
                .order_by(desc(Message.id))
                .limit(history_limit)
            )).scalars().all()
            history = list(reversed(rows))

    # 加载记忆上下文
    memory_context = ""
    if user_id is not None:
        from .memory_service import MemoryService
        memory_svc = MemoryService(db)
        memory_context = await memory_svc.build_memory_context(agent.id, user_id, limit=5)

    # 加载知识库上下文
    knowledge_context = ""
    if agent.kb_id:
        from .knowledge_service import KnowledgeService
        try:
            kb_svc = KnowledgeService(db)
            # ponytail: 用最后一条用户消息作为检索 query；多轮对话场景可改进为累计上下文
            last_user_msg = next((m.content for m in reversed(history) if m.role == "user"), "")
            if last_user_msg:
                results = await kb_svc.search(agent.kb_id, last_user_msg, top_k=3)
                if results:
                    chunks = "\n\n".join(r["content"] for r in results)
                    knowledge_context = f"以下是从知识库中检索到的相关信息：\n\n{chunks}"
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Knowledge search failed: %s", e)

    return AgentContext(
        agent=agent,
        skills=skills,
        mcps=mcps,
        packs=packs,
        model=model,
        fallback_model=fb,
        history=history,
        memory_context=memory_context,
        conversation_summary=conversation_summary,
        _knowledge_context=knowledge_context,
    )
