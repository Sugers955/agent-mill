"""多 Agent 编排 API — 支持 Agent 间协作和任务委托。"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from ..db.session import get_db
from ..db.models import Agent, AgentMessage, User
from ..deps import current_user

router = APIRouter(prefix="/api/orchestrator", tags=["orchestrator"])


class DelegateTaskRequest(BaseModel):
    to_agent_code: str
    task_description: str
    context: dict | None = None
    conversation_id: int | None = None


class QueryAgentRequest(BaseModel):
    to_agent_code: str
    question: str
    context: dict | None = None


@router.post("/delegate")
async def delegate_task(
    body: DelegateTaskRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    """委托任务给另一个 Agent。"""
    from ...services.agent_communication import AgentCommunicationService
    
    # 查找源 Agent（使用用户默认 Agent）
    source_agent = (await db.execute(
        select(Agent).where(Agent.is_default == True, Agent.enabled == True)
    )).scalar_one_or_none()
    
    if not source_agent:
        raise HTTPException(400, "未找到默认 Agent")
    
    # 查找目标 Agent
    target_agent = (await db.execute(
        select(Agent).where(Agent.code == body.to_agent_code, Agent.enabled == True)
    )).scalar_one_or_none()
    
    if not target_agent:
        raise HTTPException(404, f"Agent '{body.to_agent_code}' 不存在或已禁用")
    
    if source_agent.id == target_agent.id:
        raise HTTPException(400, "不能委托任务给自己")
    
    # 发送委托消息
    svc = AgentCommunicationService(db)
    msg_id = await svc.delegate_task(
        from_agent_id=source_agent.id,
        to_agent_id=target_agent.id,
        task_description=body.task_description,
        context=body.context,
        conversation_id=body.conversation_id,
    )
    
    return {
        "message_id": msg_id,
        "from_agent": source_agent.name,
        "to_agent": target_agent.name,
        "status": "delegated",
    }


@router.post("/query")
async def query_agent(
    body: QueryAgentRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    """向另一个 Agent 查询信息。"""
    from ...services.agent_communication import AgentCommunicationService
    
    # 查找源 Agent
    source_agent = (await db.execute(
        select(Agent).where(Agent.is_default == True, Agent.enabled == True)
    )).scalar_one_or_none()
    
    if not source_agent:
        raise HTTPException(400, "未找到默认 Agent")
    
    # 查找目标 Agent
    target_agent = (await db.execute(
        select(Agent).where(Agent.code == body.to_agent_code, Agent.enabled == True)
    )).scalar_one_or_none()
    
    if not target_agent:
        raise HTTPException(404, f"Agent '{body.to_agent_code}' 不存在或已禁用")
    
    # 发送查询消息
    svc = AgentCommunicationService(db)
    msg_id = await svc.send_message(
        from_agent_id=source_agent.id,
        to_agent_id=target_agent.id,
        message_type="query",
        content=body.question,
        context_json=body.context,
    )
    
    return {
        "message_id": msg_id,
        "from_agent": source_agent.name,
        "to_agent": target_agent.name,
        "status": "query_sent",
    }


@router.get("/messages")
async def get_messages(
    agent_id: int | None = None,
    status: str | None = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    """获取 Agent 间消息列表。"""
    query = select(AgentMessage)
    
    if agent_id:
        query = query.where(
            (AgentMessage.from_agent_id == agent_id) |
            (AgentMessage.to_agent_id == agent_id)
        )
    
    if status:
        query = query.where(AgentMessage.status == status)
    
    messages = list((await db.execute(
        query.order_by(desc(AgentMessage.created_at)).limit(limit)
    )).scalars().all())
    
    return {
        "items": [
            {
                "id": m.id,
                "from_agent_id": m.from_agent_id,
                "to_agent_id": m.to_agent_id,
                "message_type": m.message_type,
                "content": m.content,
                "status": m.status,
                "priority": m.priority,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
        "total": len(messages),
    }


@router.post("/messages/{message_id}/complete")
async def complete_message(
    message_id: int,
    result: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    """标记消息为已完成。"""
    from ...services.agent_communication import AgentCommunicationService
    
    svc = AgentCommunicationService(db)
    ok = await svc.complete_message(message_id, result)
    
    if not ok:
        raise HTTPException(404, "消息不存在")
    
    return {"status": "completed"}


@router.post("/messages/{message_id}/reply")
async def reply_message(
    message_id: int,
    content: str,
    result: dict | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    """回复一条消息。"""
    from ...services.agent_communication import AgentCommunicationService
    
    svc = AgentCommunicationService(db)
    try:
        reply_id = await svc.reply_to_message(message_id, content, result)
    except ValueError as e:
        raise HTTPException(404, str(e))
    
    return {"reply_id": reply_id, "status": "replied"}


@router.get("/available")
async def list_available_agents(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    """列出可用于协作的 Agent。"""
    agents = list((await db.execute(
        select(Agent).where(Agent.enabled == True).order_by(Agent.name)
    )).scalars().all())
    
    return [
        {
            "id": a.id,
            "code": a.code,
            "name": a.name,
            "description": a.description,
        }
        for a in agents
    ]


class RunMultiAgentTaskRequest(BaseModel):
    agents: list[str]
    task: str
    workflow: str = "sequential"  # sequential / parallel / map_reduce
    timeout: int = 300


@router.post("/run-task")
async def run_multi_agent_task(
    body: RunMultiAgentTaskRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    """运行多 Agent 协作任务。"""
    from ...services.orchestrator import Orchestrator
    
    orch = Orchestrator()
    result = await orch.run_multi_agent_task(
        task_config={
            "agents": body.agents,
            "task": body.task,
            "workflow": body.workflow,
            "timeout": body.timeout,
        },
        db=db,
    )
    return result


@router.get("/messages/pending")
async def get_pending_messages(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    """获取待处理消息。"""
    pending = list((await db.execute(
        select(AgentMessage)
        .where(AgentMessage.status == "pending")
        .order_by(desc(AgentMessage.priority), desc(AgentMessage.created_at))
        .limit(limit)
    )).scalars().all())
    
    return [
        {
            "id": m.id,
            "from_agent_id": m.from_agent_id,
            "to_agent_id": m.to_agent_id,
            "content": m.content,
            "message_type": m.message_type,
            "priority": m.priority,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in pending
    ]
