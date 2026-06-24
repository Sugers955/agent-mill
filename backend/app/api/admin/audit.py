"""审计日志 API — 查询操作记录。"""
from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from ...db.session import get_db
from ...db.models import User
from ...deps import current_user, require_admin

router = APIRouter(prefix="/api/admin/audit", tags=["audit"])


@router.get("/logs", dependencies=[Depends(require_admin)])
async def get_audit_logs(
    user_id: int | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """查询审计日志（管理员用）。"""
    from ...services.audit_service import AuditService
    from ...core.crypto import mask_text

    audit_svc = AuditService(db)
    logs, total = await audit_svc.get_logs(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        limit=limit,
        offset=offset,
    )

    # 对日志中的敏感信息脱敏
    masked_logs = []
    for log in logs:
        log_dict = dict(log)
        # 脱敏 detail_json 中的敏感信息
        if log_dict.get("detail_json") and isinstance(log_dict["detail_json"], dict):
            log_dict["detail_json"] = _mask_log_detail(log_dict["detail_json"])
        masked_logs.append(log_dict)

    return {"items": masked_logs, "total": total}


def _mask_log_detail(detail: dict) -> dict:
    """脱敏审计日志中的敏感信息。"""
    from ...core.crypto import mask_email, mask_phone

    masked = {}
    for key, value in detail.items():
        if isinstance(value, str):
            # 脱敏邮箱
            if "email" in key.lower() or "@" in str(value):
                masked[key] = mask_email(value)
            # 脱敏手机号
            elif "phone" in key.lower() or "mobile" in key.lower():
                masked[key] = mask_phone(value)
            else:
                masked[key] = value
        else:
            masked[key] = value
    return masked


@router.get("/user/{target_user_id}", dependencies=[Depends(require_admin)])
async def get_user_activity(
    target_user_id: int,
    days: int = 30,
    db: AsyncSession = Depends(get_db),
):
    """获取用户活动统计（管理员用）。"""
    from ...services.audit_service import AuditService
    
    audit_svc = AuditService(db)
    stats = await audit_svc.get_user_activity(target_user_id, days)
    
    return stats


@router.get("/my-activity")
async def get_my_activity(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    """获取当前用户的活动统计。"""
    from ...services.audit_service import AuditService
    
    audit_svc = AuditService(db)
    stats = await audit_svc.get_user_activity(user.id, days)
    
    return stats
