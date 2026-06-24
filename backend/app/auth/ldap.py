"""LDAP/SSO 认证后端 — 企业统一认证。"""
from __future__ import annotations
import asyncio
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LDAPConfig:
    """LDAP 配置。"""
    enabled: bool = False
    server: str = ""  # ldap://ldap.example.com
    base_dn: str = ""  # dc=example,dc=com
    bind_dn: str = ""  # cn=admin,dc=example,dc=com
    bind_password: str = ""
    user_search_base: str = ""  # ou=users,dc=example,dc=com
    user_search_filter: str = "(uid={username})"
    group_search_base: str = ""  # ou=groups,dc=example,dc=com
    group_search_filter: str = "(member={dn})"
    # 映射
    email_attr: str = "mail"
    display_name_attr: str = "cn"
    role_attr: str = ""  # 组名映射到角色


class LDAPAuthBackend:
    """LDAP 认证后端。"""
    
    def __init__(self, config: LDAPConfig | None = None):
        self.config = config or self._load_config()
    
    def _load_config(self) -> LDAPConfig:
        """从环境变量加载配置。"""
        return LDAPConfig(
            enabled=os.getenv("LDAP_ENABLED", "false").lower() == "true",
            server=os.getenv("LDAP_SERVER", ""),
            base_dn=os.getenv("LDAP_BASE_DN", ""),
            bind_dn=os.getenv("LDAP_BIND_DN", ""),
            bind_password=os.getenv("LDAP_BIND_PASSWORD", ""),
            user_search_base=os.getenv("LDAP_USER_SEARCH_BASE", ""),
            user_search_filter=os.getenv("LDAP_USER_SEARCH_FILTER", "(uid={username})"),
            group_search_base=os.getenv("LDAP_GROUP_SEARCH_BASE", ""),
            group_search_filter=os.getenv("LDAP_GROUP_SEARCH_FILTER", "(member={dn})"),
            email_attr=os.getenv("LDAP_EMAIL_ATTR", "mail"),
            display_name_attr=os.getenv("LDAP_DISPLAY_NAME_ATTR", "cn"),
            role_attr=os.getenv("LDAP_ROLE_ATTR", ""),
        )
    
    async def authenticate(self, username: str, password: str) -> dict | None:
        """LDAP 认证（非阻塞）。"""
        if not self.config.enabled:
            logger.debug("LDAP not enabled")
            return None
        
        try:
            import ldap3  # noqa: F811
        except ImportError:
            logger.warning("ldap3 not installed, LDAP auth disabled")
            return None
        
        return await asyncio.to_thread(self._sync_authenticate, username, password)
    
    def _sync_authenticate(self, username: str, password: str) -> dict | None:
        """同步 LDAP 认证（在线程池中执行）。"""
        import ldap3
        from ldap3.utils.conv import escape_filter_chars
        
        conn = None
        user_conn = None
        try:
            server = ldap3.Server(self.config.server)
            conn = ldap3.Connection(
                server,
                user=self.config.bind_dn,
                password=self.config.bind_password,
                auto_bind=True,
            )
            
            escaped_username = escape_filter_chars(username)
            search_filter = self.config.user_search_filter.format(username=escaped_username)
            conn.search(
                search_base=self.config.user_search_base,
                search_filter=search_filter,
                attributes=[self.config.email_attr, self.config.display_name_attr, self.config.role_attr],
            )
            
            if not conn.entries:
                logger.info("LDAP user not found: %s", username)
                return None
            
            user_entry = conn.entries[0]
            user_dn = user_entry.entry_dn
            
            user_conn = ldap3.Connection(
                server,
                user=user_dn,
                password=password,
                auto_bind=True,
            )
            
            user_info = {
                "username": username,
                "email": str(getattr(user_entry, self.config.email_attr, "")),
                "display_name": str(getattr(user_entry, self.config.display_name_attr, "")),
                "source": "ldap",
            }
            
            if self.config.role_attr and self.config.group_search_base:
                groups = self._get_user_groups(conn, user_dn)
                user_info["groups"] = groups
            
            logger.info("LDAP authentication successful: %s", username)
            return user_info
            
        except ldap3.core.exceptions.LDAPBindError:
            logger.warning("LDAP bind failed for %s", username)
            return None
        except Exception as e:
            logger.warning("LDAP authentication failed: %s", e)
            return None
        finally:
            if conn:
                try:
                    conn.unbind()
                except Exception:
                    pass
            if user_conn:
                try:
                    user_conn.unbind()
                except Exception:
                    pass
    
    def _get_user_groups(self, conn, user_dn: str) -> list[str]:
        """获取用户所属的组。"""
        try:
            from ldap3.utils.conv import escape_filter_chars
            
            escaped_dn = escape_filter_chars(user_dn)
            search_filter = self.config.group_search_filter.format(dn=escaped_dn)
            conn.search(
                search_base=self.config.group_search_base,
                search_filter=search_filter,
                attributes=["cn"],
            )
            return [str(entry.cn) for entry in conn.entries]
        except Exception as e:
            logger.warning("Failed to get user groups: %s", e)
            return []


# 全局 LDAP 后端实例
ldap_backend = LDAPAuthBackend()
