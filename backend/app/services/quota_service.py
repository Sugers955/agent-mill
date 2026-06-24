"""用户月度额度检查与告警服务。

- get_user_monthly_usage: 从 call_logs 聚合当月已用量
- check_quota: 在对话发送前校验额度是否超限（管理员豁免）
- check_and_alert: 对话结束后检查是否触发告警（每月一次）
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from calendar import monthrange

from fastapi import HTTPException
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import User, UserQuota, CallLog, Notification

logger = logging.getLogger(__name__)


def _month_start(dt: datetime | None = None) -> datetime:
    """返回指定时间（默认当前 UTC）所在月份的 1 日 00:00:00 UTC（naive）。"""
    if dt is None:
        dt = datetime.now(timezone.utc)
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=None)


def _month_end(dt: datetime | None = None) -> datetime:
    """返回指定时间（默认当前 UTC）所在月份的最后一天 23:59:59.999999 UTC（naive）。"""
    if dt is None:
        dt = datetime.now(timezone.utc)
    _, last_day = monthrange(dt.year, dt.month)
    return dt.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999, tzinfo=None)


async def get_user_monthly_usage(db: AsyncSession, user_id: int) -> int:
    """返回用户当月已使用的 token 总量（tokens_in + tokens_out）。"""
    start = _month_start()
    end = _month_end()
    row = (await db.execute(
        select(func.coalesce(func.sum(CallLog.tokens_in + CallLog.tokens_out), 0))
        .where(
            CallLog.user_id == user_id,
            CallLog.created_at >= start,
            CallLog.created_at <= end,
        )
    )).scalar()
    return int(row)


async def check_quota(db: AsyncSession, user: User) -> None:
    """对话发送前检查用户配额。

    管理员（role.code == "admin"）直接通过。
    普通用户：无额度记录或 monthly_limit==0 不限；否则比较用量与上限。
    超限时抛出 HTTPException(429)。
    """
    if user.role.code == "admin":
        return

    quota = (await db.execute(
        select(UserQuota).where(UserQuota.user_id == user.id)
    )).scalar_one_or_none()

    if not quota or quota.monthly_limit <= 0:
        return  # 未设置额度，不限

    usage = await get_user_monthly_usage(db, user.id)
    if usage >= quota.monthly_limit:
        raise HTTPException(
            status_code=429,
            detail=f"本月额度已用完（已用 {usage:,} / 上限 {quota.monthly_limit:,} tokens），请联系管理员。",
        )


async def check_and_alert(db: AsyncSession, user_id: int, usage: int, limit: int, threshold: int) -> None:
    """对话结束后检查是否需要发送额度告警。

    仅在用量首次达到阈值百分比时发送（每月最多一次），通过 last_alert_at 去重。
    """
    if limit <= 0 or threshold <= 0:
        return

    usage_pct = int(usage * 100 / limit)
    if usage_pct < threshold:
        return

    quota = (await db.execute(
        select(UserQuota).where(UserQuota.user_id == user_id)
    )).scalar_one_or_none()
    if not quota:
        return

    # 每月只告警一次：如果 last_alert_at 在当月内，跳过
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    month_s = _month_start()
    if quota.last_alert_at and quota.last_alert_at >= month_s:
        return

    # 查询用户信息
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        return

    user_name = user.display_name or user.username
    title = f"额度预警：{user_name} 本月用量已达 {usage_pct}%"
    body = (
        f"用户 {user_name} 本月 token 用量已达到设定的 {threshold}% 阈值。\n"
        f"当前用量: {usage:,} tokens / 上限: {limit:,} tokens"
    )

    # 写入站内通知（发给管理员后面可通过通知列表查看，也发给用户本人）
    db.add(Notification(
        user_id=user_id,
        type="quota_alert",
        title=title,
        body=body,
    ))

    # 邮件告警（如果用户配置了邮箱且 SMTP 可用）
    if user.email:
        try:
            from .mailer import send_email
            await send_email(
                to_addr=user.email,
                subject=title,
                body_text=body,
            )
        except Exception as e:
            logger.warning("quota alert email failed for user %s: %s", user_id, e)

    # 更新 last_alert_at
    quota.last_alert_at = now
    await db.commit()
