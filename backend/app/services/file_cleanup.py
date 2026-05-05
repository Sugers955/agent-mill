"""Periodic cleanup of orphan uploaded files.

A file is considered orphan when:
- last_used_at is older than RETENTION_DAYS, AND
- No conversation references its conversation_id (or conversation_id is NULL).

We delete the DB row + the on-disk file. Cleanup runs once per day in-process.
"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select, or_

from ..db.models import UploadedFile
from ..db.session import SessionLocal

logger = logging.getLogger(__name__)

RETENTION_DAYS = 30
RUN_INTERVAL_SEC = 24 * 3600  # daily


async def cleanup_once() -> int:
    """Run a single cleanup pass. Returns number of files removed."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    removed = 0
    async with SessionLocal() as db:
        rows = (await db.execute(
            select(UploadedFile).where(
                or_(UploadedFile.last_used_at.is_(None), UploadedFile.last_used_at < cutoff),
                UploadedFile.created_at < cutoff,
            )
        )).scalars().all()
        for r in rows:
            try:
                Path(r.path).unlink(missing_ok=True)
            except OSError:
                pass
            await db.delete(r)
            removed += 1
        if removed:
            await db.commit()
    if removed:
        logger.info("cleanup: removed %d orphan files", removed)
    return removed


async def cleanup_loop() -> None:
    """Background loop. Sleeps RUN_INTERVAL_SEC between passes."""
    while True:
        try:
            await cleanup_once()
        except Exception as e:  # noqa: BLE001
            logger.exception("cleanup pass failed: %s", e)
        await asyncio.sleep(RUN_INTERVAL_SEC)
