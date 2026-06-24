"""API 限流中间件 — 令牌桶算法，保护系统稳定。"""
from __future__ import annotations
import time
import logging
from collections import defaultdict
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# 不活跃桶清理间隔（秒）
CLEANUP_INTERVAL = 600  # 10分钟
# 桶最大保留数（防止内存泄漏）
MAX_BUCKETS = 10000


class RateLimitBucket:
    """令牌桶实现。"""
    
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
        self.last_access = time.time()
    
    def consume(self) -> bool:
        self._refill()
        if self.tokens >= 1:
            self.tokens -= 1
            self.last_access = time.time()
            return True
        return False
    
    def _refill(self):
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
    
    @property
    def retry_after(self) -> float:
        self._refill()
        if self.tokens >= 1:
            return 0
        return (1 - self.tokens) / self.refill_rate
    
    @property
    def idle_seconds(self) -> float:
        return time.time() - self.last_access


class RateLimiter:
    """限流器，支持按用户/IP/端点配置。"""
    
    def __init__(self):
        self.limits: dict[str, tuple[int, float]] = {
            "/api/auth/login": (5, 0.1),
            "/api/auth/register": (3, 0.05),
            "/api/": (60, 1),
            "/api/admin/": (120, 2),
            "/api/conversations/": (30, 0.5),
        }
        
        self.user_buckets: dict[str, dict[str, RateLimitBucket]] = defaultdict(dict)
        self.ip_buckets: dict[str, dict[str, RateLimitBucket]] = defaultdict(dict)
        
        self._last_cleanup = time.time()
    
    def _get_limit(self, path: str) -> tuple[int, float]:
        for pattern, limit in sorted(self.limits.items(), key=lambda x: len(x[0]), reverse=True):
            if path.startswith(pattern):
                return limit
        return self.limits.get("/api/", (60, 1))
    
    def _get_or_create_bucket(
        self,
        buckets: dict[str, RateLimitBucket],
        key: str,
        path: str,
    ) -> RateLimitBucket:
        if key not in buckets:
            capacity, refill_rate = self._get_limit(path)
            buckets[key] = RateLimitBucket(capacity, refill_rate)
        return buckets[key]
    
    def _cleanup_idle_buckets(self, buckets: dict[str, dict[str, RateLimitBucket]]):
        """清理不活跃的用户/IP 桶，防止内存泄漏。"""
        idle_keys = [
            k for k, v in buckets.items()
            if all(b.idle_seconds > CLEANUP_INTERVAL for b in v.values())
        ]
        for k in idle_keys:
            del buckets[k]
    
    def check(self, user_id: int | None, ip: str, path: str) -> tuple[bool, float]:
        if time.time() - self._last_cleanup > CLEANUP_INTERVAL:
            self._cleanup_idle_buckets(self.user_buckets)
            self._cleanup_idle_buckets(self.ip_buckets)
            self._last_cleanup = time.time()
        
        if user_id:
            key = f"user:{user_id}"
            bucket = self._get_or_create_bucket(self.user_buckets[key], path, path)
        else:
            key = f"ip:{ip}"
            bucket = self._get_or_create_bucket(self.ip_buckets[key], path, path)
        
        if bucket.consume():
            return True, 0
        return False, bucket.retry_after
    
    def get_user_stats(self, user_id: int) -> dict:
        key = f"user:{user_id}"
        buckets = self.user_buckets.get(key, {})
        return {
            pattern: {
                "tokens_remaining": int(bucket.tokens),
                "capacity": bucket.capacity,
            }
            for pattern, bucket in buckets.items()
        }


rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI 限流中间件。"""
    
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)
        
        ip = request.client.host if request.client else "unknown"
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
        
        allowed, retry_after = rate_limiter.check(user_id, ip, path)
        
        if not allowed:
            logger.warning("Rate limited: user=%s ip=%s path=%s retry=%.1fs",
                          user_id, ip, path, retry_after)
            return Response(
                content='{"detail":"请求过于频繁，请稍后重试"}',
                status_code=429,
                media_type="application/json",
                headers={
                    "Retry-After": str(int(retry_after) + 1),
                    "X-RateLimit-Limit": str(rate_limiter._get_limit(path)[0]),
                    "X-RateLimit-Remaining": "0",
                },
            )
        
        response = await call_next(request)
        capacity, _ = rate_limiter._get_limit(path)
        remaining = capacity
        if user_id:
            key = f"user:{user_id}"
            user_buckets = rate_limiter.user_buckets.get(key, {})
            bucket = user_buckets.get(path)
            if bucket:
                remaining = int(bucket.tokens)
        response.headers["X-RateLimit-Limit"] = str(capacity)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        
        return response