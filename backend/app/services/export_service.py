"""对话导出服务 — 支持 Markdown/HTML/JSON 格式。"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..db.models import Conversation, Message


class ExportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def to_markdown(self, conversation_id: int) -> str:
        """导出为 Markdown。"""
        stmt = select(Conversation).where(Conversation.id == conversation_id)
        result = await self.db.execute(stmt)
        conv = result.scalar_one_or_none()
        if not conv:
            return ""
        
        lines = [f"# {conv.title}\n"]
        lines.append(f"*导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")
        
        msg_stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        msg_result = await self.db.execute(msg_stmt)
        messages = msg_result.scalars().all()
        
        for msg in messages:
            role = "用户" if msg.role == "user" else "助手"
            content = msg.content_json.get("text", "") if isinstance(msg.content_json, dict) else ""
            lines.append(f"## {role}\n")
            lines.append(f"{content}\n")
        
        return "\n".join(lines)

    async def to_html(self, conversation_id: int) -> str:
        """导出为 HTML。"""
        md = await self.to_markdown(conversation_id)
        # 简单转换（不依赖 markdown 库）
        html_body = md.replace("\n\n", "</p><p>").replace("\n", "<br>")
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>对话导出</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; line-height: 1.6; color: #1e293b; }}
        h1 {{ color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; }}
        h2 {{ color: #475569; margin-top: 24px; }}
        .user {{ background: #eff6ff; padding: 12px 16px; border-radius: 8px; margin: 8px 0; border-left: 3px solid #3b82f6; }}
        .assistant {{ background: #f8fafc; padding: 12px 16px; border-radius: 8px; margin: 8px 0; border-left: 3px solid #22c55e; }}
        .meta {{ color: #94a3b8; font-size: 14px; }}
    </style>
</head>
<body>
<p class="meta">Agent Mill 对话导出</p>
{html_body}
</body>
</html>"""

    async def to_json(self, conversation_id: int) -> dict:
        """导出为 JSON。"""
        stmt = select(Conversation).where(Conversation.id == conversation_id)
        result = await self.db.execute(stmt)
        conv = result.scalar_one_or_none()
        if not conv:
            return {}
        
        msg_stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        msg_result = await self.db.execute(msg_stmt)
        messages = msg_result.scalars().all()
        
        return {
            "title": conv.title,
            "agent_id": conv.agent_id,
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content_json.get("text", "") if isinstance(m.content_json, dict) else "",
                    "timestamp": m.created_at.isoformat() if m.created_at else None,
                }
                for m in messages
            ],
        }
