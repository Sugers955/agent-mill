from __future__ import annotations
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..core.config import settings
from ..db.session import get_db
from ..db.models import User, AuditLog
from ..core.security import decode_token
from ..services.downloads import resolve_token, register_file

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


@router.post("/refresh")
async def refresh_token(
    request: Request,
    output_path: str = Query(..., description="Stable path under STORAGE_ROOT/outputs (e.g. '5/abcd1234-foo.html')"),
    db: AsyncSession = Depends(get_db),
    bearer: HTTPAuthorizationCredentials | None = Depends(_bearer),
):
    """Mint a fresh download token for an existing output file (when the previous one expired).

    The caller must be the file owner (path starts with `<user_id>/`). This is the
    only safe lookup we have without a separate output-files table.
    """
    user = await _resolve_caller(request, db, bearer, None)

    # path must be relative; resolve under outputs root and verify containment
    rel = (output_path or "").strip().lstrip("/")
    if not rel or ".." in rel.split("/"):
        raise HTTPException(400, "invalid output_path")

    outputs_root = (Path(settings.STORAGE_ROOT) / "outputs").resolve()
    target = (outputs_root / rel).resolve()
    try:
        target.relative_to(outputs_root)
    except ValueError:
        raise HTTPException(400, "path_escape")
    if not target.exists() or not target.is_file():
        raise HTTPException(404, "file_missing")

    # Ownership: outputs are stored under <user_id>/<uuid>-<name>.
    # Admins/operators may refresh tokens for any file (e.g. for shared review).
    parts = rel.split("/", 1)
    owner_seg = parts[0] if parts else ""
    if user.role.code not in ("admin", "operator"):
        if owner_seg != str(user.id):
            raise HTTPException(403, "forbidden")
    try:
        owner_id = int(owner_seg) if owner_seg.isdigit() else user.id
    except ValueError:
        owner_id = user.id

    import mimetypes as _mt
    mime = _mt.guess_type(target.name)[0] or "application/octet-stream"
    tok = await register_file(
        db, file_path=str(target), file_name=target.name,
        user_id=owner_id, mime=mime,
    )
    await db.commit()
    return {"download_url": f"/api/downloads/{tok.token}", "name": target.name, "size": tok.size, "mime": mime}
