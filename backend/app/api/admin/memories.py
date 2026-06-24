"""Agent 记忆管理 API。"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from ...db.session import get_db
from ...db.models import AgentMemory, User
from ...deps import current_user
from ...services.memory_service import MemoryService

router = APIRouter(prefix="/api/memories", tags=["memories"])


class MemoryCreate(BaseModel):
    memory_type: str  # preference/fact/decision/context
    content: str
    importance: float = 0.5
    source_conversation_id: int | None = None


class MemoryOut(BaseModel):
    id: int
    memory_type: str
    content: str
    importance: float
    access_count: int
    source_conversation_id: int | None
    created_at: str

    class Config:
        from_attributes = True


@router.get("/{agent_id}")
async def list_memories(
    agent_id: int,
    user_id: int | None = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    """获取某个 Agent 对指定用户的记忆列表。管理员可查任意用户，普通用户只能查自己。"""
    from ...db.models import Role
    from ...services.memory_service import MemoryService
    role = (await db.execute(select(Role).where(Role.id == user.role_id))).scalar_one_or_none() if user.role_id else None
    target_user_id = user_id if (user_id and role and role.code == "admin") else user.id
    service = MemoryService(db)
    memories = await service.get_memories(agent_id, target_user_id, limit)
    return [
        {
            "id": m.id,
            "memory_type": m.memory_type,
            "content": m.content,
            "importance": m.importance,
            "access_count": m.access_count,
            "source_conversation_id": m.source_conversation_id,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in memories
    ]


@router.post("/{agent_id}")
async def create_memory(
    agent_id: int,
    body: MemoryCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    """手动创建一条记忆。"""
    service = MemoryService(db)
    memory = await service.save_memory(
        agent_id=agent_id,
        user_id=user.id,
        memory_type=body.memory_type,
        content=body.content,
        importance=body.importance,
        source_conversation_id=body.source_conversation_id,
    )
    return {"id": memory.id, "status": "created"}


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    """删除一条记忆。"""
    service = MemoryService(db)
    ok = await service.delete_memory(memory_id, user.id)
    if not ok:
        raise HTTPException(404, "记忆不存在")
    return {"status": "deleted"}