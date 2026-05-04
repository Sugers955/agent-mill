from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..db.session import get_db
from ..db.models import User, AuditLog
from ..core.security import decode_token
from ..services.downloads import resolve_token

router = APIRouter(prefix="/api/downloads", tags=["downloads"])

_bearer = HTTPBearer(auto_error=False)


async def _resolve_caller(
    request: Request,
    db: AsyncSession,
    bearer_cred: HTTPAuthorizationCredentials | None,
    query_token: str | None,
) -> User:
    """Accept user auth from EITHER an Authorization header OR a `?t=<jwt>` query param.

    Browser <a download> and direct popups can't set custom headers, so we expose
    the same JWT via a short-lived query parameter for the download path only.
    """
    raw: str | None = None
    if bearer_cred is not None:
        raw = bearer_cred.credentials
    elif query_token:
        raw = query_token
    if not raw:
        raise HTTPException(401, "missing token")
    try:
        payload = decode_token(raw)
    except Exception:
        raise HTTPException(401, "invalid token")
    if payload.get("type") != "access":
        raise HTTPException(401, "wrong token type")
    user_id = int(payload.get("sub", 0))
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user or user.status != "active":
        raise HTTPException(401, "user not found or disabled")
    return user


@router.get("/{token}")
async def download(
    token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    bearer: HTTPAuthorizationCredentials | None = Depends(_bearer),
    t: str | None = Query(default=None, description="Auth token via query (for direct browser GET)"),
):
    user = await _resolve_caller(request, db, bearer, t)
    try:
        row = await resolve_token(db, token, user.id)
    except ValueError as e:
        code = {"token_not_found": 404, "expired": 410, "forbidden": 403,
                "download_limit_reached": 410, "path_escape": 400, "file_missing": 404}.get(str(e), 400)
        raise HTTPException(code, str(e))
    row.download_count += 1
    db.add(AuditLog(
        user_id=user.id, action="download",
        target_type="file", target_id=token[:16],
        detail_json={"name": row.file_name, "size": row.size},
    ))
    await db.commit()
    return FileResponse(path=row.file_path, filename=row.file_name, media_type=row.mime)
