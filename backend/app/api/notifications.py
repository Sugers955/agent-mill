"""In-app notifications API. Per-user scoped."""
from __future__ import annotations
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, desc, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..db.models import Notification, User
from ..deps import current_user
from ..schemas import NotificationOut, NotificationPage

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=NotificationPage)
async def list_notifications(unread: int = 0, limit: int = 30, offset: int = 0,
                              user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    q = select(Notification).where(Notification.user_id == user.id)
    if unread:
        q = q.where(Notification.read_at.is_(None))
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    unread_count = (await db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == user.id, Notification.read_at.is_(None))
    )).scalar_one()
    rows = (await db.execute(
        q.order_by(desc(Notification.id)).limit(limit).offset(offset)
    )).scalars().all()
    return NotificationPage(
        items=[NotificationOut.model_validate(r, from_attributes=True) for r in rows],
        total=int(total or 0),
        unread=int(unread_count or 0),
    )


@router.post("/{nid}/read", response_model=NotificationOut)
async def mark_read(nid: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    n = (await db.execute(select(Notification).where(
        Notification.id == nid, Notification.user_id == user.id))).scalar_one_or_none()
    if not n:
        raise HTTPException(404, "不存在")
    if n.read_at is None:
        n.read_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(n)
    return NotificationOut.model_validate(n, from_attributes=True)


@router.post("/read-all")
async def mark_all_read(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(timezone.utc))
    )
    await db.commit()
    return {"ok": True}
