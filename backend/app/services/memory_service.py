"""Agent 持久记忆服务 — 管理数字员工的记忆。"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from ..db.models import AgentMemory

logger = logging.getLogger(__name__)


def _is_duplicate(new_text: str, existing_texts: list[str], threshold: float = 0.8) -> bool:
    """简单的文本重叠去重。
    
    Args:
        new_text: 新记忆文本
        existing_texts: 已有记忆文本列表
        threshold: 相似度阈值，默认 0.8
    
    Returns:
        bool: 如果与已有记忆重复返回 True
    """
    new_words = set(new_text.lower().split())
    if not new_words:
        return False
    for existing in existing_texts:
        existing_words = set(existing.lower().split())
        if not existing_words:
            continue
        overlap = len(new_words & existing_words) / min(len(new_words), len(existing_words))
        if overlap >= threshold:
            return True
    return False


def _decay_importance(importance: float, created_at: datetime | None) -> float:
    """importance 随时间衰减，90天后衰减到0。
    
    Args:
        importance: 原始重要度
        created_at: 创建时间
    
    Returns:
        float: 衰减后的重要度
    """
    if not created_at:
        return importance
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    days = (now - created_at).days
    decay = max(0.0, 1.0 - days / 90.0)
    return importance * decay


class MemoryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_memory(
        self, agent_id: int, user_id: int,
        memory_type: str, content: str,
        importance: float = 0.5,
        source_conversation_id: int | None = None,
    ) -> AgentMemory:
        """保存一条新记忆。"""
        memory = AgentMemory(
            agent_id=agent_id,
            user_id=user_id,
            memory_type=memory_type,
            content=content,
            importance=importance,
            source_conversation_id=source_conversation_id,
        )
        self.db.add(memory)
        await self.db.commit()
        await self.db.refresh(memory)
        logger.info("Memory saved: agent=%d user=%d type=%s", agent_id, user_id, memory_type)
        return memory

    async def get_memories(
        self, agent_id: int, user_id: int, limit: int = 10
    ) -> list[dict]:
        """获取相关记忆（按衰减后重要度+最近访问排序）。
        
        Returns:
            list[dict]: 包含 memory 对象和 effective_importance 的字典列表
        """
        stmt = (
            select(AgentMemory)
            .where(
                AgentMemory.agent_id == agent_id,
                AgentMemory.user_id == user_id,
                AgentMemory.is_active == True,  # noqa: E712
            )
            .order_by(desc(AgentMemory.importance), desc(AgentMemory.last_accessed_at))
            .limit(limit * 2)  # 多取一些以便衰减后排序
        )
        result = await self.db.execute(stmt)
        memories = list(result.scalars().all())
        
        # 应用时间衰减并计算有效重要度
        memory_dicts = []
        for m in memories:
            effective_importance = _decay_importance(m.importance, m.created_at)
            memory_dicts.append({
                "memory": m,
                "effective_importance": effective_importance,
            })
        
        # 按 effective_importance 降序排序
        memory_dicts.sort(key=lambda x: x["effective_importance"], reverse=True)
        
        # 取 top limit 个
        memory_dicts = memory_dicts[:limit]
        
        # 更新访问计数
        for item in memory_dicts:
            m = item["memory"]
            m.access_count = (m.access_count or 0) + 1
            m.last_accessed_at = datetime.now(timezone.utc)
        if memory_dicts:
            await self.db.commit()
        
        return memory_dicts

    async def delete_memory(self, memory_id: int, user_id: int) -> bool:
        """软删除一条记忆。"""
        stmt = select(AgentMemory).where(
            AgentMemory.id == memory_id,
            AgentMemory.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        memory = result.scalar_one_or_none()
        if not memory:
            return False
        memory.is_active = False
        await self.db.commit()
        return True

    async def build_memory_context(self, agent_id: int, user_id: int, limit: int = 5) -> str:
        """构建记忆上下文字符串，用于注入 system_prompt。"""
        memory_dicts = await self.get_memories(agent_id, user_id, limit)
        if not memory_dicts:
            return ""
        lines = []
        type_labels = {"preference": "偏好", "fact": "事实", "decision": "决策", "context": "上下文"}
        for item in memory_dicts:
            m = item["memory"]
            label = type_labels.get(m.memory_type, m.memory_type)
            lines.append(f"- [{label}] {m.content}")
        return "\n".join(lines)