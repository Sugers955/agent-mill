"""IM 机器人 Webhook 接收端点 — 钉钉/飞书机器人回调入口。"""
from __future__ import annotations
import logging
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ...db.session import get_db
from ...db.models import Agent, User, Conversation, Message
from ...integrations.dingtalk import DingTalkBot
from ...integrations.feishu import FeishuBot
from ...runtime.agent_runner import AgentRunner
from ...services.agent_context_service import build_agent_context

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def _resolve_agent(db: AsyncSession) -> Agent | None:
    """获取默认或第一个可用 Agent。"""
    stmt = select(Agent).where(Agent.enabled == True, Agent.is_default == True)  # noqa: E712
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()
    if not agent:
        stmt = select(Agent).where(Agent.enabled == True).limit(1)  # noqa: E712
        result = await db.execute(stmt)
        agent = result.scalar_one_or_none()
    return agent


async def _get_or_create_user(
    db: AsyncSession, platform: str, sender_id: str, display_name: str = ""
) -> User:
    """创建或获取平台用户。"""
    username = f"{platform}_{sender_id}"
    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            username=username,
            password_hash="",
            display_name=display_name or sender_id,
            role_id=3,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


async def _run_agent(db: AsyncSession, agent: Agent, user: User, user_text: str) -> str:
    """调用 Agent 并返回回复文本。"""
    conv = Conversation(user_id=user.id, agent_id=agent.id, title=user_text[:50])
    db.add(conv)
    await db.commit()
    await db.refresh(conv)

    msg = Message(conversation_id=conv.id, role="user", content_json={"text": user_text})
    db.add(msg)
    await db.commit()

    # 构建 AgentContext
    ctx = await build_agent_context(db, agent=agent, conversation_id=conv.id, user_id=user.id)
    runner = AgentRunner(ctx, user_id=user.id)
    response_text = ""
    async for event in runner.run():
        if hasattr(event, "type") and event.type == "text":
            response_text += event.data.get("text", "") if isinstance(event.data, dict) else str(event.data)
        elif isinstance(event, dict) and event.get("type") == "text":
            response_text += event.get("data", {}).get("text", "")

    if response_text:
        assistant_msg = Message(
            conversation_id=conv.id,
            role="assistant",
            content_json={"text": response_text},
        )
        db.add(assistant_msg)
        await db.commit()

    return response_text


@router.post("/dingtalk")
async def dingtalk_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """钉钉机器人回调。"""
    data = await request.json()

    # 解析消息
    parsed = DingTalkBot.parse_callback(data)
    if not parsed or not parsed.get("text"):
        return {"msg": "ok"}

    user_text = parsed["text"]
    sender_id = parsed.get("sender_id", "unknown")
    sender_nick = parsed.get("sender_nick", "")

    logger.info("DingTalk message from %s (%s): %s", sender_nick, sender_id, user_text[:100])

    # 获取 Agent
    agent = await _resolve_agent(db)
    if not agent:
        return {"msg": "no agent available"}

    # 获取用户
    user = await _get_or_create_user(db, "dingtalk", sender_id, sender_nick)

    try:
        response_text = await _run_agent(db, agent, user, user_text)
        return {"msg": "ok", "reply": response_text}
    except Exception as e:
        logger.exception("DingTalk agent error")
        return {"msg": "error", "detail": str(e)}


@router.post("/feishu")
async def feishu_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """飞书机器人回调。"""
    data = await request.json()

    # 飞书 URL 验证
    if data.get("type") == "url_verification":
        return {"challenge": data.get("challenge", "")}

    parsed = FeishuBot.parse_callback(data)
    if not parsed or not parsed.get("text"):
        return {"msg": "ok"}

    user_text = parsed["text"]
    sender_id = parsed.get("sender_id", "unknown")

    logger.info("Feishu message from %s: %s", sender_id, user_text[:100])

    # 获取 Agent
    agent = await _resolve_agent(db)
    if not agent:
        return {"msg": "no agent available"}

    # 获取用户
    user = await _get_or_create_user(db, "feishu", sender_id, f"飞书用户-{sender_id[:8]}")

    try:
        response_text = await _run_agent(db, agent, user, user_text)
        return {"msg": "ok", "reply": response_text}
    except Exception as e:
        logger.exception("Feishu agent error")
        return {"msg": "error", "detail": str(e)}
