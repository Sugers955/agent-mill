"""记忆自动提取服务 — 对话结束后提取关键信息存入持久记忆。"""
from __future__ import annotations
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# 提取记忆的 prompt 模板
_EXTRACT_PROMPT = """分析以下对话，提取用户的关键信息。只提取明确表达的偏好、事实、决策。

对话内容：
{conversation}

请以 JSON 数组格式返回，每个元素包含：
- memory_type: "preference"（偏好）/ "fact"（事实）/ "decision"（决策）/ "context"（上下文）
- content: 简洁描述（50字以内）
- importance: 0.0-1.0（重要性）

如果对话中没有值得记住的信息，返回空数组 []

示例：
[
  {"memory_type": "preference", "content": "用户偏好使用 Python 进行数据分析", "importance": 0.7},
  {"memory_type": "fact", "content": "用户是产品经理，负责企业级 SaaS 产品", "importance": 0.8}
]

只返回 JSON，不要其他文字。"""


async def extract_memories_from_conversation(
    db: AsyncSession,
    *,
    agent_id: int,
    user_id: int,
    conversation_id: int,
    messages: list[dict],
    model_id: int | None = None,
) -> int:
    """从对话中提取记忆并保存。返回提取的记忆数量。
    
    设计原则：
    - 只在对话有实质内容时提取（至少 2 轮 user 消息）
    - 使用 LLM 提取，避免规则匹配的局限性
    - 失败静默处理，不影响对话流程
    """
    try:
        # 过滤出 user 消息，检查是否有足够内容
        user_messages = [m for m in messages if m.get("role") == "user"]
        if len(user_messages) < 2:
            return 0
        
        # 构建对话摘要（只取最近 10 轮，避免 token 过多）
        recent_messages = messages[-20:]  # 最近 20 条
        conversation_text = ""
        for msg in recent_messages:
            role = msg.get("role", "")
            content = msg.get("content_json", {})
            if isinstance(content, dict):
                text = content.get("text", "")
            else:
                text = str(content)
            if text:
                conversation_text += f"{role}: {text[:500]}\n\n"
        
        if not conversation_text.strip():
            return 0
        
        # 调用 LLM 提取记忆
        from ..core.config import settings
        from ..db.models import Model
        
        # 获取模型
        if model_id:
            model = (await db.execute(
                select(Model).where(Model.id == model_id)
            )).scalar_one_or_none()
        else:
            model = None
        
        if not model:
            # 没有模型配置，跳过提取
            return 0
        
        # 使用 OpenAI 兼容接口提取
        import httpx
        prompt = _EXTRACT_PROMPT.format(conversation=conversation_text[:3000])
        
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{model.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {model.api_key}"},
                json={
                    "model": model.model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 1000,
                },
            )
            resp.raise_for_status()
            result = resp.json()
        
        # 解析提取结果
        content = result["choices"][0]["message"]["content"]
        # 尝试提取 JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        memories_data = json.loads(content.strip())
        if not isinstance(memories_data, list):
            return 0
        
        # 保存记忆
        from .memory_service import MemoryService
        memory_svc = MemoryService(db)
        
        saved_count = 0
        for item in memories_data:
            if not isinstance(item, dict):
                continue
            memory_type = item.get("memory_type", "context")
            mem_content = item.get("content", "")
            importance = float(item.get("importance", 0.5))
            
            if not mem_content or len(mem_content) < 10:
                continue
            
            # 限制 importance 范围
            importance = max(0.0, min(1.0, importance))
            
            await memory_svc.save_memory(
                agent_id=agent_id,
                user_id=user_id,
                memory_type=memory_type,
                content=mem_content,
                importance=importance,
                source_conversation_id=conversation_id,
            )
            saved_count += 1
        
        logger.info("Extracted %d memories from conversation %d", saved_count, conversation_id)
        return saved_count
        
    except Exception as e:
        # 记忆提取失败不应影响对话
        logger.warning("Memory extraction failed: %s", e)
        return 0
