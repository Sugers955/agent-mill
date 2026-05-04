"""Token-based file download service.

Files are served via short-lived opaque tokens. The real filesystem path is never
exposed to the client. Each fetch validates:
1. Token exists, not expired, not over max_downloads
2. Resolved real path stays within configured allowed roots (no path traversal)
3. Caller's user_id matches the owner stored at registration time
"""
from __future__ import annotations
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from ..core.config import settings
from ..db.models import DownloadToken


def _allowed_roots() -> list[Path]:
    roots = [
        Path(settings.UPLOADS_DIR).resolve(),
        Path(settings.STORAGE_ROOT).resolve() / "outputs",
    ]
    return [r for r in roots if r.exists()]


async def register_file(
    db: AsyncSession,
    file_path: str | Path,
    file_name: str,
    user_id: int | None,
    *,
    mime: str = "application/octet-stream",
    ttl_hours: int = 24,
    max_downloads: int = 0,
) -> DownloadToken:
    """Generate a download token for a file. Validates path is under allowed roots."""
    real = Path(file_path).resolve()
    if not real.exists() or not real.is_file():
        raise FileNotFoundError(f"file not found: {file_path}")
    if not any(str(real).startswith(str(root)) for root in _allowed_roots()):
        raise PermissionError(f"file not in allowed roots: {real}")

    tok = DownloadToken(
        token=secrets.token_urlsafe(32),
        user_id=user_id,
        file_path=str(real),
        file_name=file_name or real.name,
        mime=mime,
        size=real.stat().st_size,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=ttl_hours),
        max_downloads=max_downloads,
    )
    db.add(tok)
    await db.flush()
    return tok


async def resolve_token(
    db: AsyncSession, token: str, requesting_user_id: int | None,
) -> DownloadToken:
    """Validate a download token. Raises ValueError on any failure."""
    row = (await db.execute(select(DownloadToken).where(DownloadToken.token == token))).scalar_one_or_none()
    if not row:
        raise ValueError("token_not_found")
    if row.expires_at < datetime.now(timezone.utc):
        raise ValueError("expired")
    if row.user_id is not None and row.user_id != requesting_user_id:
        raise ValueError("forbidden")
    if row.max_downloads and row.download_count >= row.max_downloads:
        raise ValueError("download_limit_reached")
    real = Path(row.file_path).resolve()
    if not any(str(real).startswith(str(root)) for root in _allowed_roots()):
        raise ValueError("path_escape")
    if not real.exists():
        raise ValueError("file_missing")
    return row


async def cleanup_expired(db: AsyncSession) -> int:
    """Delete expired token rows (call periodically). Returns number deleted."""
    now = datetime.now(timezone.utc)
    result = await db.execute(delete(DownloadToken).where(DownloadToken.expires_at < now))
    await db.commit()
    return result.rowcount or 0
