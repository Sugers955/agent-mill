"""Tiny helper for writing AuditLog rows. Use it inside admin handlers."""
from __future__ import annotations
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import AuditLog


async def audit(
    db: AsyncSession,
    user_id: int | None,
    action: str,
    *,
    target_type: str | None = None,
    target_id: str | int | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Record a single audit entry. Caller is responsible for committing."""
    db.add(AuditLog(
        user_id=user_id,
        action=action,
        resource_type=target_type,
        resource_id=str(target_id) if target_id is not None else None,
        detail_json=detail,
    ))
