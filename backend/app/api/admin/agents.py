from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
from ...db.session import get_db
from ...db.models import Agent, AgentSkill, AgentMCP, RoleAgentGrant
from ...deps import require_admin_or_operator
from ...services.audit import audit
from ...db.models import User
from ...schemas import AgentIn, AgentOut

router = APIRouter(prefix="/api/admin/agents", tags=["admin-agents"])


async def _to_out(db: AsyncSession, a: Agent) -> AgentOut:
    skill_ids = [r[0] for r in (await db.execute(select(AgentSkill.skill_id).where(AgentSkill.agent_id == a.id))).all()]
    mcp_ids = [r[0] for r in (await db.execute(select(AgentMCP.mcp_id).where(AgentMCP.agent_id == a.id))).all()]
    role_ids = [r[0] for r in (await db.execute(select(RoleAgentGrant.role_id).where(RoleAgentGrant.agent_id == a.id))).all()]
    out = AgentOut.model_validate(a, from_attributes=True)
    out.skill_ids = skill_ids
    out.mcp_ids = mcp_ids
    out.role_ids = role_ids
    return out


@router.get("", response_model=list[AgentOut])
async def list_agents(db: AsyncSession = Depends(get_db), _=Depends(require_admin_or_operator)):
    rows = (await db.execute(select(Agent).order_by(Agent.id))).scalars().all()
    return [await _to_out(db, a) for a in rows]


@router.get("/{aid}", response_model=AgentOut)
async def get_agent(aid: int, db: AsyncSession = Depends(get_db), _=Depends(require_admin_or_operator)):
    a = (await db.execute(select(Agent).where(Agent.id == aid))).scalar_one_or_none()
    if not a:
        raise HTTPException(404, "不存在")
    return await _to_out(db, a)


async def _set_relations(db: AsyncSession, agent_id: int, payload: AgentIn) -> None:
    await db.execute(delete(AgentSkill).where(AgentSkill.agent_id == agent_id))
    await db.execute(delete(AgentMCP).where(AgentMCP.agent_id == agent_id))
    await db.execute(delete(RoleAgentGrant).where(RoleAgentGrant.agent_id == agent_id))
    db.add_all([AgentSkill(agent_id=agent_id, skill_id=sid) for sid in payload.skill_ids])
    db.add_all([AgentMCP(agent_id=agent_id, mcp_id=mid) for mid in payload.mcp_ids])
    db.add_all([RoleAgentGrant(role_id=rid, agent_id=agent_id) for rid in payload.role_ids])


@router.post("", response_model=AgentOut)
async def create_agent(payload: AgentIn, db: AsyncSession = Depends(get_db), actor: User = Depends(require_admin_or_operator)):
    if (await db.execute(select(Agent).where(Agent.code == payload.code))).scalar_one_or_none():
        raise HTTPException(400, "code 已存在")
    if payload.is_default:
        await db.execute(update(Agent).values(is_default=False))
    data = payload.model_dump(exclude={"skill_ids", "mcp_ids", "role_ids"})
    a = Agent(**data)
    db.add(a)
    await db.flush()
    await _set_relations(db, a.id, payload)
    await audit(db, actor.id, "agent.create", target_type="agent", target_id=None)
    await db.commit(); await db.refresh(a)
    return await _to_out(db, a)


@router.patch("/{aid}", response_model=AgentOut)
async def update_agent(aid: int, payload: AgentIn, db: AsyncSession = Depends(get_db), actor: User = Depends(require_admin_or_operator)):
    a = (await db.execute(select(Agent).where(Agent.id == aid))).scalar_one_or_none()
    if not a:
        raise HTTPException(404, "不存在")
    if payload.is_default:
        await db.execute(update(Agent).where(Agent.id != aid).values(is_default=False))
    for k, v in payload.model_dump(exclude={"skill_ids", "mcp_ids", "role_ids"}).items():
        setattr(a, k, v)
    await _set_relations(db, a.id, payload)
    await audit(db, actor.id, "agent.update", target_type="agent", target_id=a.id)
    await db.commit(); await db.refresh(a)
    return await _to_out(db, a)


@router.delete("/{aid}")
async def delete_agent(aid: int, db: AsyncSession = Depends(get_db), actor: User = Depends(require_admin_or_operator)):
    a = (await db.execute(select(Agent).where(Agent.id == aid))).scalar_one_or_none()
    if not a:
        raise HTTPException(404, "不存在")
    await audit(db, actor.id, "agent.delete", target_type="agent", target_id=a.id)
    await db.delete(a); await db.commit()
    return {"ok": True}
