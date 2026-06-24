from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from ...db.session import get_db
from ...db.models import PackApproval, PackRun, User
from ...deps import require_admin_or_operator
from ...schemas import PackApprovalOut, PackApprovalDecision
from ...services.audit import audit
from ...runtime.pack_engine import PackEngine

router = APIRouter(prefix="/api/admin/approvals", tags=["admin-approvals"])


@router.get("", response_model=list[PackApprovalOut])
async def list_approvals(
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db), _=Depends(require_admin_or_operator),
):
    stmt = select(PackApproval).order_by(desc(PackApproval.id)).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(PackApproval.status == status)
    return (await db.execute(stmt)).scalars().all()


async def _resume_pack_run(run_id: str, decision: str, reason: str | None, approver_id: int) -> None:
    """Background task: drive PackEngine.resume() to completion."""
    try:
        engine = PackEngine()
        async for _ev in engine.resume(run_id, approval_decision=decision,
                                        approval_reason=reason, approver_id=approver_id):
            pass  # progress is persisted on each step; no SSE here
    except Exception as e:  # noqa: BLE001
        # Persist failure on the run row
        from ...db.session import SessionLocal
        async with SessionLocal() as db:
            run = (await db.execute(select(PackRun).where(PackRun.run_id == run_id))).scalar_one_or_none()
            if run:
                run.status = "failed"
                run.error = f"resume failed: {e}"
                await db.commit()


@router.post("/{aid}/decision")
async def decide_approval(
    aid: int,
    payload: PackApprovalDecision,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_admin_or_operator),
):
    a = (await db.execute(select(PackApproval).where(PackApproval.id == aid))).scalar_one_or_none()
    if not a:
        raise HTTPException(404, "审批不存在")
    if a.status != "pending":
        raise HTTPException(400, f"审批当前状态为 {a.status},不能重复处理")
    a.status = payload.decision
    a.decision_reason = payload.reason
    a.decided_by = actor.id
    a.decided_at = datetime.now(timezone.utc)
    run = (await db.execute(select(PackRun).where(PackRun.run_id == a.run_id))).scalar_one_or_none()
    if run and run.status == "waiting_approval":
        run.status = "running"  # engine flips to success/failed/etc as it resumes
    await audit(db, actor.id, f"pack_approval.{payload.decision}", target_type="pack_approval", target_id=a.id,
                detail={"run_id": a.run_id, "reason": payload.reason})
    await db.commit()

    # Kick off resume in background (don't block the HTTP response)
    asyncio.create_task(_resume_pack_run(a.run_id, payload.decision, payload.reason, actor.id))
    return {"ok": True, "status": a.status}
