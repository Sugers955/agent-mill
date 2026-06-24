"""告警规则评估服务 — 定时检查阈值并触发通知。"""
from __future__ import annotations
import logging
import httpx
from datetime import datetime, timedelta
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

METRIC_QUERIES = {
    "token_consumption": """
        SELECT COALESCE(SUM(tokens_in + tokens_out), 0) AS val
        FROM call_logs
        WHERE created_at >= NOW() - INTERVAL :window MINUTE
    """,
    "error_rate": """
        SELECT COALESCE(ROUND(
            SUM(CASE WHEN status != 'ok' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) * 100, 2
        ), 0) AS val
        FROM call_logs
        WHERE created_at >= NOW() - INTERVAL :window MINUTE
    """,
    "call_count": """
        SELECT COUNT(*) AS val
        FROM call_logs
        WHERE created_at >= NOW() - INTERVAL :window MINUTE
    """,
    "latency_p50": """
        SELECT COALESCE(ROUND(AVG(latency_ms)), 0) AS val
        FROM call_logs
        WHERE created_at >= NOW() - INTERVAL :window MINUTE
    """,
}

CONDITION_FUNCS = {
    "gte": lambda v, t: v >= t,
    "gt": lambda v, t: v > t,
    "lte": lambda v, t: v <= t,
    "lt": lambda v, t: v < t,
}


class AlertService:
    """告警规则评估引擎。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def evaluate_rules(self) -> list[dict]:
        """评估所有启用的规则，返回新触发的事件列表。"""
        from ..db.models import AlertRule, AlertEvent

        rules = (await self.db.execute(
            select(AlertRule).where(AlertRule.enabled == True)  # noqa: E712
        )).scalars().all()

        triggered = []
        for rule in rules:
            try:
                event = await self._evaluate_rule(rule)
                if event:
                    triggered.append(event)
            except Exception as e:
                logger.warning("Alert rule %s evaluation failed: %s", rule.id, e)

        return triggered

    async def _evaluate_rule(self, rule) -> dict | None:
        """评估单条规则。"""
        from ..db.models import AlertEvent

        if rule.cooldown_minutes > 0:
            recent = (await self.db.execute(
                select(AlertEvent).where(
                    AlertEvent.rule_id == rule.id,
                    AlertEvent.status == "firing",
                    AlertEvent.triggered_at > datetime.utcnow() - timedelta(minutes=rule.cooldown_minutes),
                )
            )).scalar_one_or_none()
            if recent:
                return None

        query_tpl = METRIC_QUERIES.get(rule.metric)
        if not query_tpl:
            return None

        sql = text(query_tpl)
        row = (await self.db.execute(sql, {"window": rule.window_minutes})).fetchone()
        current_value = float(row.val) if row else 0

        cond_fn = CONDITION_FUNCS.get(rule.condition)
        if not cond_fn or not cond_fn(current_value, rule.threshold):
            return None

        event = AlertEvent(
            rule_id=rule.id,
            metric_value=current_value,
            metric_detail={"window_minutes": rule.window_minutes, "threshold": rule.threshold},
            status="firing",
        )
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)

        logger.info("Alert triggered: rule=%s metric=%s value=%.2f threshold=%.2f",
                    rule.name, rule.metric, current_value, rule.threshold)

        await self._create_notification(event)
        await self._send_webhook(rule, current_value)

        return {"id": event.id, "rule_id": rule.id, "metric_value": current_value}

    async def _create_notification(self, event):
        """创建应用内通知。"""
        from ..db.models import Notification, AlertRule

        rule = (await self.db.execute(
            select(AlertRule).where(AlertRule.id == event.rule_id)
        )).scalar_one_or_none()
        if not rule:
            return

        admins = (await self.db.execute(
            text("SELECT id FROM users WHERE role_id IN (SELECT id FROM roles WHERE code = 'admin')")
        )).fetchall()

        for admin in admins:
            notif = Notification(
                user_id=admin.id,
                title=f"告警: {rule.name}",
                body=(
                    f"指标: {rule.metric}, "
                    f"当前值: {event.metric_value:.2f}, "
                    f"阈值: {rule.threshold}, "
                    f"条件: {rule.condition}"
                ),
                type="alert",
            )
            self.db.add(notif)

        await self.db.commit()

    async def _send_webhook(self, rule, alert_value: float):
        """发送 Webhook 通知（钉钉/企微/飞书）。"""
        from ..db.models import SystemConfig

        try:
            config_result = await self.db.execute(
                select(SystemConfig).where(SystemConfig.key == "alert_webhook")
            )
            config = config_result.scalar_one_or_none()

            if not config or not config.value:
                return

            webhook_url = config.value.get("url", "")
            webhook_type = config.value.get("type", "dingtalk")

            if not webhook_url:
                return

            message = self._build_webhook_message(rule, alert_value, webhook_type)

            async with httpx.AsyncClient(timeout=10) as client:
                if webhook_type == "dingtalk":
                    payload = {"msgtype": "markdown", "markdown": message}
                elif webhook_type == "wecom":
                    payload = {"msgtype": "markdown", "markdown": {"content": message}}
                elif webhook_type == "feishu":
                    payload = {"msg_type": "text", "content": {"text": message}}
                else:
                    return

                resp = await client.post(webhook_url, json=payload)
                if resp.status_code != 200:
                    logger.warning("Webhook 发送失败: %s %s", resp.status_code, resp.text)
        except Exception as e:
            logger.warning("Webhook 发送异常: %s", e)

    def _build_webhook_message(self, rule, alert_value: float, webhook_type: str) -> str:
        """构建 Webhook 消息。"""
        title = f"⚠️ Agent Mill 告警：{rule.name}"
        body = f"""
### {title}
- **规则**: {rule.name}
- **指标**: {rule.metric}
- **条件**: {rule.condition} {rule.threshold}
- **当前值**: {alert_value:.2f}
- **触发时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

        if webhook_type == "dingtalk":
            return f"# {title}\n{body}"
        elif webhook_type == "wecom":
            return f"## {title}\n{body}"
        else:
            return f"{title}\n{body}"
