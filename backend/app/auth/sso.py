"""SSO/OIDC 认证服务 — 支持多种 SSO 提供商。"""
from __future__ import annotations
import logging
import os
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

# 简单的内存 state 存储（生产环境应使用 Redis）
_oauth_states: dict[str, float] = {}  # state -> created_at
_STATE_TTL = 600  # 10 分钟过期


def generate_oauth_state() -> str:
    """生成并存储 OAuth state 参数。"""
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = time.time()
    # 清理过期 state
    now = time.time()
    expired = [k for k, t in _oauth_states.items() if now - t > _STATE_TTL]
    for k in expired:
        del _oauth_states[k]
    return state


def validate_oauth_state(state: str) -> bool:
    """验证 OAuth state 参数。"""
    if not state or state not in _oauth_states:
        return False
    created = _oauth_states.pop(state)
    return time.time() - created <= _STATE_TTL


@dataclass
class SSOConfig:
    """SSO 配置。"""
    enabled: bool = False
    provider: str = ""  # oidc/saml/cas
    # OIDC 配置
    client_id: str = ""
    client_secret: str = ""
    issuer_url: str = ""
    redirect_uri: str = ""
    # SAML 配置
    idp_metadata_url: str = ""
    sp_entity_id: str = ""
    # 角色映射
    role_mapping: dict[str, str] = None  # SSO角色 -> 系统角色

    def __post_init__(self):
        if self.role_mapping is None:
            self.role_mapping = {}


class SSOService:
    """SSO/OIDC 认证服务。"""

    def __init__(self, config: SSOConfig | None = None):
        self.config = config or self._load_config()

    def _load_config(self) -> SSOConfig:
        """从环境变量加载配置。"""
        import json

        role_mapping_str = os.getenv("SSO_ROLE_MAPPING", "{}")
        try:
            role_mapping = json.loads(role_mapping_str)
        except json.JSONDecodeError:
            role_mapping = {}

        return SSOConfig(
            enabled=os.getenv("SSO_ENABLED", "false").lower() == "true",
            provider=os.getenv("SSO_PROVIDER", "oidc"),
            client_id=os.getenv("SSO_CLIENT_ID", ""),
            client_secret=os.getenv("SSO_CLIENT_SECRET", ""),
            issuer_url=os.getenv("SSO_ISSUER_URL", ""),
            redirect_uri=os.getenv("SSO_REDIRECT_URI", ""),
            idp_metadata_url=os.getenv("SSO_IDP_METADATA_URL", ""),
            sp_entity_id=os.getenv("SSO_SP_ENTITY_ID", ""),
            role_mapping=role_mapping,
        )

    def get_oidc_config(self) -> dict | None:
        """获取 OIDC 配置（用于前端）。"""
        if not self.config.enabled or self.config.provider != "oidc":
            return None

        return {
            "client_id": self.config.client_id,
            "issuer_url": self.config.issuer_url,
            "redirect_uri": self.config.redirect_uri,
            "scopes": os.getenv("SSO_SCOPES", "openid profile email").split(),
        }

    def get_authorization_url(self, state: str = "") -> str:
        """生成授权 URL（自动生成 state 如果未提供）。"""
        config = self.get_oidc_config()
        if not config:
            return ""

        if not state:
            state = generate_oauth_state()

        scopes = config.get("scopes", ["openid", "profile", "email"])
        issuer = config["issuer_url"].rstrip("/")
        params = {
            "response_type": "code",
            "client_id": config["client_id"],
            "redirect_uri": config["redirect_uri"],
            "scope": " ".join(scopes),
            "state": state,
        }
        return f"{issuer}/authorize?{urlencode(params)}"

    async def handle_callback(self, code: str, state: str = "") -> dict:
        """处理 OIDC 回调，获取 token 和用户信息。"""
        # 验证 state 参数（防 CSRF）
        if state and not validate_oauth_state(state):
            return {"error": "state 参数无效或已过期，请重新发起登录"}

        config = self.get_oidc_config()
        if not config:
            return {"error": "SSO 未配置"}

        # 1. 用 code 换取 token
        token_data = await self._exchange_code(code, config)
        if not token_data:
            return {"error": "换取 token 失败"}

        access_token = token_data.get("access_token")
        if not access_token:
            return {"error": "未获取到 access_token"}

        # 2. 获取用户信息
        user_info = await self._get_user_info(access_token, config)
        if not user_info:
            return {"error": "获取用户信息失败"}

        # 3. 映射角色
        role = self._map_role(user_info)

        # 4. 创建/更新用户
        from ..db.session import SessionLocal
        from ..db.models import User, Role

        async with SessionLocal() as db:
            from sqlalchemy import select

            # 获取角色
            role_obj = (await db.execute(
                select(Role).where(Role.code == role)
            )).scalar_one_or_none()

            if not role_obj:
                role_obj = (await db.execute(
                    select(Role).where(Role.code == "user")
                )).scalar_one()

            # 查找或创建用户
            username = user_info.get("preferred_username", user_info.get("email", ""))
            user = (await db.execute(
                select(User).where(User.username == username)
            )).scalar_one_or_none()

            if not user:
                user = User(
                    username=username,
                    password_hash="",  # SSO 用户无需密码
                    email=user_info.get("email", ""),
                    display_name=user_info.get("name", ""),
                    role_id=role_obj.id,
                )
                db.add(user)
            else:
                user.email = user_info.get("email", user.email)
                user.display_name = user_info.get("name", user.display_name)
                user.role_id = role_obj.id

            await db.commit()
            await db.refresh(user)

            # 5. 生成 JWT
            from ..core.security import create_access_token
            token = create_access_token(user.id, user.role.code if user.role else "user")

            return {
                "access_token": token,
                "token_type": "bearer",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "role": user.role.code if user.role else role,
                    "display_name": user.display_name,
                },
            }

    async def _exchange_code(self, code: str, config: dict) -> dict | None:
        """用授权码换取 token。"""
        issuer = config["issuer_url"].rstrip("/")
        token_url = f"{issuer}/token"
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config["redirect_uri"],
            "client_id": config["client_id"],
            "client_secret": self.config.client_secret,
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(token_url, data=data)
                if resp.status_code == 200:
                    return resp.json()
                logger.warning("Token 交换失败: %s %s", resp.status_code, resp.text)
        except Exception as e:
            logger.warning("Token 交换异常: %s", e)
        return None

    async def _get_user_info(self, access_token: str, config: dict) -> dict | None:
        """获取用户信息。"""
        issuer = config["issuer_url"].rstrip("/")
        userinfo_url = f"{issuer}/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(userinfo_url, headers=headers)
                if resp.status_code == 200:
                    return resp.json()
                logger.warning("获取用户信息失败: %s %s", resp.status_code, resp.text)
        except Exception as e:
            logger.warning("获取用户信息异常: %s", e)
        return None

    def _map_role(self, user_info: dict) -> str:
        """映射 SSO 角色到系统角色。"""
        # 从 user_info 中获取角色信息
        # 支持多种字段名
        sso_roles = user_info.get("roles", [])
        if isinstance(sso_roles, str):
            sso_roles = [sso_roles]

        # 使用配置的角色映射
        for role in sso_roles:
            if role in self.config.role_mapping:
                return self.config.role_mapping[role]

        # 默认角色映射规则
        for role in sso_roles:
            role_lower = role.lower()
            if role_lower in ("admin", "administrator", "系统管理员"):
                return "admin"
            elif role_lower in ("operator", "运营", "运营者"):
                return "operator"

        return "user"  # 默认

    def map_role(self, sso_role: str) -> str:
        """将 SSO 角色映射到系统角色（兼容旧接口）。"""
        return self.config.role_mapping.get(sso_role, "user")


# 全局 SSO 服务实例
sso_service = SSOService()
