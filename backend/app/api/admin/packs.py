from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import yaml

from ...db.session import get_db
from ...db.models import SolutionPack, User
from ...deps import require_admin_or_operator
from ...schemas import SolutionPackIn, SolutionPackOut
from ...services.audit import audit
from ...runtime.pack_engine import PackEngine

router = APIRouter(prefix="/api/admin/packs", tags=["admin-packs"])


def _validate_yaml_text(yaml_text: str) -> dict:
    try:
        spec = yaml.safe_load(yaml_text) or {}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"YAML 解析失败: {e}")
    try:
        PackEngine().validate_pack(spec)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Pack 校验失败: {e}")
    return spec


@router.get("", response_model=list[SolutionPackOut])
async def list_packs(db: AsyncSession = Depends(get_db), _=Depends(require_admin_or_operator)):
    rows = (await db.execute(select(SolutionPack).order_by(SolutionPack.id))).scalars().all()
    return rows


@router.post("", response_model=SolutionPackOut)
async def create_pack(payload: SolutionPackIn, db: AsyncSession = Depends(get_db),
                      actor: User = Depends(require_admin_or_operator)):
    if (await db.execute(select(SolutionPack).where(SolutionPack.code == payload.code))).scalar_one_or_none():
        raise HTTPException(400, "code 已存在")
    spec = _validate_yaml_text(payload.yaml_text)
    p = SolutionPack(
        code=payload.code,
        name=payload.name,
        version=payload.version,
        description=payload.description,
        yaml_text=payload.yaml_text,
        spec_json=spec,
        enabled=payload.enabled,
    )
    db.add(p); await db.flush()
    await audit(db, actor.id, "pack.create", target_type="pack", target_id=p.id,
                detail={"code": p.code, "version": p.version})
    await db.commit(); await db.refresh(p)
    return p


@router.get("/{pid}", response_model=SolutionPackOut)
async def get_pack(pid: int, db: AsyncSession = Depends(get_db), _=Depends(require_admin_or_operator)):
    p = (await db.execute(select(SolutionPack).where(SolutionPack.id == pid))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "不存在")
    return p


@router.patch("/{pid}", response_model=SolutionPackOut)
async def update_pack(pid: int, payload: SolutionPackIn, db: AsyncSession = Depends(get_db),
                      actor: User = Depends(require_admin_or_operator)):
    p = (await db.execute(select(SolutionPack).where(SolutionPack.id == pid))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "不存在")
    spec = _validate_yaml_text(payload.yaml_text)
    p.code = payload.code
    p.name = payload.name
    p.version = payload.version
    p.description = payload.description
    p.yaml_text = payload.yaml_text
    p.spec_json = spec
    p.enabled = payload.enabled
    await audit(db, actor.id, "pack.update", target_type="pack", target_id=p.id,
                detail={"code": p.code, "version": p.version})
    await db.commit(); await db.refresh(p)
    return p


@router.delete("/{pid}")
async def delete_pack(pid: int, db: AsyncSession = Depends(get_db),
                      actor: User = Depends(require_admin_or_operator)):
    p = (await db.execute(select(SolutionPack).where(SolutionPack.id == pid))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "不存在")
    await audit(db, actor.id, "pack.delete", target_type="pack", target_id=p.id,
                detail={"code": p.code})
    await db.delete(p); await db.commit()
    return {"ok": True}
