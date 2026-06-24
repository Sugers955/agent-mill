"""对话上下文压缩服务 — 长对话自动摘要历史消息，降低 Token 消耗。"""
from __future__ import annotations
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)

# 摘要 prompt 模板
_SUMMARY_PROMPT = """请将以下对话历史压缩为简洁摘要，保留关键信息：

{history}

要求：
1. 保留用户的核心需求和决策
2. 保留助手的关键回答和结论
3. 保留重要的事实和数据
4. 压缩到原文的 1/3 长度以内
5. 使用中文输出

摘要："""

# 触发压缩的消息数阈值
COMPRESSION_THRESHOLD = 30
# 保留最近的消息数（不压缩）
RECENT_MESSAGES_KEEP = 10


async def compress_conversation_history(
    db: AsyncSession,
    *,
    conversation_id: int,
    model_id: int | None = None,
) -> str | None:
    """压缩对话历史，返回摘要文本。
    
    设计原则：
    - 只在消息数超过阈值时触发
    - 保留最近 N 条消息不压缩
    - 使用 LLM 生成摘要
    - 失败时返回 None，不影响正常流程
    """
    try:
        from ..db.models import Message, Model
        
        # 获取所有消息
        messages = list((await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id)
        )).scalars().all())
        
        # 检查是否需要压缩
        if len(messages) <= COMPRESSION_THRESHOLD:
            return None
        
        # 分离旧消息和新消息
        old_messages = messages[:-RECENT_MESSAGES_KEEP]
        # new_messages = messages[-RECENT_MESSAGES_KEEP:]  # 保留不压缩
        
        # 构建旧消息文本
        history_text = ""
        for msg in old_messages:
            role = "用户" if msg.role == "user" else "助手"
            content = msg.content_json or {}
            if isinstance(content, dict):
                text = content.get("text", "")
            else:
                text = str(content)
            if text:
                history_text += f"{role}: {text[:500]}\n\n"
        
        if not history_text.strip():
            return None
        
        # 获取模型
        if model_id:
            model = (await db.execute(
                select(Model).where(Model.id == model_id)
            )).scalar_one_or_none()
        else:
            model = None
        
        if not model:
            return None
        
        # 调用 LLM 生成摘要
        import httpx
        prompt = _SUMMARY_PROMPT.format(history=history_text[:5000])
        
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{model.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {model.api_key}"},
                json={
                    "model": model.model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 1000,
                },
            )
            resp.raise_for_status()
            result = resp.json()
        
        summary = result["choices"][0]["message"]["content"].strip()
        logger.info("Compressed conversation %d: %d messages → summary",
                    conversation_id, len(old_messages))
        return summary
        
    except Exception as e:
        logger.warning("Conversation compression failed: %s", e)
        return None


def build_compressed_context(
    summary: str | None,
    recent_messages: list[dict],
) -> str:
    """构建压缩后的上下文字符串，用于注入 prompt。
    
    格式：
    [之前的对话摘要]
    摘要内容...
    
    [最近的对话]
    用户: xxx
    助手: xxx
    """
    parts = []
    
    if summary:
        parts.append(f"[之前的对话摘要]\n{summary}\n")
    
    if recent_messages:
        recent_text = ""
        for msg in recent_messages:
            role = "用户" if msg.get("role") == "user" else "助手"
            content = msg.get("content_json", {})
            if isinstance(content, dict):
                text = content.get("text", "")
            else:
                text = str(content)
            if text:
                recent_text += f"{role}: {text[:500]}\n\n"
        if recent_text:
            parts.append(f"[最近的对话]\n{recent_text}")
    
    return "\n".join(parts)
