from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..db.session import get_db
from ..db.models import User
from ..core.security import verify_password, create_access_token, create_refresh_token, decode_token
from ..schemas import LoginIn, TokenOut, RefreshIn, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
async def login(payload: LoginIn, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.username == payload.username))).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误")
    if user.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账号已停用")
    return TokenOut(
        access_token=create_access_token(user.id, user.role.code),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenOut)
async def refresh(payload: RefreshIn, db: AsyncSession = Depends(get_db)):
    try:
        data = decode_token(payload.refresh_token)
        if data.get("type") != "refresh":
            raise ValueError()
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid refresh")
    user = (await db.execute(select(User).where(User.id == int(data["sub"])))).scalar_one_or_none()
    if not user or user.status != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found")
    return TokenOut(
        access_token=create_access_token(user.id, user.role.code),
        refresh_token=create_refresh_token(user.id),
    )


from ..deps import current_user


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(current_user)):
    return user
