"""审计中间件 — 自动记录 API 操作。"""
from __future__ import annotations
import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.background import BackgroundTask

logger = logging.getLogger(__name__)

# 需要审计的操作
AUDIT_ACTIONS = {
    "POST": "create",
    "PUT": "update",
    "PATCH": "update",
    "DELETE": "delete",
}

# 资源类型映射
RESOURCE_TYPE_MAP = {
    "/api/auth/login": ("auth", "login"),
    "/api/auth/logout": ("auth", "logout"),
    "/api/admin/users": ("user", None),
    "/api/admin/agents": ("agent", None),
    "/api/admin/models": ("model", None),
    "/api/admin/skills": ("skill", None),
    "/api/admin/mcp": ("mcp", None),
    "/api/admin/roles": ("role", None),
    "/api/conversations": ("conversation", None),
    "/api/tasks": ("task", None),
    "/api/files": ("file", None),
    "/api/memories": ("memory", None),
    "/api/feedback": ("feedback", None),
}

# 敏感操作（需要审计）
SENSITIVE_PATHS = {
    "/api/auth/login",
    "/api/auth/logout",
    "/api/admin/users",
    "/api/admin/roles",
    "/api/admin/models",
    "/api/admin/mcp",
    "/api/admin/skills",
    "/api/admin/agents",
    "/api/tasks",
    "/api/files/upload",
}


def _extract_resource_id(path: str) -> str | None:
    """从路径提取最后一个数字段作为资源 ID。"""
    parts = path.strip("/").split("/")
    for part in reversed(parts):
        try:
            int(part)
            return part
        except ValueError:
            continue
    return None


class AuditMiddleware(BaseHTTPMiddleware):
    """审计中间件，自动记录敏感操作。"""
    
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method
        
        # 只审计 API 请求
        if not path.startswith("/api/"):
            return await call_next(request)
        
        # 只审计敏感操作
        is_sensitive = any(path.startswith(p) for p in SENSITIVE_PATHS)
        is_write = method in ("POST", "PUT", "PATCH", "DELETE")
        
        if not is_sensitive and not is_write:
            return await call_next(request)
        
        # 记录开始时间
        start_time = time.time()
        
        # 执行请求
        response = await call_next(request)
        
        # 计算耗时
        duration_ms = int((time.time() - start_time) * 1000)
        
        # 获取客户端信息
        ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("User-Agent", "")
        
        # 获取用户 ID
        user_id = None
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            try:
                from ..core.security import decode_token
                payload = decode_token(auth[7:])
                user_id = payload.get("sub")
                if user_id:
                    user_id = int(user_id)
            except Exception:
                pass
        
        # 确定操作类型
        action = AUDIT_ACTIONS.get(method, "read")
        if path == "/api/auth/login":
            action = "login"
        elif path == "/api/auth/logout":
            action = "logout"
        
        # 确定资源类型
        resource_type = "api"
        for prefix, (rtype, _) in RESOURCE_TYPE_MAP.items():
            if path.startswith(prefix):
                resource_type = rtype
                break
        
        # 从路径提取资源 ID
        resource_id = _extract_resource_id(path)
        
        # 确定状态
        status = "success" if response.status_code < 400 else "failed"
        if response.status_code == 403:
            status = "denied"
        
        # 后台记录审计日志（不阻塞响应）
        response.background = BackgroundTask(
            _log_audit,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            detail_json={
                "method": method,
                "path": path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
            ip_address=ip,
            user_agent=user_agent,
            status=status,
        )
        
        return response


async def _log_audit(
    user_id: int | None,
    action: str,
    resource_type: str,
    resource_id: str | None,
    detail_json: dict,
    ip_address: str,
    user_agent: str,
    status: str,
):
    """后台记录审计日志。"""
    try:
        from ..db.session import SessionLocal
        from ..services.audit_service import AuditService
        
        async with SessionLocal() as db:
            audit_svc = AuditService(db)
            await audit_svc.log(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                detail_json=detail_json,
                ip_address=ip_address,
                user_agent=user_agent,
                status=status,
            )
    except Exception as e:
        logger.warning("Audit logging failed: %s", e)
