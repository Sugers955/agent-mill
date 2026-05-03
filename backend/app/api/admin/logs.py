from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from ...db.session import get_db
from ...db.models import CallLog, AuditLog, User, Agent, Model
from ...deps import require_admin_or_operator
from ...schemas import CallLogOut, AuditLogOut, CallLogPage, AuditLogPage

router = APIRouter(prefix="/api/admin/logs", tags=["admin-logs"],
                   dependencies=[Depends(require_admin_or_operator)])


@router.get("/calls", response_model=CallLogPage)
async def list_call_logs(
    limit: int = Query(20, ge=1, le=500), offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    total = (await db.execute(select(func.count(CallLog.id)))).scalar_one()

    user_username = User.username.label("user_username")
    user_display = User.display_name.label("user_display")
    rows = (await db.execute(
        select(
            CallLog,
            user_username,
            user_display,
            Agent.name.label("agent_name"),
            Model.code.label("model_code"),
            Model.model_id.label("model_model_id"),
            Model.provider.label("model_provider"),
        )
        .outerjoin(User, User.id == CallLog.user_id)
        .outerjoin(Agent, Agent.id == CallLog.agent_id)
        .outerjoin(Model, Model.id == CallLog.model_id)
        .order_by(desc(CallLog.id))
        .limit(limit)
        .offset(offset)
    )).all()

    items: list[CallLogOut] = []
    for log, uname, udisp, aname, mcode, mmid, mprov in rows:
        items.append(CallLogOut(
            id=log.id,
            user_id=log.user_id,
            user_name=udisp or uname,
            agent_id=log.agent_id,
            agent_name=aname,
            conversation_id=log.conversation_id,
            model_id=log.model_id,
            model_name=mcode or mmid,
            model_provider=mprov,
            tokens_in=log.tokens_in,
            tokens_out=log.tokens_out,
            latency_ms=log.latency_ms,
            status=log.status,
            error=log.error,
            created_at=log.created_at,
        ))
    return CallLogPage(items=items, total=total)


@router.get("/audit", response_model=AuditLogPage)
async def list_audit_logs(
    limit: int = Query(20, ge=1, le=500), offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    total = (await db.execute(select(func.count(AuditLog.id)))).scalar_one()

    rows = (await db.execute(
        select(
            AuditLog,
            User.username.label("user_username"),
            User.display_name.label("user_display"),
        )
        .outerjoin(User, User.id == AuditLog.user_id)
        .order_by(desc(AuditLog.id))
        .limit(limit)
        .offset(offset)
    )).all()

    items: list[AuditLogOut] = []
    for log, uname, udisp in rows:
        items.append(AuditLogOut(
            id=log.id,
            user_id=log.user_id,
            user_name=udisp or uname,
            action=log.action,
            target_type=log.target_type,
            target_id=log.target_id,
            detail_json=log.detail_json,
            created_at=log.created_at,
        ))
    return AuditLogPage(items=items, total=total)
