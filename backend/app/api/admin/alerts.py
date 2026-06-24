"""告警规则 API — CRUD 操作。"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from ...db.session import get_db
from ...db.models import User, AlertRule, AlertEvent, SystemConfig
from ...deps import require_admin
from pydantic import BaseModel

router = APIRouter(prefix="/api/admin/alerts", tags=["alerts"])


class AlertRuleCreate(BaseModel):
    name: str
    description: str | None = None
    metric: str
    condition: str = "gte"
    threshold: float
    window_minutes: int = 5
    cooldown_minutes: int = 30
    enabled: bool = True


class AlertRuleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    metric: str | None = None
    condition: str | None = None
    threshold: float | None = None
    window_minutes: int | None = None
    cooldown_minutes: int | None = None
    enabled: bool | None = None


@router.get("/rules")
async def get_rules(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """获取所有告警规则。"""
    rules = (await db.execute(
        select(AlertRule).order_by(AlertRule.id.desc())
    )).scalars().all()
    return rules


@router.post("/rules")
async def create_rule(
    payload: AlertRuleCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """创建告警规则。"""
    rule = AlertRule(
        name=payload.name,
        description=payload.description,
        metric=payload.metric,
        condition=payload.condition,
        threshold=payload.threshold,
        window_minutes=payload.window_minutes,
        cooldown_minutes=payload.cooldown_minutes,
        enabled=payload.enabled,
        user_id=user.id,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.put("/rules/{rule_id}")
async def update_rule(
    rule_id: int,
    payload: AlertRuleUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """更新告警规则。"""
    rule = (await db.execute(select(AlertRule).where(AlertRule.id == rule_id))).scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "规则不存在")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(rule, field, value)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """删除告警规则。"""
    rule = (await db.execute(select(AlertRule).where(AlertRule.id == rule_id))).scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "规则不存在")
    await db.delete(rule)
    await db.commit()
    return {"ok": True}


@router.get("/events")
async def get_events(
    rule_id: int | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """获取告警事件列表。"""
    conditions = [True]
    if rule_id:
        conditions.append(AlertEvent.rule_id == rule_id)
    if status:
        conditions.append(AlertEvent.status == status)

    total_query = await db.execute(
        select(func.count(AlertEvent.id)).where(*conditions)
    )
    total = total_query.scalar() or 0

    events = (await db.execute(
        select(AlertEvent).where(*conditions)
        .order_by(AlertEvent.id.desc())
        .limit(limit).offset(offset)
    )).scalars().all()

    return {"items": events, "total": total}


class WebhookConfig(BaseModel):
    """Webhook 配置。"""
    url: str = ""
    type: str = "dingtalk"  # dingtalk / wecom / feishu


@router.get("/webhook")
async def get_webhook_config(
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """获取 Webhook 配置。"""
    config = (await db.execute(
        select(SystemConfig).where(SystemConfig.key == "alert_webhook")
    )).scalar_one_or_none()
    return config.value if config and config.value else {"url": "", "type": "dingtalk"}


@router.post("/webhook")
async def update_webhook_config(
    payload: WebhookConfig,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """更新 Webhook 配置。"""
    existing = (await db.execute(
        select(SystemConfig).where(SystemConfig.key == "alert_webhook")
    )).scalar_one_or_none()

    if existing:
        existing.value = payload.model_dump()
    else:
        db.add(SystemConfig(key="alert_webhook", value=payload.model_dump()))

    await db.commit()
    return {"message": "Webhook 配置已更新"}


@router.post("/webhook/test")
async def test_webhook(
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """测试 Webhook 连通性。"""
    from ...services.alert_service import AlertService

    config = (await db.execute(
        select(SystemConfig).where(SystemConfig.key == "alert_webhook")
    )).scalar_one_or_none()

    if not config or not config.value or not config.value.get("url"):
        raise HTTPException(status_code=400, detail="未配置 Webhook")

    svc = AlertService(db)
    test_rule = type('Rule', (), {
        'name': '测试告警',
        'metric': 'test',
        'condition': 'gte',
        'threshold': 0,
    })()

    await svc._send_webhook(test_rule, 0)
    return {"message": "测试消息已发送"}
