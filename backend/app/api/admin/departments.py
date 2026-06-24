from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from ...db.session import get_db
from ...db.models import Department, User
from ...deps import require_admin
from ...services.audit import audit
from ...schemas import (
    DepartmentIn, DepartmentUpdate, DepartmentOut, DepartmentNode,
)

router = APIRouter(prefix="/api/admin/departments", tags=["admin-departments"])


@router.get("")
async def list_departments(
    q: str | None = Query(None),
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    stmt = select(Department).order_by(
        Department.parent_id.isnot(None).desc(),
        Department.parent_id,
        Department.sort,
        Department.id
    )
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Department.name.ilike(like), Department.code.ilike(like)))
    total = (await db.execute(select(func.count(Department.id)))).scalar_one()
    rows = (await db.execute(stmt.limit(limit).offset(offset))).scalars().all()
    return {"items": rows, "total": total}


@router.get("/tree", response_model=list[DepartmentNode])
async def department_tree(
    db: AsyncSession = Depends(get_db), _=Depends(require_admin),
):
    rows = (await db.execute(
        select(Department).order_by(Department.sort, Department.id)
    )).scalars().all()

    counts_q = (await db.execute(
        select(User.department_id, func.count(User.id))
        .where(User.department_id.is_not(None))
        .group_by(User.department_id)
    )).all()
    counts: dict[int, int] = {dep_id: c for dep_id, c in counts_q}

    nodes: dict[int, DepartmentNode] = {
        d.id: DepartmentNode.model_validate(d, from_attributes=True) for d in rows
    }
    for n in nodes.values():
        n.user_count = counts.get(n.id, 0)
        n.children = []

    roots: list[DepartmentNode] = []
    for d in rows:
        node = nodes[d.id]
        if d.parent_id and d.parent_id in nodes:
            nodes[d.parent_id].children.append(node)
        else:
            roots.append(node)
    return roots


def _validate_no_cycle(rows: list[Department], me_id: int, new_parent_id: int | None) -> None:
    """Walk up from new_parent_id and ensure we don't hit me_id."""
    if new_parent_id is None or new_parent_id == me_id:
        if new_parent_id == me_id:
            raise HTTPException(400, "上级部门不能是自己")
        return
    by_id = {r.id: r for r in rows}
    cur: int | None = new_parent_id
    seen: set[int] = set()
    while cur is not None:
        if cur == me_id:
            raise HTTPException(400, "上级部门不能是自己的子部门")
        if cur in seen:
            return  # already cyclic in DB, ignore
        seen.add(cur)
        cur = by_id[cur].parent_id if cur in by_id else None


@router.post("", response_model=DepartmentOut)
async def create_department(
    payload: DepartmentIn, db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_admin),
):
    if (await db.execute(select(Department).where(Department.code == payload.code))).scalar_one_or_none():
        raise HTTPException(400, "code 已存在")
    if payload.parent_id is not None:
        if not (await db.execute(select(Department).where(Department.id == payload.parent_id))).scalar_one_or_none():
            raise HTTPException(400, "上级部门不存在")
    d = Department(**payload.model_dump())
    db.add(d)
    await db.flush()
    await audit(db, actor.id, "department.create", target_type="department", target_id=d.id)
    await db.commit()
    await db.refresh(d)
    return d


@router.patch("/{dep_id}", response_model=DepartmentOut)
async def update_department(
    dep_id: int, payload: DepartmentUpdate,
    db: AsyncSession = Depends(get_db), actor: User = Depends(require_admin),
):
    d = (await db.execute(select(Department).where(Department.id == dep_id))).scalar_one_or_none()
    if not d:
        raise HTTPException(404, "部门不存在")

    data = payload.model_dump(exclude_unset=True)
    if "code" in data and data["code"] != d.code:
        if (await db.execute(select(Department).where(Department.code == data["code"]))).scalar_one_or_none():
            raise HTTPException(400, "code 已存在")
    if "parent_id" in data and data["parent_id"] != d.parent_id:
        rows = (await db.execute(select(Department))).scalars().all()
        _validate_no_cycle(rows, dep_id, data["parent_id"])
        if data["parent_id"] is not None:
            if not (await db.execute(select(Department).where(Department.id == data["parent_id"]))).scalar_one_or_none():
                raise HTTPException(400, "上级部门不存在")
    for k, v in data.items():
        setattr(d, k, v)
    await audit(db, actor.id, "department.update", target_type="department", target_id=d.id, detail=data)
    await db.commit()
    await db.refresh(d)
    return d


@router.delete("/{dep_id}")
async def delete_department(
    dep_id: int, force: bool = False,
    db: AsyncSession = Depends(get_db), actor: User = Depends(require_admin),
):
    d = (await db.execute(select(Department).where(Department.id == dep_id))).scalar_one_or_none()
    if not d:
        raise HTTPException(404, "部门不存在")
    children = (await db.execute(select(func.count(Department.id)).where(Department.parent_id == dep_id))).scalar_one()
    if children:
        raise HTTPException(400, f"该部门下还有 {children} 个子部门,请先迁移或删除")
    user_cnt = (await db.execute(select(func.count(User.id)).where(User.department_id == dep_id))).scalar_one()
    if user_cnt and not force:
        raise HTTPException(400, f"该部门下还有 {user_cnt} 个用户,请先迁移或加 force=true 强制解除关联")
    await audit(db, actor.id, "department.delete", target_type="department", target_id=d.id,
                detail={"name": d.name, "user_count": user_cnt})
    await db.delete(d)
    await db.commit()
    return {"ok": True}
