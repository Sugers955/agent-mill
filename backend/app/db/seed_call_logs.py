"""播种演示统计数据 — 30天 call_logs"""
from __future__ import annotations
import random
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .models import CallLog, User, Agent, Model
from .session import SessionLocal


async def seed_call_logs():
    """播种30天的模拟统计数据"""
    async with SessionLocal() as db:
        # 检查是否已有足够数据
        count = (await db.execute(select(func.count(CallLog.id)))).scalar()
        if count and count > 50:
            return {"call_logs": 0, "note": "已存在足够数据"}

        users = (await db.execute(select(User))).scalars().all()
        agents = (await db.execute(select(Agent))).scalars().all()
        models = (await db.execute(select(Model))).scalars().all()

        if not users or not agents or not models:
            return {"call_logs": 0, "note": "缺少基础数据"}

        now = datetime.now(timezone.utc)
        log_count = 0

        # 生成30天数据
        for day_offset in range(30):
            day = now - timedelta(days=day_offset)
            # 每天 10-30 条记录
            daily_count = random.randint(10, 30)

            for _ in range(daily_count):
                user = random.choice(users)
                agent = random.choice(agents)
                model = random.choice(models)

                # 随机时间
                hour = random.randint(8, 22)
                minute = random.randint(0, 59)
                log_time = day.replace(hour=hour, minute=minute, second=0, microsecond=0)

                log = CallLog(
                    user_id=user.id,
                    agent_id=agent.id,
                    model_id=model.id,
                    tokens_in=random.randint(200, 3000),
                    tokens_out=random.randint(500, 8000),
                    latency_ms=random.randint(800, 6000),
                    status="ok",
                    created_at=log_time,
                )
                db.add(log)
                log_count += 1

        await db.commit()
        return {"call_logs": log_count}
