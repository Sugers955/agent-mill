"""认证 API — 登录、注册、SSO。"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ...db.session import get_db
from ...db.models import User
from ...deps import require_admin
from pydantic import BaseModel

router = APIRouter(prefix="/api/admin/auth", tags=["auth"])


@router.get("/sso/config")
async def get_sso_config(
    user: User = Depends(require_admin),
):
    """获取 SSO 配置。"""
    from ...auth.sso import SSOService
    svc = SSOService()
    config = svc.get_oidc_config()
    return config or {"client_id": "", "issuer_url": "", "redirect_uri": "", "scopes": []}


@router.get("/sso/authorize")
async def sso_authorize(
    state: str = "",
):
    """生成 SSO 授权 URL。"""
    from ...auth.sso import SSOService
    svc = SSOService()
    url = svc.get_authorization_url(state)
    if not url:
        raise HTTPException(status_code=400, detail="SSO 未配置")
    return {"url": url}


class SSOCallbackRequest(BaseModel):
    """SSO 回调请求。"""
    code: str


@router.post("/sso/callback")
async def sso_callback(
    payload: SSOCallbackRequest,
):
    """处理 SSO 回调。"""
    from ...auth.sso import SSOService
    svc = SSOService()
    result = await svc.handle_callback(payload.code)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
