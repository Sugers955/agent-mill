"""播种演示对话数据"""
from __future__ import annotations
import random
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Conversation, Message, CallLog, User, Agent, Model
from .session import SessionLocal


# 模拟对话内容
SAMPLE_CONVERSATIONS = [
    {
        "agent_code": "office-assistant",
        "title": "处理今日邮件摘要",
        "messages": [
            {"role": "user", "content": "帮我整理一下今天的重要邮件"},
            {"role": "assistant", "content": "好的，我来帮你整理今日重要邮件。根据扫描结果，今天共收到 23 封邮件，其中 5 封需要优先处理：\n\n1. **会议通知** - 明天下午2点产品评审会\n2. **客户反馈** - A客户对方案的修改意见\n3. **审批请求** - 市场活动预算申请\n4. **项目更新** - Q2 进度报告\n5. **HR通知** - 本月团建安排"},
        ],
    },
    {
        "agent_code": "finance-advisor",
        "title": "Q2 预算分析报告",
        "messages": [
            {"role": "user", "content": "帮我做一份Q2的预算分析报告"},
            {"role": "assistant", "content": "我来为你生成 Q2 预算分析报告。\n\n**Q2 预算执行概况：**\n- 总预算：500万元\n- 已执行：320万元（64%）\n- 剩余：180万元\n\n**各部门执行情况：**\n| 部门 | 预算 | 执行 | 执行率 |\n|------|------|------|--------|\n| 市场部 | 150万 | 110万 | 73% |\n| 研发部 | 200万 | 128万 | 64% |\n| 销售部 | 100万 | 62万 | 62% |\n| 行政部 | 50万 | 20万 | 40% |\n\n**建议：**\n1. 市场部执行率偏高，需控制Q3支出\n2. 行政部执行率偏低，建议加快采购进度"},
        ],
    },
    {
        "agent_code": "hr-manager",
        "title": "招聘需求汇总",
        "messages": [
            {"role": "user", "content": "汇总一下本月的招聘需求"},
            {"role": "assistant", "content": "本月招聘需求汇总如下：\n\n**新增岗位：**\n1. 高级前端工程师 - 研发部 - 2人\n2. 产品经理 - 产品部 - 1人\n3. 销售经理 - 华东区 - 1人\n\n**进度更新：**\n- 已面试：12人\n- 待面试：5人\n- 已发offer：2人\n- 已入职：1人\n\n**关键提醒：**\n- 高级前端工程师岗位已挂出30天，建议调整薪资范围\n- 产品经理岗位候选人质量较高，建议尽快安排终面"},
        ],
    },
    {
        "agent_code": "marketing-manager",
        "title": "618 活动方案评审",
        "messages": [
            {"role": "user", "content": "618活动方案准备得怎么样了？"},
            {"role": "assistant", "content": "618 活动方案进展汇报：\n\n**方案状态：** 已完成初稿，待评审\n\n**核心策略：**\n1. 主题：年中大促，全场5折起\n2. 时间：6月16日-6月18日\n3. 渠道：小程序 + APP + 公众号\n\n**预算分配：**\n- 广告投放：30万\n- KOL合作：15万\n- 优惠补贴：50万\n- 物料制作：5万\n\n**风险点：**\n- 竞品同期可能有更大力度促销\n- 库存需提前备货"},
        ],
    },
    {
        "agent_code": "expense-assistant",
        "title": "差旅报销整理",
        "messages": [
            {"role": "user", "content": "帮我整理上周出差的报销材料"},
            {"role": "assistant", "content": "我来帮你整理上周出差（6月9日-6月13日，上海）的报销材料：\n\n**交通费用：**\n- 机票：1,280元\n- 市内打车：356元\n- 地铁：45元\n\n**住宿费用：**\n- 酒店（4晚）：2,400元\n\n**其他费用：**\n- 餐饮补贴：400元\n- 会议材料打印：85元\n\n**合计：4,566元**\n\n已为你生成报销单，发票已关联。请确认后提交审批。"},
        ],
    },
]


async def seed_conversations():
    """播种演示对话数据"""
    async with SessionLocal() as db:
        # 获取用户和智能体
        users = (await db.execute(select(User))).scalars().all()
        agents = (await db.execute(select(Agent))).scalars().all()
        models = (await db.execute(select(Model))).scalars().all()

        agent_map = {a.code: a for a in agents}
        model = models[0] if models else None

        # 检查是否已有对话
        existing = (await db.execute(select(Conversation))).scalars().all()
        if existing:
            return {"conversations": 0, "messages": 0}

        now = datetime.now(timezone.utc)
        conv_count = 0
        msg_count = 0

        for i, conv_data in enumerate(SAMPLE_CONVERSATIONS):
            agent = agent_map.get(conv_data["agent_code"])
            if not agent:
                continue

            # 随机选择用户
            user = random.choice(users)

            # 创建对话（时间分布在最近7天内）
            conv_time = now - timedelta(days=random.randint(0, 6), hours=random.randint(0, 23))
            conv = Conversation(
                user_id=user.id,
                agent_id=agent.id,
                title=conv_data["title"],
                created_at=conv_time,
                updated_at=conv_time,
            )
            db.add(conv)
            await db.flush()
            conv_count += 1

            # 创建消息
            for j, msg in enumerate(conv_data["messages"]):
                msg_time = conv_time + timedelta(minutes=j * 2)
                message = Message(
                    conversation_id=conv.id,
                    role=msg["role"],
                    content_json={"text": msg["content"]},
                    tokens_in=random.randint(100, 500) if msg["role"] == "user" else 0,
                    tokens_out=random.randint(500, 2000) if msg["role"] == "assistant" else 0,
                    created_at=msg_time,
                )
                db.add(message)
                msg_count += 1

            # 创建 call_log
            call_log = CallLog(
                user_id=user.id,
                agent_id=agent.id,
                conversation_id=conv.id,
                model_id=model.id if model else None,
                tokens_in=random.randint(200, 1500),
                tokens_out=random.randint(500, 3000),
                latency_ms=random.randint(1000, 5000),
                status="ok",
                created_at=conv_time,
            )
            db.add(call_log)

        await db.commit()
        return {"conversations": conv_count, "messages": msg_count}
