"""SMTP-based email sender for task notifications.

Reads SMTP settings from app config. Returns a status dict so callers can
record per-channel send results without raising on transient failures.
"""
from __future__ import annotations
import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any

from ..core.config import settings

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    return bool(settings.SMTP_HOST and (settings.SMTP_FROM or settings.SMTP_USER))


def _send_sync(to_addr: str, subject: str, body_text: str, body_html: str | None) -> dict[str, Any]:
    if not is_configured():
        return {"ok": False, "error": "SMTP 未配置"}
    if not to_addr:
        return {"ok": False, "error": "收件人为空"}

    sender = settings.SMTP_FROM or settings.SMTP_USER
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body_text or "")
    if body_html:
        msg.add_alternative(body_html, subtype="html")

    try:
        if settings.SMTP_USE_SSL:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=ctx, timeout=30) as s:
                if settings.SMTP_USER:
                    s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                s.send_message(msg)
        else:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as s:
                s.ehlo()
                if settings.SMTP_USE_TLS:
                    s.starttls(context=ssl.create_default_context())
                    s.ehlo()
                if settings.SMTP_USER:
                    s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                s.send_message(msg)
        return {"ok": True}
    except Exception as e:
        logger.warning("SMTP send failed: %s", e)
        return {"ok": False, "error": str(e)[:300]}


async def send_email(to_addr: str, subject: str, body_text: str, body_html: str | None = None) -> dict[str, Any]:
    """Async wrapper that runs the blocking SMTP call in a thread."""
    return await asyncio.to_thread(_send_sync, to_addr, subject, body_text, body_html)
