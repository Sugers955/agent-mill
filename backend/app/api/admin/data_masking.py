"""数据脱敏配置 API — 管理敏感信息展示规则。"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ...db.session import get_db
from ...db.models import User, SystemConfig
from ...deps import require_admin
from ...core.crypto import mask_email, mask_phone, mask_id_card
from pydantic import BaseModel

router = APIRouter(prefix="/api/admin/settings", tags=["admin"])


class MaskingConfig(BaseModel):
    """数据脱敏配置。"""
    mask_email: bool = True
    mask_phone: bool = True
    mask_id_card: bool = False
    mask_log_errors: bool = True


async def _get_masking_config(db: AsyncSession) -> dict:
    """从数据库读取脱敏配置。"""
    config = (await db.execute(
        select(SystemConfig).where(SystemConfig.key == "data_masking")
    )).scalar_one_or_none()

    if config and config.value:
        return config.value
    return {"mask_email": True, "mask_phone": True, "mask_id_card": False, "mask_log_errors": True}


async def _save_masking_config(db: AsyncSession, config: dict):
    """保存脱敏配置到数据库。"""
    existing = (await db.execute(
        select(SystemConfig).where(SystemConfig.key == "data_masking")
    )).scalar_one_or_none()

    if existing:
        existing.value = config
    else:
        db.add(SystemConfig(key="data_masking", value=config))

    await db.commit()


@router.get("/data-masking")
async def get_masking_config(
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """获取当前脱敏配置。"""
    return await _get_masking_config(db)


@router.put("/data-masking")
async def update_masking_config(
    payload: MaskingConfig,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """更新脱敏配置。"""
    await _save_masking_config(db, payload.model_dump())
    return {"ok": True}


def maybe_mask_email(email: str | None, config: dict | None = None) -> str | None:
    """根据配置脱敏邮箱。"""
    if not email:
        return email
    if config and not config.get("mask_email", True):
        return email
    return mask_email(email)
