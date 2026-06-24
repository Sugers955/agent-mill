from __future__ import annotations
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .core.security import decode_token
from .db.session import get_db
from .db.models import User

bearer = HTTPBearer(auto_error=False)


async def current_user(
    cred: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing token")
    try:
        payload = decode_token(cred.credentials)
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "wrong token type")
    user_id = int(payload.get("sub", 0))
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user or user.status != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found or disabled")
    return user


def require_role(*allowed: str):
    async def _dep(user: Annotated[User, Depends(current_user)]) -> User:
        if user.role.code not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden")
        return user
    return _dep


require_admin = require_role("admin")
require_admin_or_operator = require_role("admin", "operator")
