from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..db.session import get_db
from ..db.models import User
from ..core.security import verify_password, hash_password, create_access_token, create_refresh_token, decode_token
from ..schemas import LoginIn, TokenOut, RefreshIn, UserOut, ChangePasswordIn, EmailUpdateIn

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
async def login(payload: LoginIn, db: AsyncSession = Depends(get_db)):
    """登录（支持本地认证 + LDAP 降级）。"""
    user = (await db.execute(select(User).where(User.username == payload.username))).scalar_one_or_none()
    
    # 本地认证
    if user and verify_password(payload.password, user.password_hash):
        if user.status != "active":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "账号已停用")
        return TokenOut(
            access_token=create_access_token(user.id, user.role.code),
            refresh_token=create_refresh_token(user.id),
        )
    
    # LDAP 认证（本地认证失败时尝试）
    from ..auth.ldap import ldap_backend
    ldap_info = await ldap_backend.authenticate(payload.username, payload.password)
    
    if ldap_info:
        from ..db.models import Role
        from ..core.security import hash_password
        
        if user:
            # 更新已有 LDAP 用户信息
            if ldap_info.get("email"):
                user.email = ldap_info["email"]
            if ldap_info.get("display_name"):
                user.display_name = ldap_info["display_name"]
            user.password_hash = hash_password(payload.password)
            await db.commit()
            await db.refresh(user)
        else:
            # 创建新用户
            role = (await db.execute(select(Role).where(Role.code == "user"))).scalar_one_or_none()
            if not role:
                role = (await db.execute(select(Role).where(Role.code == "admin"))).scalar_one_or_none()
            if not role:
                from ..core.security import hash_password as _hp
                raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "未找到可用角色")
            
            user = User(
                username=payload.username,
                email=ldap_info.get("email"),
                display_name=ldap_info.get("display_name"),
                password_hash=hash_password(payload.password),
                role_id=role.id,
                status="active",
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
        
        return TokenOut(
            access_token=create_access_token(user.id, user.role.code),
            refresh_token=create_refresh_token(user.id),
        )
    
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误")


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


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "原密码不正确")
    if payload.old_password == payload.new_password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "新密码不能与原密码相同")
    user.password_hash = hash_password(payload.new_password)
    await db.commit()
    return {"ok": True}


@router.patch("/me/email", response_model=UserOut)
async def update_email(
    payload: EmailUpdateIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    email = (payload.email or "").strip() or None
    if email and "@" not in email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "邮箱格式不正确")
    user.email = email
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/sso/config")
async def get_sso_config():
    """获取 SSO 配置（仅返回前端需要的信息）。"""
    from ..auth.sso import sso_service
    config = sso_service.get_oidc_config()
    return {"enabled": sso_service.config.enabled, "config": config}
