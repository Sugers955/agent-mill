"""统计数据 API — 从 call_logs 实时聚合成本、用量、趋势"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from calendar import monthrange

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select, func, and_, case, extract, text, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_db
from ...db.models import CallLog, Model, User, Agent, Conversation, Department
from ...deps import require_admin_or_operator
from ...schemas import (
    StatsOverview,
    StatsByUserItem,
    StatsByAgentItem,
    StatsByModelItem,
    StatsTrendItem,
    TokenDetailItem,
)
from ...core.config import settings


def _is_mysql() -> bool:
    return settings.DB_TYPE == "mysql"

router = APIRouter(prefix="/api/admin/stats", tags=["admin-stats"])


def _month_range():
    """返回 (month_start, month_end) 当前月份 UTC 时间范围（naive）。"""
    now = datetime.now(timezone.utc)
    _, last_day = monthrange(now.year, now.month)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    end = now.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999, tzinfo=None)
    return start, end


def _cost_expr(model_unit_price_col):
    """根据 unit_price 计算 cost（分），公式：(tokens_in + tokens_out) / 1000 * unit_price"""
    unit = func.coalesce(model_unit_price_col, 0)
    total_t = CallLog.tokens_in + CallLog.tokens_out
    return func.coalesce(func.cast(total_t / 1000.0 * unit, func.INTEGER), 0)


@router.get("/overview", response_model=StatsOverview)
async def stats_overview(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin_or_operator),
):
    month_s, month_e = _month_range()

    # 总 tokens
    tokens_row = (await db.execute(
        select(
            func.coalesce(func.sum(CallLog.tokens_in), 0),
            func.coalesce(func.sum(CallLog.tokens_out), 0),
        ).where(and_(CallLog.created_at >= month_s, CallLog.created_at <= month_e))
    )).one()
    total_tokens = int(tokens_row[0]) + int(tokens_row[1])

    # 总成本（分）→ 元
    cost_subq = (
        select(
            func.coalesce(func.sum(
                (CallLog.tokens_in + CallLog.tokens_out) / 1000.0
                * func.coalesce(Model.unit_price_per_1k_tokens, 0)
            ), 0).label("total_cost_fen")
        )
        .select_from(CallLog)
        .outerjoin(Model, Model.id == CallLog.model_id)
        .where(and_(CallLog.created_at >= month_s, CallLog.created_at <= month_e))
    )
    cost_row = (await db.execute(cost_subq)).one()
    total_cost = round(float(cost_row[0]) / 100.0, 2)

    # 活跃用户数
    active_users = (await db.execute(
        select(func.count(func.distinct(CallLog.user_id)))
        .where(and_(CallLog.created_at >= month_s, CallLog.created_at <= month_e))
    )).scalar()

    # 对话数
    total_conv = (await db.execute(
        select(func.count(func.distinct(CallLog.conversation_id)))
        .where(and_(CallLog.created_at >= month_s, CallLog.created_at <= month_e))
    )).scalar()

    return StatsOverview(
        total_tokens=total_tokens,
        total_cost=total_cost,
        active_users=int(active_users or 0),
        total_conversations=int(total_conv or 0),
    )


@router.get("/by-user", response_model=list[StatsByUserItem])
async def stats_by_user(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin_or_operator),
):
    month_s, month_e = _month_range()
    rows = (await db.execute(
        select(
            CallLog.user_id,
            User.username.label("user_name"),
            func.coalesce(func.sum(CallLog.tokens_in), 0).label("tokens_in"),
            func.coalesce(func.sum(CallLog.tokens_out), 0).label("tokens_out"),
            func.count(CallLog.id).label("call_count"),
            func.coalesce(func.sum(
                (CallLog.tokens_in + CallLog.tokens_out) / 1000.0
                * func.coalesce(Model.unit_price_per_1k_tokens, 0)
            ), 0).label("cost_fen"),
        )
        .select_from(CallLog)
        .outerjoin(User, User.id == CallLog.user_id)
        .outerjoin(Model, Model.id == CallLog.model_id)
        .where(and_(CallLog.created_at >= month_s, CallLog.created_at <= month_e))
        .group_by(CallLog.user_id, User.username)
        .order_by(func.sum(CallLog.tokens_in + CallLog.tokens_out).desc())
        .limit(50)
    )).all()

    return [
        StatsByUserItem(
            user_id=r.user_id,
            user_name=r.user_name,
            tokens_in=int(r.tokens_in),
            tokens_out=int(r.tokens_out),
            total_tokens=int(r.tokens_in) + int(r.tokens_out),
            call_count=int(r.call_count),
            cost=round(float(r.cost_fen) / 100.0, 2),
        )
        for r in rows
    ]


@router.get("/by-agent", response_model=list[StatsByAgentItem])
async def stats_by_agent(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin_or_operator),
):
    month_s, month_e = _month_range()
    rows = (await db.execute(
        select(
            CallLog.agent_id,
            Agent.name.label("agent_name"),
            func.coalesce(func.sum(CallLog.tokens_in), 0).label("tokens_in"),
            func.coalesce(func.sum(CallLog.tokens_out), 0).label("tokens_out"),
            func.count(CallLog.id).label("call_count"),
            func.coalesce(func.sum(
                (CallLog.tokens_in + CallLog.tokens_out) / 1000.0
                * func.coalesce(Model.unit_price_per_1k_tokens, 0)
            ), 0).label("cost_fen"),
        )
        .select_from(CallLog)
        .outerjoin(Agent, Agent.id == CallLog.agent_id)
        .outerjoin(Model, Model.id == CallLog.model_id)
        .where(and_(CallLog.created_at >= month_s, CallLog.created_at <= month_e))
        .group_by(CallLog.agent_id, Agent.name)
        .order_by(func.sum(CallLog.tokens_in + CallLog.tokens_out).desc())
    )).all()

    return [
        StatsByAgentItem(
            agent_id=r.agent_id,
            agent_name=r.agent_name,
            tokens_in=int(r.tokens_in),
            tokens_out=int(r.tokens_out),
            total_tokens=int(r.tokens_in) + int(r.tokens_out),
            call_count=int(r.call_count),
            cost=round(float(r.cost_fen) / 100.0, 2),
        )
        for r in rows
    ]


@router.get("/by-model", response_model=list[StatsByModelItem])
async def stats_by_model(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin_or_operator),
):
    month_s, month_e = _month_range()
    rows = (await db.execute(
        select(
            CallLog.model_id,
            Model.code.label("model_name"),
            Model.provider.label("model_provider"),
            func.coalesce(func.sum(CallLog.tokens_in), 0).label("tokens_in"),
            func.coalesce(func.sum(CallLog.tokens_out), 0).label("tokens_out"),
            func.count(CallLog.id).label("call_count"),
            func.coalesce(func.sum(
                (CallLog.tokens_in + CallLog.tokens_out) / 1000.0
                * func.coalesce(Model.unit_price_per_1k_tokens, 0)
            ), 0).label("cost_fen"),
        )
        .select_from(CallLog)
        .outerjoin(Model, Model.id == CallLog.model_id)
        .where(and_(CallLog.created_at >= month_s, CallLog.created_at <= month_e))
        .group_by(CallLog.model_id, Model.code, Model.provider)
        .order_by(func.sum(
            (CallLog.tokens_in + CallLog.tokens_out) / 1000.0
            * func.coalesce(Model.unit_price_per_1k_tokens, 0)
        ).desc())
    )).all()

    return [
        StatsByModelItem(
            model_id=r.model_id,
            model_name=r.model_name,
            model_provider=r.model_provider,
            tokens_in=int(r.tokens_in),
            tokens_out=int(r.tokens_out),
            total_tokens=int(r.tokens_in) + int(r.tokens_out),
            call_count=int(r.call_count),
            cost=round(float(r.cost_fen) / 100.0, 2),
        )
        for r in rows
    ]


@router.get("/trend", response_model=list[StatsTrendItem])
async def stats_trend(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin_or_operator),
):
    """按天聚合近 N 天的用量趋势。"""
    days = max(1, min(days, 365))
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)

    # 按日期聚合 — 使用 literal_column 引用 label 避免 date_trunc 重复求值
    if _is_mysql():
        # MySQL 使用 DATE() 函数
        day_expr = func.date(CallLog.created_at).label("day")
    else:
        # PostgreSQL 使用 date_trunc
        day_expr = func.date_trunc("day", CallLog.created_at).label("day")
    
    rows = (await db.execute(
        select(
            day_expr,
            func.coalesce(func.sum(CallLog.tokens_in), 0).label("tokens_in"),
            func.coalesce(func.sum(CallLog.tokens_out), 0).label("tokens_out"),
            func.count(CallLog.id).label("call_count"),
            func.coalesce(func.sum(
                (CallLog.tokens_in + CallLog.tokens_out) / 1000.0
                * func.coalesce(Model.unit_price_per_1k_tokens, 0)
            ), 0).label("cost_fen"),
        )
        .select_from(CallLog)
        .outerjoin(Model, Model.id == CallLog.model_id)
        .where(CallLog.created_at >= start_date)
        .group_by(day_expr)
        .order_by(day_expr)
    )).all()

    # 确保每一天都有数据（补零）
    result = []
    day_map = {r.day.date() if hasattr(r.day, "date") else r.day: r for r in rows}
    for i in range(days):
        d = (start_date + timedelta(days=i)).date()
        r = day_map.get(d)
        if r:
            result.append(StatsTrendItem(
                date=d.isoformat(),
                tokens_in=int(r.tokens_in),
                tokens_out=int(r.tokens_out),
                total_tokens=int(r.tokens_in) + int(r.tokens_out),
                call_count=int(r.call_count),
                cost=round(float(r.cost_fen) / 100.0, 2),
            ))
        else:
            result.append(StatsTrendItem(
                date=d.isoformat(),
                tokens_in=0, tokens_out=0, total_tokens=0,
                call_count=0, cost=0.0,
            ))
    return result


@router.get("/by-department")
async def stats_by_department(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin_or_operator),
):
    """按部门统计使用情况。"""
    stmt = (
        select(
            Department.id,
            Department.name,
            func.count(CallLog.id).label("call_count"),
            func.coalesce(func.sum(CallLog.tokens_in + CallLog.tokens_out), 0).label("total_tokens"),
            func.coalesce(func.sum(CallLog.latency_ms), 0).label("total_latency_ms"),
        )
        .join(User, User.department_id == Department.id)
        .join(CallLog, CallLog.user_id == User.id)
        .group_by(Department.id, Department.name)
        .order_by(desc("total_tokens"))
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        {
            "department_id": r.id,
            "department_name": r.name,
            "call_count": r.call_count,
            "total_tokens": r.total_tokens,
            "avg_latency_ms": round(r.total_latency_ms / r.call_count) if r.call_count > 0 else 0,
        }
        for r in rows
    ]


@router.get("/agent-effectiveness")
async def agent_effectiveness(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin_or_operator),
):
    """Agent 效果分析 — 对话完成率、平均轮次、复用率。"""
    # 每个 Agent 的统计
    stmt = (
        select(
            Agent.id,
            Agent.name,
            func.count(Conversation.id).label("conversation_count"),
            func.count(CallLog.id).label("call_count"),
            func.coalesce(func.sum(CallLog.tokens_in + CallLog.tokens_out), 0).label("total_tokens"),
            func.coalesce(func.sum(CallLog.latency_ms), 0).label("total_latency_ms"),
        )
        .outerjoin(Conversation, Conversation.agent_id == Agent.id)
        .outerjoin(CallLog, CallLog.agent_id == Agent.id)
        .where(Agent.enabled == True)  # noqa: E712
        .group_by(Agent.id, Agent.name)
        .order_by(desc("conversation_count"))
    )
    result = await db.execute(stmt)
    rows = result.all()

    # 计算每个 Agent 的平均对话轮次
    effectiveness = []
    for r in rows:
        avg_latency = round(r.total_latency_ms / r.call_count) if r.call_count > 0 else 0

        # 计算复用率（有多轮对话的用户占比）
        reuse_stmt = (
            select(
                func.count(func.distinct(Conversation.user_id)).label("total_users"),
            )
            .where(Conversation.agent_id == r.id)
        )
        reuse_result = await db.execute(reuse_stmt)
        total_users = reuse_result.scalar() or 0

        # 有多个对话的用户数
        sub = (
            select(Conversation.user_id)
            .where(Conversation.agent_id == r.id)
            .group_by(Conversation.user_id)
            .having(func.count(Conversation.id) > 1)
            .subquery()
        )
        multi_conv_stmt = select(func.count(func.distinct(sub.c.user_id)))
        multi_result = await db.execute(multi_conv_stmt)
        multi_users = multi_result.scalar() or 0

        reuse_rate = round(multi_users / total_users * 100, 1) if total_users > 0 else 0

        effectiveness.append({
            "agent_id": r.id,
            "agent_name": r.name,
            "conversation_count": r.conversation_count,
            "call_count": r.call_count,
            "total_tokens": r.total_tokens,
            "avg_latency_ms": avg_latency,
            "unique_users": total_users,
            "reuse_rate": reuse_rate,
        })

    return effectiveness


@router.get("/token-detail")
async def stats_token_detail(
    user_id: int | None = None,
    agent_id: int | None = None,
    conversation_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_or_operator),
):
    """Token 消耗明细（分页）。"""
    conditions = ["1=1"]
    params: dict = {"lim": limit, "off": offset}

    if user_id:
        conditions.append("cl.user_id = :uid")
        params["uid"] = user_id
    if agent_id:
        conditions.append("cl.agent_id = :aid")
        params["aid"] = agent_id
    if conversation_id:
        conditions.append("cl.conversation_id = :cid")
        params["cid"] = conversation_id
    if start_date:
        conditions.append("cl.created_at >= :start")
        params["start"] = start_date
    if end_date:
        conditions.append("cl.created_at < :end + INTERVAL 1 DAY")
        params["end"] = end_date

    where = " AND ".join(conditions)

    count_sql = text(f"SELECT COUNT(*) FROM call_logs cl WHERE {where}")
    total = (await db.execute(count_sql, params)).scalar() or 0

    sql = text(f"""
        SELECT cl.id, cl.created_at, cl.tokens_in, cl.tokens_out,
               cl.tokens_in + cl.tokens_out AS total_tokens,
               cl.latency_ms, cl.status,
               u.username AS user_name,
               a.name AS agent_name,
               m.code AS model_name
        FROM call_logs cl
        LEFT JOIN users u ON u.id = cl.user_id
        LEFT JOIN agents a ON a.id = cl.agent_id
        LEFT JOIN models m ON m.id = cl.model_id
        WHERE {where}
        ORDER BY cl.id DESC
        LIMIT :lim OFFSET :off
    """)
    rows = (await db.execute(sql, params)).fetchall()

    items = []
    for r in rows:
        cost = (r.tokens_in + r.tokens_out) / 1000 * 0.002
        items.append(TokenDetailItem(
            id=r.id, created_at=r.created_at,
            user_name=r.user_name, agent_name=r.agent_name, model_name=r.model_name,
            tokens_in=r.tokens_in, tokens_out=r.tokens_out,
            total_tokens=r.total_tokens, cost=round(cost, 4),
            latency_ms=r.latency_ms, status=r.status,
        ))

    return {"items": items, "total": total}


@router.get("/token-export")
async def stats_token_export(
    user_id: int | None = None,
    agent_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_or_operator),
):
    """导出 Token 消耗明细为 CSV。"""
    import csv, io

    conditions = ["1=1"]
    params: dict = {}
    if user_id:
        conditions.append("cl.user_id = :uid")
        params["uid"] = user_id
    if agent_id:
        conditions.append("cl.agent_id = :aid")
        params["aid"] = agent_id
    if start_date:
        conditions.append("cl.created_at >= :start")
        params["start"] = start_date
    if end_date:
        conditions.append("cl.created_at < :end + INTERVAL 1 DAY")
        params["end"] = end_date

    where = " AND ".join(conditions)
    sql = text(f"""
        SELECT cl.id, cl.created_at, cl.tokens_in, cl.tokens_out,
               cl.latency_ms, cl.status,
               u.username AS user_name,
               a.name AS agent_name,
               m.code AS model_name
        FROM call_logs cl
        LEFT JOIN users u ON u.id = cl.user_id
        LEFT JOIN agents a ON a.id = cl.agent_id
        LEFT JOIN models m ON m.id = cl.model_id
        WHERE {where}
        ORDER BY cl.id DESC
    """)
    rows = (await db.execute(sql, params)).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "时间", "用户", "数字员工", "模型", "输入Token", "输出Token", "合计Token", "延迟(ms)", "状态"])
    for r in rows:
        writer.writerow([r.id, r.created_at, r.user_name, r.agent_name, r.model_name,
                        r.tokens_in, r.tokens_out, r.tokens_in + r.tokens_out,
                        r.latency_ms, r.status])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=token-consumption.csv"},
    )


@router.get("/latency-trend")
async def stats_latency_trend(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_or_operator),
):
    """延迟趋势（平均延迟逐日）。"""
    date_fn = "DATE(created_at)" if _is_mysql() else "date_trunc('day', created_at)::date"

    sql = text(f"""
        SELECT {date_fn} AS dt,
               ROUND(AVG(latency_ms)) AS avg_latency,
               COUNT(*) AS calls
        FROM call_logs
        WHERE created_at >= NOW() - INTERVAL :days DAY
        GROUP BY dt
        ORDER BY dt
    """)
    rows = (await db.execute(sql, {"days": days})).fetchall()

    return [{
        "date": str(r.dt),
        "avg_latency": r.avg_latency,
        "calls": r.calls,
    } for r in rows]


@router.get("/error-trend")
async def stats_error_trend(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_or_operator),
):
    """错误率趋势（逐日）。"""
    date_fn = "DATE(created_at)" if _is_mysql() else "date_trunc('day', created_at)::date"

    sql = text(f"""
        SELECT {date_fn} AS dt,
               COUNT(*) AS total_calls,
               SUM(CASE WHEN status != 'ok' THEN 1 ELSE 0 END) AS error_count,
               ROUND(SUM(CASE WHEN status != 'ok' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) * 100, 2) AS error_rate
        FROM call_logs
        WHERE created_at >= NOW() - INTERVAL :days DAY
        GROUP BY dt
        ORDER BY dt
    """)
    rows = (await db.execute(sql, {"days": days})).fetchall()

    return [{
        "date": str(r.dt),
        "total_calls": r.total_calls,
        "error_count": r.error_count,
        "error_rate": r.error_rate,
    } for r in rows]


@router.get("/system-health")
async def stats_system_health(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_or_operator),
):
    """系统健康概览（近 1 小时）。"""
    sql = text("""
        SELECT
            COALESCE(ROUND(AVG(latency_ms)), 0) AS avg_latency,
            COUNT(*) AS total_calls,
            COALESCE(ROUND(SUM(CASE WHEN status != 'ok' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) * 100, 2), 0) AS error_rate,
            (SELECT COUNT(*) FROM agents WHERE status = 'active') AS active_agents,
            (SELECT COUNT(*) FROM conversations WHERE status = 'active') AS active_conversations
        FROM call_logs
        WHERE created_at >= NOW() - INTERVAL 1 HOUR
    """)
    row = (await db.execute(sql)).fetchone()

    return {
        "avg_latency": row.avg_latency,
        "error_rate": row.error_rate,
        "active_agents": row.active_agents,
        "active_conversations": row.active_conversations,
        "total_calls_1h": row.total_calls,
    }
