from __future__ import annotations
import os
import uuid
from pathlib import Path
import aiofiles
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from ...db.session import get_db
from ...db.models import MCPConnector
from ...deps import require_admin_or_operator
from ...services.audit import audit
from ...services.capability_summarizer import summarize_mcp
from ...db.models import User
from ...schemas import MCPIn, MCPOut
from ...core.config import settings

router = APIRouter(prefix="/api/admin/mcp", tags=["admin-mcp"])


@router.get("")
async def list_mcp(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin_or_operator),
):
    total = (await db.execute(select(func.count(MCPConnector.id)))).scalar_one()
    rows = (await db.execute(
        select(MCPConnector).order_by(MCPConnector.id).limit(limit).offset(offset)
    )).scalars().all()
    return {"items": rows, "total": total}


@router.post("", response_model=MCPOut)
async def create_mcp(payload: MCPIn, background_tasks: BackgroundTasks,
                     db: AsyncSession = Depends(get_db),
                     actor: User = Depends(require_admin_or_operator)):
    # Validate MCP config before saving
    from ...runtime.mcp_manager import validate_mcp_config
    error = validate_mcp_config(payload.config_json or {}, payload.transport)
    if error:
        raise HTTPException(400, f"MCP 配置验证失败: {error}")
    if (await db.execute(select(MCPConnector).where(MCPConnector.name == payload.name))).scalar_one_or_none():
        raise HTTPException(400, "名称已存在")
    m = MCPConnector(**payload.model_dump())
    await audit(db, actor.id, "mcp.create", target_type="mcp", target_id=None)
    db.add(m); await db.commit(); await db.refresh(m)
    background_tasks.add_task(summarize_mcp, m.id)
    return m


@router.patch("/{mid}", response_model=MCPOut)
async def update_mcp(mid: int, payload: MCPIn, background_tasks: BackgroundTasks,
                     db: AsyncSession = Depends(get_db),
                     actor: User = Depends(require_admin_or_operator)):
    m = (await db.execute(select(MCPConnector).where(MCPConnector.id == mid))).scalar_one_or_none()
    if not m:
        raise HTTPException(404, "不存在")
    for k, v in payload.model_dump().items():
        setattr(m, k, v)
    await audit(db, actor.id, "mcp.update", target_type="mcp", target_id=m.id)
    await db.commit(); await db.refresh(m)
    background_tasks.add_task(summarize_mcp, m.id)
    return m


@router.delete("/{mid}")
async def delete_mcp(mid: int, db: AsyncSession = Depends(get_db), actor: User = Depends(require_admin_or_operator)):
    m = (await db.execute(select(MCPConnector).where(MCPConnector.id == mid))).scalar_one_or_none()
    if not m:
        raise HTTPException(404, "不存在")
    await audit(db, actor.id, "mcp.delete", target_type="mcp", target_id=m.id)
    await db.delete(m); await db.commit()
    return {"ok": True}


@router.post("/{mid}/icon")
async def upload_mcp_icon(
    mid: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_admin_or_operator),
):
    m = (await db.execute(select(MCPConnector).where(MCPConnector.id == mid))).scalar_one_or_none()
    if not m:
        raise HTTPException(404, "MCP 不存在")

    # Validate file type
    allowed_types = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(400, "只支持 JPG/PNG/GIF/WebP 图片")

    # Validate file size (2MB max)
    max_size = 2 * 1024 * 1024
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(400, "图片大小不能超过 2MB")

    # Save icon
    root = Path(settings.UPLOADS_DIR) / "icons" / "mcp"
    root.mkdir(parents=True, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1].lower() or ".png"
    saved_name = f"{uuid.uuid4().hex}{ext}"
    saved_path = root / saved_name

    async with aiofiles.open(saved_path, "wb") as f:
        await f.write(content)

    # Update mcp icon_url
    icon_url = f"/api/files/icons/mcp/{saved_name}"
    m.icon_url = icon_url
    await audit(db, actor.id, "mcp.update_icon", target_type="mcp", target_id=m.id)
    await db.commit()

    return {"ok": True, "icon_url": icon_url}


@router.post("/{mid}/ping")
async def ping_mcp(mid: int, db: AsyncSession = Depends(get_db), actor: User = Depends(require_admin_or_operator)):
    m = (await db.execute(select(MCPConnector).where(MCPConnector.id == mid))).scalar_one_or_none()
    if not m:
        raise HTTPException(404, "不存在")
    try:
        from ...runtime.mcp_manager import list_mcp_tools
        info = await list_mcp_tools(m, timeout=10.0)
        return {"ok": True, "server": info["server"], "tools_count": len(info["tools"])}
    except Exception as e:
        raise HTTPException(400, f"连接失败: {e}")


@router.get("/{mid}/tools")
async def get_mcp_tools(mid: int, db: AsyncSession = Depends(get_db), _=Depends(require_admin_or_operator)):
    m = (await db.execute(select(MCPConnector).where(MCPConnector.id == mid))).scalar_one_or_none()
    if not m:
        raise HTTPException(404, "不存在")
    try:
        from ...runtime.mcp_manager import list_mcp_tools
        return await list_mcp_tools(m, timeout=20.0)
    except Exception as e:
        raise HTTPException(400, f"连接失败: {e}")


@router.post("/{mid}/resummarize")
async def resummarize_mcp(mid: int, background_tasks: BackgroundTasks,
                          db: AsyncSession = Depends(get_db),
                          actor: User = Depends(require_admin_or_operator)):
    m = (await db.execute(select(MCPConnector).where(MCPConnector.id == mid))).scalar_one_or_none()
    if not m:
        raise HTTPException(404, "不存在")
    background_tasks.add_task(summarize_mcp, m.id)
    await audit(db, actor.id, "mcp.resummarize", target_type="mcp", target_id=m.id)
    await db.commit()
    return {"ok": True, "queued": True}
