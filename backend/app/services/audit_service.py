"""审计日志服务 — 记录所有敏感操作，满足合规要求。"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class AuditService:
    """审计日志服务。"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def log(
        self,
        *,
        user_id: int | None = None,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        detail_json: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        status: str = "success",
        error_message: str | None = None,
    ) -> int:
        """记录审计日志。
        
        Args:
            user_id: 操作用户 ID
            action: 操作类型（login/logout/create/update/delete/export等）
            resource_type: 资源类型（user/agent/conversation/model等）
            resource_id: 资源 ID
            detail_json: 操作详情
            ip_address: 客户端 IP
            user_agent: User-Agent
            status: 操作状态（success/failed/denied）
            error_message: 错误信息
        
        Returns:
            日志 ID
        """
        from ..db.models import AuditLog
        
        log_entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            detail_json=detail_json,
            ip_address=ip_address,
            user_agent=user_agent[:512] if user_agent else None,
            status=status,
            error_message=error_message,
        )
        self.db.add(log_entry)
        await self.db.commit()
        await self.db.refresh(log_entry)
        
        logger.info("Audit: user=%s action=%s resource=%s/%s status=%s",
                    user_id, action, resource_type, resource_id, status)
        return log_entry.id
    
    async def get_logs(
        self,
        *,
        user_id: int | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """查询审计日志。"""
        from ..db.models import AuditLog
        
        query = select(AuditLog)
        count_query = select(func.count(AuditLog.id))
        
        filters = []
        if user_id:
            filters.append(AuditLog.user_id == user_id)
        if action:
            filters.append(AuditLog.action == action)
        if resource_type:
            filters.append(AuditLog.resource_type == resource_type)
        if start_time:
            filters.append(AuditLog.created_at >= start_time)
        if end_time:
            filters.append(AuditLog.created_at <= end_time)
        
        if filters:
            query = query.where(*filters)
            count_query = count_query.where(*filters)
        
        total = (await self.db.execute(count_query)).scalar() or 0
        
        logs = list((await self.db.execute(
            query.order_by(desc(AuditLog.created_at))
            .limit(limit)
            .offset(offset)
        )).scalars().all())
        
        return [
            {
                "id": l.id,
                "user_id": l.user_id,
                "action": l.action,
                "resource_type": l.resource_type,
                "resource_id": l.resource_id,
                "detail_json": l.detail_json,
                "ip_address": l.ip_address,
                "status": l.status,
                "error_message": l.error_message,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in logs
        ], total
    
    async def get_user_activity(
        self,
        user_id: int,
        days: int = 30,
    ) -> dict:
        """获取用户活动统计。"""
        from ..db.models import AuditLog
        from datetime import timedelta
        
        since = datetime.now(timezone.utc) - timedelta(days=days)
        
        # 按操作类型统计
        action_stats = list((await self.db.execute(
            select(
                AuditLog.action,
                func.count(AuditLog.id).label("count"),
            )
            .where(AuditLog.user_id == user_id, AuditLog.created_at >= since)
            .group_by(AuditLog.action)
        )).all())
        
        # 按资源类型统计
        resource_stats = list((await self.db.execute(
            select(
                AuditLog.resource_type,
                func.count(AuditLog.id).label("count"),
            )
            .where(AuditLog.user_id == user_id, AuditLog.created_at >= since)
            .group_by(AuditLog.resource_type)
        )).all())
        
        # 按天统计
        daily_stats = list((await self.db.execute(
            select(
                func.date(AuditLog.created_at).label("date"),
                func.count(AuditLog.id).label("count"),
            )
            .where(AuditLog.user_id == user_id, AuditLog.created_at >= since)
            .group_by(func.date(AuditLog.created_at))
        )).all())
        
        return {
            "period_days": days,
            "actions": {r.action: r.count for r in action_stats},
            "resources": {r.resource_type: r.count for r in resource_stats},
            "daily": [{"date": str(r.date), "count": r.count} for r in daily_stats],
            "total_operations": sum(r.count for r in action_stats),
        }


# 全局审计服务实例（延迟初始化）
_audit_service: AuditService | None = None


def get_audit_service(db: AsyncSession) -> AuditService:
    """获取审计服务实例。"""
    return AuditService(db)
