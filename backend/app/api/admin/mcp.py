from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ...db.session import get_db
from ...db.models import MCPConnector
from ...deps import require_admin_or_operator
from ...schemas import MCPIn, MCPOut

router = APIRouter(prefix="/api/admin/mcp", tags=["admin-mcp"],
                   dependencies=[Depends(require_admin_or_operator)])


@router.get("", response_model=list[MCPOut])
async def list_mcp(db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(MCPConnector).order_by(MCPConnector.id))).scalars().all()


@router.post("", response_model=MCPOut)
async def create_mcp(payload: MCPIn, db: AsyncSession = Depends(get_db)):
    if (await db.execute(select(MCPConnector).where(MCPConnector.name == payload.name))).scalar_one_or_none():
        raise HTTPException(400, "名称已存在")
    m = MCPConnector(**payload.model_dump())
    db.add(m); await db.commit(); await db.refresh(m)
    return m


@router.patch("/{mid}", response_model=MCPOut)
async def update_mcp(mid: int, payload: MCPIn, db: AsyncSession = Depends(get_db)):
    m = (await db.execute(select(MCPConnector).where(MCPConnector.id == mid))).scalar_one_or_none()
    if not m:
        raise HTTPException(404, "不存在")
    for k, v in payload.model_dump().items():
        setattr(m, k, v)
    await db.commit(); await db.refresh(m)
    return m


@router.delete("/{mid}")
async def delete_mcp(mid: int, db: AsyncSession = Depends(get_db)):
    m = (await db.execute(select(MCPConnector).where(MCPConnector.id == mid))).scalar_one_or_none()
    if not m:
        raise HTTPException(404, "不存在")
    await db.delete(m); await db.commit()
    return {"ok": True}


@router.post("/{mid}/ping")
async def ping_mcp(mid: int, db: AsyncSession = Depends(get_db)):
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
async def get_mcp_tools(mid: int, db: AsyncSession = Depends(get_db)):
    m = (await db.execute(select(MCPConnector).where(MCPConnector.id == mid))).scalar_one_or_none()
    if not m:
        raise HTTPException(404, "不存在")
    try:
        from ...runtime.mcp_manager import list_mcp_tools
        return await list_mcp_tools(m, timeout=20.0)
    except Exception as e:
        raise HTTPException(400, f"连接失败: {e}")
