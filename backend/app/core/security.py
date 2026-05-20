from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any
import jwt
import bcrypt
from .config import settings


def hash_password(plain: str) -> str:
    # bcrypt has a 72-byte input limit; truncate defensively
    return bcrypt.hashpw(plain.encode("utf-8")[:72], bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except Exception:
        return False


def _encode(payload: dict[str, Any], minutes: int | None = None, days: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    if minutes is not None:
        exp = now + timedelta(minutes=minutes)
    elif days is not None:
        exp = now + timedelta(days=days)
    else:
        exp = now + timedelta(minutes=60)
    payload = {**payload, "iat": int(now.timestamp()), "exp": int(exp.timestamp())}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALG)


def create_access_token(user_id: int, role_code: str) -> str:
    return _encode({"sub": str(user_id), "role": role_code, "type": "access"},
                   minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)


def create_refresh_token(user_id: int) -> str:
    return _encode({"sub": str(user_id), "type": "refresh"},
                   days=settings.REFRESH_TOKEN_EXPIRE_DAYS)


def create_file_token(file_id: int, user_id: int, minutes: int = 30) -> str:
    """Short-lived token scoped to a single uploaded file.

    Handed to external tools (MCP servers) so they can pull raw bytes via
    /api/files/{id}/raw?t=... without holding a full access token.
    """
    return _encode(
        {"sub": str(user_id), "type": "file", "file_id": int(file_id)},
        minutes=minutes,
    )


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
