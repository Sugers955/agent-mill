from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ...db.session import get_db
from ...db.models import User, Role
from ...deps import require_admin
from ...core.security import hash_password
from ...schemas import UserOut, UserCreate, UserUpdate, RoleOut
from ...services.audit import audit

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/roles", response_model=list[RoleOut])
async def list_roles(db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    rows = (await db.execute(select(Role).order_by(Role.id))).scalars().all()
    return rows


@router.get("/users", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    rows = (await db.execute(select(User).order_by(User.id))).scalars().all()
    return rows


@router.post("/users", response_model=UserOut)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db),
                       actor: User = Depends(require_admin)):
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
    await db.flush()
    await audit(db, actor.id, "user.create", target_type="user", target_id=u.id,
                detail={"username": u.username, "role_id": u.role_id})
    await db.commit()
    await db.refresh(u)
    return u


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(user_id: int, payload: UserUpdate, db: AsyncSession = Depends(get_db),
                       actor: User = Depends(require_admin)):
    u = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not u:
        raise HTTPException(404, "用户不存在")
    changes: dict = {}
    if payload.display_name is not None:
        changes["display_name"] = [u.display_name, payload.display_name]
        u.display_name = payload.display_name
    if payload.role_id is not None:
        changes["role_id"] = [u.role_id, payload.role_id]
        u.role_id = payload.role_id
    if payload.status is not None:
        changes["status"] = [u.status, payload.status]
        u.status = payload.status
    if payload.password:
        u.password_hash = hash_password(payload.password)
        changes["password"] = "rotated"
    await audit(db, actor.id, "user.update", target_type="user", target_id=u.id, detail=changes)
    await db.commit()
    await db.refresh(u)
    return u


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db),
                       actor: User = Depends(require_admin)):
    u = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not u:
        raise HTTPException(404, "用户不存在")
    await audit(db, actor.id, "user.delete", target_type="user", target_id=u.id,
                detail={"username": u.username})
    await db.delete(u)
    await db.commit()
    return {"ok": True}
