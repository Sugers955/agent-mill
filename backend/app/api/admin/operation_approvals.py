"""通用操作审批 API — 高危操作需审批。"""
from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ...db.session import get_db
from ...db.models import User, OperationApproval, Notification
from ...deps import require_admin
from pydantic import BaseModel

router = APIRouter(prefix="/api/admin/operation-approvals", tags=["admin"])


class ApprovalCreate(BaseModel):
    operation_type: str
    target_id: int | None = None
    target_name: str | None = None
    reason: str | None = None
    detail_json: dict | None = None


class ApprovalDecision(BaseModel):
    decision: str  # approved / rejected
    reason: str | None = None


@router.get("")
async def list_approvals(
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """获取操作审批列表。"""
    conditions = [True]
    if status:
        conditions.append(OperationApproval.status == status)
    
    total = len((await db.execute(select(OperationApproval).where(*conditions))).scalars().all())
    
    items = (await db.execute(
        select(OperationApproval).where(*conditions)
        .order_by(OperationApproval.id.desc())
        .limit(limit).offset(offset)
    )).scalars().all()
    
    return {"items": items, "total": total}


@router.post("")
async def create_approval(
    payload: ApprovalCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """创建操作审批请求。"""
    approval = OperationApproval(
        operation_type=payload.operation_type,
        target_id=payload.target_id,
        target_name=payload.target_name,
        requested_by=user.id,
        reason=payload.reason,
        detail_json=payload.detail_json,
        status="pending",
    )
    db.add(approval)
    await db.commit()
    await db.refresh(approval)
    
    # 通知其他管理员
    admins = (await db.execute(
        select(User).where(User.id != user.id)
    )).scalars().all()
    for admin in admins:
        notif = Notification(
            user_id=admin.id,
            title=f"审批请求: {payload.operation_type}",
            body=f"{user.username} 请求 {payload.operation_type}: {payload.target_name or payload.target_id or ''}",
            type="approval",
        )
        db.add(notif)
    await db.commit()
    
    return approval


@router.post("/{approval_id}/decide")
async def decide_approval(
    approval_id: int,
    payload: ApprovalDecision,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """审批操作请求（通过/拒绝）。"""
    approval = (await db.execute(
        select(OperationApproval).where(OperationApproval.id == approval_id)
    )).scalar_one_or_none()
    if not approval:
        raise HTTPException(404, "审批不存在")
    if approval.status != "pending":
        raise HTTPException(400, f"审批当前状态为 {approval.status}，不能重复处理")
    if approval.requested_by == user.id:
        raise HTTPException(400, "不能审批自己的请求")
    
    approval.status = payload.decision
    approval.decided_by = user.id
    approval.decided_at = datetime.utcnow()
    approval.decision_reason = payload.reason
    await db.commit()
    
    return {"ok": True, "status": approval.status}


async def create_approval_internal(
    db: AsyncSession,
    user: User,
    operation_type: str,
    target_id: int | None = None,
    target_name: str | None = None,
    reason: str | None = None,
    detail_json: dict | None = None,
) -> OperationApproval:
    """内部辅助：创建审批请求（供其他端点调用）。"""
    approval = OperationApproval(
        operation_type=operation_type,
        target_id=target_id,
        target_name=target_name,
        requested_by=user.id,
        reason=reason,
        detail_json=detail_json,
        status="pending",
    )
    db.add(approval)
    await db.commit()
    await db.refresh(approval)
    
    # 通知其他管理员
    admins = (await db.execute(
        select(User).where(User.id != user.id)
    )).scalars().all()
    for admin in admins:
        notif = Notification(
            user_id=admin.id,
            title=f"审批请求: {operation_type}",
            body=f"{user.username} 请求 {operation_type}: {target_name or target_id or ''}",
            type="approval",
        )
        db.add(notif)
    await db.commit()
    
    return approval
