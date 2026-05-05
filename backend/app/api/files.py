from __future__ import annotations
import os
import uuid
from pathlib import Path
import aiofiles
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..core.config import settings
from ..core.security import decode_token
from ..db.session import get_db
from ..db.models import UploadedFile, User, Conversation, Agent
from ..deps import current_user
from ..services.file_parser import parse_uploaded_file

router = APIRouter(prefix="/api/files", tags=["files"])

_bearer = HTTPBearer(auto_error=False)


def _to_brief(rec: UploadedFile) -> dict:
    ext = os.path.splitext(rec.name or "")[1].lower()
    return {
        "id": rec.id,
        "name": rec.name,
        "size": rec.size,
        "mime": rec.mime,
        "ext": ext,
        "parse_status": rec.parse_status,
        "parse_engine": rec.parse_engine,
        "parsed_chars": rec.parsed_chars or 0,
        "parse_error": rec.parse_error,
        # PreviewPanel + FileCard expect this. /raw accepts JWT via ?t= for direct
        # browser access (img src / iframe src / a download).
        "download_url": f"/api/files/{rec.id}/raw",
    }


@router.post("/upload")
async def upload(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    conversation_id: int | None = Form(None),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    # ---- Apply Agent's upload policy if conversation provided ----
    # Policy keys (all optional):
    #   allowed_ext: list[str]            — whitelist of extensions
    #   max_size_mb: int                  — hard limit per single file
    #   max_files_per_send: int           — cap on files per chat send (enforced in chat API)
    policy: dict = {}
    if conversation_id:
        c = (await db.execute(select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user.id))).scalar_one_or_none()
        if not c:
            raise HTTPException(404, "会话不存在")
        a = (await db.execute(select(Agent).where(Agent.id == c.agent_id))).scalar_one()
        policy = a.upload_policy_json or {}
        # Extension check
        allowed = policy.get("allowed_ext")
        if allowed:
            ext = os.path.splitext(file.filename or "")[1].lower().lstrip(".")
            if ext not in [e.lower().lstrip(".") for e in allowed]:
                raise HTTPException(400, f"不允许的文件类型: {ext}")

    # Effective size limit = min(global cap, agent cap)
    global_cap = settings.MAX_UPLOAD_MB
    agent_cap = int(policy.get("max_size_mb") or 0)
    effective_mb = min(global_cap, agent_cap) if agent_cap > 0 else global_cap
    max_bytes = effective_mb * 1024 * 1024

    # Per-user isolation directory
    root = Path(settings.UPLOADS_DIR) / str(user.id)
    root.mkdir(parents=True, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1]
    saved_name = f"{uuid.uuid4().hex}{ext}"
    saved_path = root / saved_name

    size = 0
    async with aiofiles.open(saved_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                await f.close()
                saved_path.unlink(missing_ok=True)
                raise HTTPException(400, f"文件超过 {effective_mb}MB 限制")
            await f.write(chunk)

    rec = UploadedFile(
        user_id=user.id, conversation_id=conversation_id,
        name=file.filename or saved_name, path=str(saved_path),
        size=size, mime=file.content_type or "application/octet-stream",
        parse_status="parsing",
    )
    db.add(rec); await db.commit(); await db.refresh(rec)

    # Async parse in background
    background.add_task(parse_uploaded_file, rec.id)

    return _to_brief(rec)


@router.get("/{file_id}")
async def get_file(
    file_id: int,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    rec = (await db.execute(select(UploadedFile).where(UploadedFile.id == file_id))).scalar_one_or_none()
    if not rec or rec.user_id != user.id:
        raise HTTPException(404, "文件不存在")
    return _to_brief(rec)


@router.post("/{file_id}/reparse")
async def reparse_file(
    file_id: int,
    background: BackgroundTasks,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    rec = (await db.execute(select(UploadedFile).where(UploadedFile.id == file_id))).scalar_one_or_none()
    if not rec or rec.user_id != user.id:
        raise HTTPException(404, "文件不存在")
    rec.parse_status = "parsing"
    rec.parse_error = None
    await db.commit(); await db.refresh(rec)
    background.add_task(parse_uploaded_file, rec.id)
    return _to_brief(rec)


@router.delete("/{file_id}")
async def delete_file(
    file_id: int,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an uploaded file (DB row + on-disk file)."""
    rec = (await db.execute(select(UploadedFile).where(UploadedFile.id == file_id))).scalar_one_or_none()
    if not rec or rec.user_id != user.id:
        raise HTTPException(404, "文件不存在")
    try:
        Path(rec.path).unlink(missing_ok=True)
    except OSError:
        pass
    await db.delete(rec); await db.commit()
    return {"ok": True}


async def _resolve_caller_dual(
    db: AsyncSession,
    bearer_cred: HTTPAuthorizationCredentials | None,
    query_token: str | None,
) -> User:
    """Auth via Authorization header OR ?t= query param (for browser direct GET)."""
    raw = bearer_cred.credentials if bearer_cred else query_token
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


@router.get("/{file_id}/raw")
async def serve_raw(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    bearer: HTTPAuthorizationCredentials | None = Depends(_bearer),
    t: str | None = Query(default=None),
):
    """Stream the original uploaded file. Authn via Bearer header OR ?t=<jwt>."""
    user = await _resolve_caller_dual(db, bearer, t)
    rec = (await db.execute(select(UploadedFile).where(UploadedFile.id == file_id))).scalar_one_or_none()
    if not rec or rec.user_id != user.id:
        raise HTTPException(404, "文件不存在")
    p = Path(rec.path)
    if not p.exists():
        raise HTTPException(404, "源文件已丢失")
    return FileResponse(path=str(p), filename=rec.name, media_type=rec.mime or "application/octet-stream")
