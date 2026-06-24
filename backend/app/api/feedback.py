"""用户反馈 API — 点赞/点踩助手消息。"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from ..db.session import get_db
from ..db.models import MessageFeedback, Message, Conversation, User
from ..deps import current_user

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


class FeedbackCreate(BaseModel):
    message_id: int
    rating: str  # "like" or "dislike"
    reason: str | None = None


class FeedbackOut(BaseModel):
    id: int
    message_id: int
    rating: str
    reason: str | None
    created_at: str

    class Config:
        from_attributes = True


@router.post("")
async def submit_feedback(
    body: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    """提交或更新对某条消息的反馈（幂等）。"""
    if body.rating not in ("like", "dislike"):
        raise HTTPException(400, "rating 必须是 like 或 dislike")

    # 验证消息存在
    msg = (await db.execute(
        select(Message).where(Message.id == body.message_id)
    )).scalar_one_or_none()
    if not msg:
        raise HTTPException(404, "消息不存在")

    # 查找已有反馈（幂等）
    existing = (await db.execute(
        select(MessageFeedback).where(
            MessageFeedback.user_id == user.id,
            MessageFeedback.message_id == body.message_id,
        )
    )).scalar_one_or_none()

    if existing:
        existing.rating = body.rating
        existing.reason = body.reason
        feedback = existing
    else:
        # agent_id 从对话获取
        conv = (await db.execute(
            select(Conversation).where(Conversation.id == msg.conversation_id)
        )).scalar_one_or_none()
        feedback = MessageFeedback(
            user_id=user.id,
            message_id=body.message_id,
            agent_id=conv.agent_id if conv else None,
            conversation_id=msg.conversation_id,
            rating=body.rating,
            reason=body.reason,
        )
        db.add(feedback)

    await db.commit()
    await db.refresh(feedback)
    return {"id": feedback.id, "rating": feedback.rating, "status": "saved"}


@router.get("/check")
async def check_feedback(
    message_ids: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    """批量查询消息的反馈状态。"""
    ids = [int(x) for x in message_ids.split(",") if x.strip()]
    if not ids:
        return {}

    rows = (await db.execute(
        select(MessageFeedback).where(
            MessageFeedback.user_id == user.id,
            MessageFeedback.message_id.in_(ids),
        )
    )).scalars().all()

    return {r.message_id: {"rating": r.rating, "id": r.id} for r in rows}


@router.delete("/{feedback_id}")
async def delete_feedback(
    feedback_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    """删除一条反馈。"""
    fb = (await db.execute(
        select(MessageFeedback).where(
            MessageFeedback.id == feedback_id,
            MessageFeedback.user_id == user.id,
        )
    )).scalar_one_or_none()
    if not fb:
        raise HTTPException(404, "反馈不存在")
    await db.delete(fb)
    await db.commit()
    return {"status": "deleted"}


@router.get("/stats")
async def feedback_stats(
    agent_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    """获取反馈统计（管理员用）。"""
    # 普通用户只能看自己的，管理员可看全部
    from ..db.models import Role
    is_admin = False
    if user.role_id:
        role = (await db.execute(
            select(Role).where(Role.id == user.role_id)
        )).scalar_one_or_none()
        if role and role.code == "admin":
            is_admin = True

    base_filter = []
    if not is_admin:
        base_filter.append(MessageFeedback.user_id == user.id)
    if agent_id:
        base_filter.append(MessageFeedback.agent_id == agent_id)

    # 统计点赞/点踩数
    stats = (await db.execute(
        select(
            MessageFeedback.rating,
            func.count(MessageFeedback.id).label("count"),
        )
        .where(*base_filter)
        .group_by(MessageFeedback.rating)
    )).all()

    result = {"like": 0, "dislike": 0}
    for row in stats:
        result[row.rating] = row.count

    total = result["like"] + result["dislike"]
    result["total"] = total
    result["satisfaction_rate"] = round(result["like"] / total * 100, 1) if total > 0 else 0

    return result
