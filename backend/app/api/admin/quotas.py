"""用户额度管理 API — CRUD + 用量查询"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_db
from ...db.models import User, UserQuota, CallLog
from ...deps import require_admin_or_operator
from ...schemas import UserQuotaIn, UserQuotaUpdate, UserQuotaOut, UserQuotaPage

router = APIRouter(prefix="/api/admin/quotas", tags=["admin-quotas"])


def _to_out(q: UserQuota, user_name: str | None = None) -> UserQuotaOut:
    return UserQuotaOut(
        id=q.id,
        user_id=q.user_id,
        user_name=user_name,
        monthly_limit=q.monthly_limit,
        alert_threshold=q.alert_threshold,
        last_alert_at=q.last_alert_at,
        created_at=q.created_at,
        updated_at=q.updated_at,
    )


@router.get("", response_model=UserQuotaPage)
async def list_quotas(
    page: int = 1, size: int = 20,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin_or_operator),
):
    total_q = await db.execute(select(func.count()).select_from(UserQuota))
    total = total_q.scalar()
    offset = (page - 1) * size
    rows = (await db.execute(
        select(UserQuota).order_by(UserQuota.id).offset(offset).limit(size)
    )).scalars().all()

    # 批量加载 user_name
    user_ids = [r.user_id for r in rows]
    user_map: dict[int, str] = {}
    if user_ids:
        users = (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
        for u in users:
            user_map[u.id] = u.display_name or u.username

    items = [_to_out(r, user_map.get(r.user_id)) for r in rows]
    return UserQuotaPage(items=items, total=total)


@router.post("", response_model=UserQuotaOut)
async def create_quota(
    payload: UserQuotaIn,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_admin_or_operator),
):
    # 验证用户存在
    user = (await db.execute(select(User).where(User.id == payload.user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "用户不存在")
    # 检查是否已有额度
    existing = (await db.execute(
        select(UserQuota).where(UserQuota.user_id == payload.user_id)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(400, "该用户已有额度记录，请使用更新接口")

    q = UserQuota(
        user_id=payload.user_id,
        monthly_limit=payload.monthly_limit,
        alert_threshold=payload.alert_threshold,
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)
    return _to_out(q, user.display_name or user.username)


@router.put("/{user_id}", response_model=UserQuotaOut)
async def update_quota(
    user_id: int,
    payload: UserQuotaUpdate,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_admin_or_operator),
):
    q = (await db.execute(
        select(UserQuota).where(UserQuota.user_id == user_id)
    )).scalar_one_or_none()
    if not q:
        raise HTTPException(404, "该用户暂无限额记录")

    if payload.monthly_limit is not None:
        q.monthly_limit = payload.monthly_limit
    if payload.alert_threshold is not None:
        q.alert_threshold = payload.alert_threshold

    await db.commit()
    await db.refresh(q)

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    return _to_out(q, user.display_name or user.username if user else None)


@router.delete("/{user_id}")
async def delete_quota(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_admin_or_operator),
):
    q = (await db.execute(
        select(UserQuota).where(UserQuota.user_id == user_id)
    )).scalar_one_or_none()
    if not q:
        raise HTTPException(404, "该用户暂无限额记录")
    await db.delete(q)
    await db.commit()
    return {"ok": True}


@router.get("/{user_id}/usage")
async def get_usage(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin_or_operator),
):
    """返回指定用户当月已使用的 token 总量及上限。"""
    from datetime import datetime, timezone
    from calendar import monthrange
    now = datetime.now(timezone.utc)
    month_s = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    _, last_day = monthrange(now.year, now.month)
    month_e = now.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999, tzinfo=None)

    usage_row = (await db.execute(
        select(func.coalesce(func.sum(CallLog.tokens_in + CallLog.tokens_out), 0))
        .where(
            CallLog.user_id == user_id,
            CallLog.created_at >= month_s,
            CallLog.created_at <= month_e,
        )
    )).scalar()

    quota = (await db.execute(
        select(UserQuota).where(UserQuota.user_id == user_id)
    )).scalar_one_or_none()

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()

    return {
        "user_id": user_id,
        "user_name": user.display_name or user.username if user else None,
        "monthly_usage": int(usage_row),
        "monthly_limit": quota.monthly_limit if quota else 0,
        "alert_threshold": quota.alert_threshold if quota else 80,
        "percentage": round(int(usage_row) * 100 / quota.monthly_limit, 1) if quota and quota.monthly_limit > 0 else 0,
    }
