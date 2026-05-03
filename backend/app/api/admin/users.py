from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ...db.session import get_db
from ...db.models import User, Role
from ...deps import require_admin
from ...core.security import hash_password
from ...schemas import UserOut, UserCreate, UserUpdate, RoleOut

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/roles", response_model=list[RoleOut])
async def list_roles(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Role).order_by(Role.id))).scalars().all()
    return rows


@router.get("/users", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(User).order_by(User.id))).scalars().all()
    return rows


@router.post("/users", response_model=UserOut)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    if (await db.execute(select(User).where(User.username == payload.username))).scalar_one_or_none():
        raise HTTPException(400, "用户名已存在")
    if not (await db.execute(select(Role).where(Role.id == payload.role_id))).scalar_one_or_none():
        raise HTTPException(400, "角色不存在")
    u = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        role_id=payload.role_id,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(user_id: int, payload: UserUpdate, db: AsyncSession = Depends(get_db)):
    u = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not u:
        raise HTTPException(404, "用户不存在")
    if payload.display_name is not None:
        u.display_name = payload.display_name
    if payload.role_id is not None:
        u.role_id = payload.role_id
    if payload.status is not None:
        u.status = payload.status
    if payload.password:
        u.password_hash = hash_password(payload.password)
    await db.commit()
    await db.refresh(u)
    return u


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db)):
    u = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not u:
        raise HTTPException(404, "用户不存在")
    await db.delete(u)
    await db.commit()
    return {"ok": True}
