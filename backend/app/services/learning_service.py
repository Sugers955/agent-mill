"""Agent 自学习服务 — 基于用户反馈调整回复策略。"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class LearningService:
    """自学习服务类，用于分析反馈并自动应用改进。"""
    
    def __init__(self, db: AsyncSession = None):
        self.db = db
    
    async def analyze_and_apply(self) -> dict:
        """分析反馈并自动应用改进。
        
        1. 分析未处理反馈
        2. 对满意度低的 Agent 自动调整 system_prompt
        3. 标记已处理
        """
        from ..db.session import SessionLocal
        from ..db.models import Agent, MessageFeedback, Message
        
        # 1. 分析未处理反馈
        analysis_results = {}
        
        async with SessionLocal() as db:
            try:
                # 获取有反馈的 Agent
                from sqlalchemy import select as sa_select
                result = await db.execute(
                    sa_select(
                        MessageFeedback.agent_id,
                        func.avg(func.case(
                            (MessageFeedback.rating == "like", 1.0),
                            (MessageFeedback.rating == "dislike", -1.0),
                            else_=0.0
                        )).label('avg_rating'),
                        func.count(MessageFeedback.id).label('count')
                    ).where(
                        MessageFeedback.analyzed == False  # noqa: E712
                    ).group_by(MessageFeedback.agent_id)
                )
                agents_with_feedback = result.all()
                
                adjustments = []
                for item in agents_with_feedback:
                    if item.count >= 5 and item.avg_rating < 0.3:
                        agent_result = await db.execute(
                            sa_select(Agent).where(Agent.id == item.agent_id)
                        )
                        agent = agent_result.scalar_one_or_none()
                        if agent:
                            # 分析常见负面反馈
                            neg_result = await db.execute(
                                sa_select(MessageFeedback.reason).where(
                                    MessageFeedback.agent_id == item.agent_id,
                                    MessageFeedback.rating == "dislike",
                                    MessageFeedback.analyzed == False,  # noqa: E712
                                    MessageFeedback.reason.isnot(None),
                                    MessageFeedback.reason != ""
                                )
                            )
                            negative_feedbacks = neg_result.all()
                            
                            reasons = " ".join([r[0] for r in negative_feedbacks if r[0]])
                            if reasons:
                                suggestion = self._generate_prompt_suggestion(
                                    agent.system_prompt or "", reasons
                                )
                                if suggestion:
                                    adjustments.append({
                                        "agent_id": agent.id,
                                        "agent_code": agent.code,
                                        "old_prompt": agent.system_prompt,
                                        "suggestion": suggestion,
                                        "avg_rating": item.avg_rating,
                                        "feedback_count": item.count,
                                    })
                
                # 2. 标记已处理
                from sqlalchemy import update
                await db.execute(
                    update(MessageFeedback)
                    .where(MessageFeedback.analyzed == False)  # noqa: E712
                    .values(analyzed=True)
                )
                await db.commit()
                
                return {
                    "analyzed": sum(item.count for item in agents_with_feedback),
                    "adjustments": adjustments,
                }
            except Exception as e:
                logger.error("Learning analysis failed: %s", e)
                await db.rollback()
                return {"analyzed": 0, "adjustments": [], "error": str(e)}
    
    def _generate_prompt_suggestion(self, current_prompt: str, reasons: str) -> str | None:
        """基于负面反馈生成 system_prompt 改进建议。"""
        if not reasons:
            return None
        
        suggestions = []
        
        # 分析常见问题并生成建议
        if "太长" in reasons or "啰嗦" in reasons or "冗余" in reasons:
            suggestions.append("回复更简洁，避免重复内容")
        if "不准确" in reasons or "错误" in reasons or "虚假" in reasons:
            suggestions.append("加强事实核查，不确定时明确说明")
        if "不相关" in reasons or "答非所问" in reasons:
            suggestions.append("更精准理解用户意图，回答前确认理解问题")
        if "不友好" in reasons or "生硬" in reasons:
            suggestions.append("使用更友好、自然的语气")
        if "太专业" in reasons or "看不懂" in reasons:
            suggestions.append("使用通俗易懂的语言解释专业概念")
        
        if suggestions:
            return "；".join(suggestions)
        return None


async def analyze_feedback_batch(
    db: AsyncSession,
    agent_id: int,
    batch_size: int = 50,
) -> dict:
    """批量分析未处理的反馈，生成 Agent 策略建议。
    
    返回：
    - analyzed: 分析的反馈数量
    - suggestions: 策略建议
    """
    from ..db.models import MessageFeedback, Message
    
    # 获取未分析的反馈
    feedbacks = list((await db.execute(
        select(MessageFeedback)
        .where(
            MessageFeedback.agent_id == agent_id,
            MessageFeedback.analyzed == False,  # noqa: E712
        )
        .order_by(desc(MessageFeedback.created_at))
        .limit(batch_size)
    )).scalars().all())
    
    if not feedbacks:
        return {"analyzed": 0, "suggestions": {}}
    
    # 统计分析
    like_count = sum(1 for f in feedbacks if f.rating == "like")
    dislike_count = sum(1 for f in feedbacks if f.rating == "dislike")
    
    # 获取被点踩的消息内容，分析问题模式
    dislike_reasons = []
    for f in feedbacks:
        if f.rating == "dislike" and f.reason:
            dislike_reasons.append(f.reason)
    
    # 生成策略建议
    suggestions = {}
    
    if dislike_count > like_count:
        # 点踩多于点赞，需要调整
        suggestions["tone"] = "更友好、更详细"
        suggestions["detail_level"] = "增加解释深度"
    
    if dislike_reasons:
        # 分析点踩原因
        reasons_text = " ".join(dislike_reasons)
        if "太长" in reasons_text or "啰嗦" in reasons_text:
            suggestions["conciseness"] = "回复更简洁"
        if "不准确" in reasons_text or "错误" in reasons_text:
            suggestions["accuracy"] = "加强事实核查"
        if "不相关" in reasons_text:
            suggestions["relevance"] = "更精准理解用户意图"
    
    # 标记为已分析
    for f in feedbacks:
        f.analyzed = True
        f.analysis_result = {
            "batch_analyzed_at": datetime.now(timezone.utc).isoformat(),
            "suggestions": suggestions,
        }
    
    await db.commit()
    
    logger.info("Analyzed %d feedbacks for agent %d: %d likes, %d dislikes",
               len(feedbacks), agent_id, like_count, dislike_count)
    
    return {
        "analyzed": len(feedbacks),
        "suggestions": suggestions,
    }


async def get_agent_learning_stats(
    db: AsyncSession,
    agent_id: int,
) -> dict:
    """获取 Agent 的学习统计。"""
    from ..db.models import MessageFeedback
    
    # 总反馈数
    total = (await db.execute(
        select(func.count(MessageFeedback.id))
        .where(MessageFeedback.agent_id == agent_id)
    )).scalar() or 0
    
    # 点赞/点踩数
    likes = (await db.execute(
        select(func.count(MessageFeedback.id))
        .where(
            MessageFeedback.agent_id == agent_id,
            MessageFeedback.rating == "like",
        )
    )).scalar() or 0
    
    dislikes = (await db.execute(
        select(func.count(MessageFeedback.id))
        .where(
            MessageFeedback.agent_id == agent_id,
            MessageFeedback.rating == "dislike",
        )
    )).scalar() or 0
    
    # 最近反馈趋势（最近 7 天）
    from datetime import timedelta
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent_feedbacks = list((await db.execute(
        select(MessageFeedback)
        .where(
            MessageFeedback.agent_id == agent_id,
            MessageFeedback.created_at >= week_ago,
        )
        .order_by(desc(MessageFeedback.created_at))
    )).scalars().all())
    
    recent_likes = sum(1 for f in recent_feedbacks if f.rating == "like")
    recent_dislikes = sum(1 for f in recent_feedbacks if f.rating == "dislike")
    
    # 满意度
    satisfaction_rate = round(likes / total * 100, 1) if total > 0 else 0
    recent_satisfaction = round(recent_likes / (recent_likes + recent_dislikes) * 100, 1) if (recent_likes + recent_dislikes) > 0 else 0
    
    # 常见点踩原因
    recent_dislike_reasons = [f.reason for f in recent_feedbacks if f.rating == "dislike" and f.reason]
    common_reasons = {}
    for reason in recent_dislike_reasons:
        common_reasons[reason] = common_reasons.get(reason, 0) + 1
    sorted_reasons = sorted(common_reasons.items(), key=lambda x: x[1], reverse=True)[:5]
    
    return {
        "total": total,
        "likes": likes,
        "dislikes": dislikes,
        "satisfaction_rate": satisfaction_rate,
        "recent_7d": {
            "total": len(recent_feedbacks),
            "likes": recent_likes,
            "dislikes": recent_dislikes,
            "satisfaction_rate": recent_satisfaction,
        },
        "common_dislike_reasons": [{"reason": r, "count": c} for r, c in sorted_reasons],
    }


async def get_learning_suggestions(
    db: AsyncSession,
    agent_id: int,
) -> list[str]:
    """基于历史反馈生成具体的优化建议。"""
    stats = await get_agent_learning_stats(db, agent_id)
    suggestions = []
    
    if stats["total"] < 10:
        suggestions.append("反馈数据不足（<10条），继续收集更多反馈")
        return suggestions
    
    if stats["satisfaction_rate"] < 60:
        suggestions.append("整体满意度偏低（<60%），建议优化系统提示词或模型选择")
    
    if stats["recent_7d"]["satisfaction_rate"] < 50:
        suggestions.append("近期满意度下降（<50%），可能存在新问题需要排查")
    
    for item in stats["common_dislike_reasons"]:
        reason = item["reason"]
        count = item["count"]
        if count >= 3:
            suggestions.append(f"常见问题「{reason}」出现 {count} 次，建议针对性优化")
    
    if not suggestions:
        suggestions.append("反馈良好，保持当前策略")
    
    return suggestions
