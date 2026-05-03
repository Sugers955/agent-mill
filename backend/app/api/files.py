from __future__ import annotations
import os
import uuid
from pathlib import Path
import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..core.config import settings
from ..db.session import get_db
from ..db.models import UploadedFile, User, Conversation, Agent
from ..deps import current_user

router = APIRouter(prefix="/api/files", tags=["files"])


@router.post("/upload")
async def upload(
    file: UploadFile = File(...),
    conversation_id: int | None = Form(None),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    # validate against agent upload policy if conversation provided
    if conversation_id:
        c = (await db.execute(select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user.id))).scalar_one_or_none()
        if not c:
            raise HTTPException(404, "会话不存在")
        a = (await db.execute(select(Agent).where(Agent.id == c.agent_id))).scalar_one()
        policy = a.upload_policy_json or {}
        allowed = policy.get("allowed_ext")
        if allowed:
            ext = os.path.splitext(file.filename or "")[1].lower().lstrip(".")
            if ext not in [e.lower().lstrip(".") for e in allowed]:
                raise HTTPException(400, f"不允许的文件类型: {ext}")
    # size limit
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    root = Path(settings.UPLOADS_DIR)
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
                raise HTTPException(400, f"文件超过 {settings.MAX_UPLOAD_MB}MB 限制")
            await f.write(chunk)
    rec = UploadedFile(
        user_id=user.id, conversation_id=conversation_id,
        name=file.filename or saved_name, path=str(saved_path),
        size=size, mime=file.content_type or "application/octet-stream",
    )
    db.add(rec); await db.commit(); await db.refresh(rec)
    return {"id": rec.id, "name": rec.name, "size": rec.size, "mime": rec.mime}
