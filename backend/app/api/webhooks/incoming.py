"""外部 Webhook 接收端点 — 外部系统触发数字员工执行。"""
from __future__ import annotations
import hashlib
import hmac
import json
import logging
from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ...db.session import get_db
from ...db.models import (
    WebhookConfig, Agent, User, Conversation, Message,
)
from ...runtime.agent_runner import AgentRunner
from ...services.agent_context_service import build_agent_context

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class WebhookTrigger(BaseModel):
    message: str
    context: dict = {}


@router.post("/trigger/{webhook_id}")
async def trigger_webhook(
    webhook_id: int,
    body: WebhookTrigger,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """通过 Webhook 触发数字员工。"""
    # 查找 Webhook 配置
    stmt = select(WebhookConfig).where(
        WebhookConfig.id == webhook_id,
        WebhookConfig.is_active == True,  # noqa: E712
    )
    result = await db.execute(stmt)
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(404, "Webhook 不存在或未启用")

    # 验证签名（可选）
    signature = request.headers.get("X-Webhook-Signature", "")
    if signature and config.secret:
        expected = hmac.HMAC(
            config.secret.encode(), body.message.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise HTTPException(403, "签名验证失败")

    # 获取 Agent
    stmt = select(Agent).where(Agent.id == config.agent_id, Agent.enabled == True)  # noqa: E712
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(500, "关联的 Agent 不存在或未启用")

    # 创建系统用户
    username = f"webhook_{config.id}"
    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            username=username,
            password_hash="",
            display_name=f"Webhook-{config.name}",
            role_id=3,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    # 构建用户消息
    msg_content = body.message
    if body.context:
        msg_content += f"\n\n[上下文: {json.dumps(body.context, ensure_ascii=False)}]"

    try:
        reply = await _run_agent(db, agent, user, msg_content)
        return {"status": "ok", "conversation_id": None, "reply": reply}
    except Exception as e:
        logger.exception("Webhook agent error")
        raise HTTPException(500, f"Agent 执行失败: {e}")


async def _run_agent(db: AsyncSession, agent: Agent, user: User, user_text: str) -> str:
    """调用 Agent 并返回回复文本（参照 im.py 的 _run_agent）。"""
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
