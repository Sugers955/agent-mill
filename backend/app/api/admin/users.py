from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from ...db.session import get_db
from ...db.models import User, Role, Department
from ...deps import require_admin
from ...core.security import hash_password
from ...schemas import (
    UserOut, UserCreate, UserUpdate, UserPage,
    RoleOut, RoleIn, RoleUpdate,
)
from ...services.audit import audit

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ---------- Roles ----------
PROTECTED_ROLE_CODES = {"admin", "operator", "user"}


@router.get("/roles", response_model=list[RoleOut])
async def list_roles(db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    rows = (await db.execute(select(Role).order_by(Role.id))).scalars().all()
    return rows


@router.post("/roles", response_model=RoleOut)
async def create_role(payload: RoleIn, db: AsyncSession = Depends(get_db),
                      actor: User = Depends(require_admin)):
    if (await db.execute(select(Role).where(Role.code == payload.code))).scalar_one_or_none():
        raise HTTPException(400, "code 已存在")
    r = Role(**payload.model_dump())
    db.add(r); await db.flush()
    await audit(db, actor.id, "role.create", target_type="role", target_id=r.id)
    await db.commit(); await db.refresh(r)
    return r


@router.patch("/roles/{rid}", response_model=RoleOut)
async def update_role(rid: int, payload: RoleUpdate, db: AsyncSession = Depends(get_db),
                       actor: User = Depends(require_admin)):
    r = (await db.execute(select(Role).where(Role.id == rid))).scalar_one_or_none()
    if not r:
        raise HTTPException(404, "角色不存在")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(r, k, v)
    await audit(db, actor.id, "role.update", target_type="role", target_id=r.id, detail=data)
    await db.commit(); await db.refresh(r)
    return r


@router.delete("/roles/{rid}")
async def delete_role(rid: int, db: AsyncSession = Depends(get_db),
                       actor: User = Depends(require_admin)):
    r = (await db.execute(select(Role).where(Role.id == rid))).scalar_one_or_none()
    if not r:
        raise HTTPException(404, "角色不存在")
    if r.code in PROTECTED_ROLE_CODES:
        raise HTTPException(400, f"内置角色 {r.code} 不可删除")
    cnt = (await db.execute(select(func.count(User.id)).where(User.role_id == rid))).scalar_one()
    if cnt:
        raise HTTPException(400, f"该角色下还有 {cnt} 个用户,请先迁移")
    await audit(db, actor.id, "role.delete", target_type="role", target_id=r.id, detail={"code": r.code})
    await db.delete(r); await db.commit()
    return {"ok": True}


# ---------- Users ----------
@router.get("/users", response_model=UserPage)
async def list_users(
    q: str | None = Query(None),
    role_id: int | None = Query(None),
    department_id: int | None = Query(None),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db), _=Depends(require_admin),
):
    filters = []
    if q:
        like = f"%{q.strip()}%"
        filters.append(or_(User.username.ilike(like), User.display_name.ilike(like)))
    if role_id is not None:
        filters.append(User.role_id == role_id)
    if department_id is not None:
        filters.append(User.department_id == department_id)

    total_q = select(func.count(User.id))
    if filters:
        total_q = total_q.where(*filters)
    total = (await db.execute(total_q)).scalar_one()

    stmt = select(User).order_by(User.id)
    if filters:
        stmt = stmt.where(*filters)
    stmt = stmt.limit(limit).offset(offset)
    rows = (await db.execute(stmt)).scalars().all()
    return UserPage(items=[UserOut.model_validate(r, from_attributes=True) for r in rows], total=total)


@router.post("/users", response_model=UserOut)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db),
                       actor: User = Depends(require_admin)):
    if (await db.execute(select(User).where(User.username == payload.username))).scalar_one_or_none():
        raise HTTPException(400, "用户名已存在")
    if not (await db.execute(select(Role).where(Role.id == payload.role_id))).scalar_one_or_none():
        raise HTTPException(400, "角色不存在")
    if payload.department_id is not None:
        if not (await db.execute(select(Department).where(Department.id == payload.department_id))).scalar_one_or_none():
            raise HTTPException(400, "部门不存在")
    u = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        role_id=payload.role_id,
        department_id=payload.department_id,
    )
    db.add(u)
    await db.flush()
    await audit(db, actor.id, "user.create", target_type="user", target_id=u.id,
                detail={"username": u.username, "role_id": u.role_id, "department_id": u.department_id})
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
    data = payload.model_dump(exclude_unset=True)
    if "display_name" in data:
        changes["display_name"] = [u.display_name, data["display_name"]]
        u.display_name = data["display_name"]
    if "role_id" in data and data["role_id"] is not None:
        if not (await db.execute(select(Role).where(Role.id == data["role_id"]))).scalar_one_or_none():
            raise HTTPException(400, "角色不存在")
        changes["role_id"] = [u.role_id, data["role_id"]]
        u.role_id = data["role_id"]
    if "department_id" in data:
        new_dep = data["department_id"]
        if new_dep is not None:
            if not (await db.execute(select(Department).where(Department.id == new_dep))).scalar_one_or_none():
                raise HTTPException(400, "部门不存在")
        changes["department_id"] = [u.department_id, new_dep]
        u.department_id = new_dep
    if "status" in data and data["status"] is not None:
        changes["status"] = [u.status, data["status"]]
        u.status = data["status"]
    if data.get("password"):
        u.password_hash = hash_password(data["password"])
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
