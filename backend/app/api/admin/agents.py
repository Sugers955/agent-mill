from __future__ import annotations
import os
import uuid
from pathlib import Path
import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update, func
from ...db.session import get_db
from ...db.models import Agent, AgentSkill, AgentMCP, AgentPack, RoleAgentGrant, SolutionPack, Model
from ...deps import require_admin_or_operator
from ...services.audit import audit
from ...db.models import User
from ...schemas import AgentIn, AgentOut
from ...core.config import settings

router = APIRouter(prefix="/api/admin/agents", tags=["admin-agents"])


async def _to_out(db: AsyncSession, a: Agent) -> AgentOut:
    skill_ids = [r[0] for r in (await db.execute(select(AgentSkill.skill_id).where(AgentSkill.agent_id == a.id))).all()]
    mcp_ids = [r[0] for r in (await db.execute(select(AgentMCP.mcp_id).where(AgentMCP.agent_id == a.id))).all()]
    pack_ids = [r[0] for r in (await db.execute(select(AgentPack.pack_id).where(AgentPack.agent_id == a.id))).all()]
    role_ids = [r[0] for r in (await db.execute(select(RoleAgentGrant.role_id).where(RoleAgentGrant.agent_id == a.id))).all()]
    out = AgentOut.model_validate(a, from_attributes=True)
    out.skill_ids = skill_ids
    out.mcp_ids = mcp_ids
    out.pack_ids = pack_ids
    out.role_ids = role_ids
    return out


@router.get("")
async def list_agents(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin_or_operator),
):
    total = (await db.execute(select(func.count(Agent.id)))).scalar_one()
    rows = (await db.execute(
        select(Agent).order_by(Agent.id).limit(limit).offset(offset)
    )).scalars().all()
    items = [await _to_out(db, a) for a in rows]
    return {"items": items, "total": total}


@router.get("/{aid}", response_model=AgentOut)
async def get_agent(aid: int, db: AsyncSession = Depends(get_db), _=Depends(require_admin_or_operator)):
    a = (await db.execute(select(Agent).where(Agent.id == aid))).scalar_one_or_none()
    if not a:
        raise HTTPException(404, "不存在")
    return await _to_out(db, a)


async def _set_relations(db: AsyncSession, agent_id: int, payload: AgentIn) -> None:
    await db.execute(delete(AgentSkill).where(AgentSkill.agent_id == agent_id))
    await db.execute(delete(AgentMCP).where(AgentMCP.agent_id == agent_id))
    await db.execute(delete(AgentPack).where(AgentPack.agent_id == agent_id))
    await db.execute(delete(RoleAgentGrant).where(RoleAgentGrant.agent_id == agent_id))
    db.add_all([AgentSkill(agent_id=agent_id, skill_id=sid) for sid in payload.skill_ids])
    db.add_all([AgentMCP(agent_id=agent_id, mcp_id=mid) for mid in payload.mcp_ids])
    db.add_all([AgentPack(agent_id=agent_id, pack_id=pid) for pid in payload.pack_ids])
    db.add_all([RoleAgentGrant(role_id=rid, agent_id=agent_id) for rid in payload.role_ids])


@router.post("", response_model=AgentOut)
async def create_agent(payload: AgentIn, db: AsyncSession = Depends(get_db), actor: User = Depends(require_admin_or_operator)):
    if (await db.execute(select(Agent).where(Agent.code == payload.code))).scalar_one_or_none():
        raise HTTPException(400, "code 已存在")
    if payload.is_default:
        await db.execute(update(Agent).values(is_default=False))
    data = payload.model_dump(exclude={"skill_ids", "mcp_ids", "pack_ids", "role_ids"})
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
    for k, v in payload.model_dump(exclude={"skill_ids", "mcp_ids", "pack_ids", "role_ids"}).items():
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
    # operator 角色需要审批；admin 直接执行
    if actor.role.code != "admin":
        from ..operation_approvals import create_approval_internal
        approval = await create_approval_internal(db, actor, "delete_agent", target_id=aid, target_name=a.name,
                                                     reason=f"删除数字员工: {a.name}")
        return {"requires_approval": True, "approval_id": approval.id}
    await audit(db, actor.id, "agent.delete", target_type="agent", target_id=a.id)
    await db.delete(a); await db.commit()
    return {"ok": True}


@router.post("/{aid}/icon")
async def upload_agent_icon(
    aid: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_admin_or_operator),
):
    a = (await db.execute(select(Agent).where(Agent.id == aid))).scalar_one_or_none()
    if not a:
        raise HTTPException(404, "智能体不存在")

    # Validate file type
    allowed_types = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(400, "只支持 JPG/PNG/GIF/WebP 图片")

    # Validate file size (2MB max)
    max_size = 2 * 1024 * 1024
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(400, "图片大小不能超过 2MB")

    # Save icon
    root = Path(settings.UPLOADS_DIR) / "icons" / "agents"
    root.mkdir(parents=True, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1].lower() or ".png"
    saved_name = f"{uuid.uuid4().hex}{ext}"
    saved_path = root / saved_name

    async with aiofiles.open(saved_path, "wb") as f:
        await f.write(content)

    # Update agent icon_url
    icon_url = f"/api/files/icons/agents/{saved_name}"
    a.icon_url = icon_url
    await audit(db, actor.id, "agent.update_icon", target_type="agent", target_id=a.id)
    await db.commit()

    return {"ok": True, "icon_url": icon_url}


# ── AI polish: refine description / system_prompt ──────────────────────────

class PolishIn(BaseModel):
    kind: str                # "description" | "system_prompt"
    text: str                # original text (may be empty)
    agent_name: str | None = None
    model_id: int | None = None   # which model to use; falls back to any configured


_DESCRIPTION_INSTRUCTION = (
    "你是资深产品经理，帮用户把智能体的「描述」润色得清晰、专业、易懂。"
    "要求：\n"
    "1. 用 1 句话概括这个智能体是做什么的，语言自然、突出亮点；\n"
    "2. 然后换行，给出正好 2 个「示例问题」，用 '- ' 开头，便于用户一眼看懂怎么用；\n"
    "3. 整段不超过 120 字，中文输出；不要出现 Markdown 标题、不要加引号、不要写「描述：」之类的前缀；\n"
    "4. 示例问题要具体可操作，贴合这个智能体的主要能力。"
)


_SYSTEM_PROMPT_INSTRUCTION = (
    "你是资深 Prompt 工程师，帮用户把一个智能体的 System Prompt 润色得更专业、结构化。"
    "要求：\n"
    "1. 用清晰的段落或要点分层（角色定位 / 能力范围 / 回答风格 / 约束）；\n"
    "2. 保留原意，不要发明用户没提过的具体业务规则；\n"
    "3. 中文输出；可以用 Markdown 轻量标记（- 列表），但不要整篇都是 #### 标题；\n"
    "4. 不要写多余的寒暄或解释，直接给最终 prompt 文本。"
)


@router.post("/polish")
async def polish_text(payload: PolishIn,
                      db: AsyncSession = Depends(get_db),
                      _: User = Depends(require_admin_or_operator)):
    kind = (payload.kind or "").strip().lower()
    if kind not in ("description", "system_prompt"):
        raise HTTPException(400, "kind 必须是 description 或 system_prompt")

    # Pick a model: explicit → any configured with API key
    if payload.model_id:
        m = (await db.execute(select(Model).where(Model.id == payload.model_id))).scalar_one_or_none()
    else:
        m = (await db.execute(
            select(Model).where(Model.api_key_enc.isnot(None)).order_by(Model.id)
        )).scalars().first()
    if not m:
        raise HTTPException(400, "未配置可用模型，无法润色")
    if not m.api_key_enc:
        raise HTTPException(400, "所选模型未配置 API Key")

    from ...core.crypto import decrypt_str
    api_key = decrypt_str(m.api_key_enc)

    instruction = _DESCRIPTION_INSTRUCTION if kind == "description" else _SYSTEM_PROMPT_INSTRUCTION
    user_block = (payload.text or "(用户尚未填写，请根据智能体名称合理生成)").strip()
    name_hint = f"智能体名称：{payload.agent_name.strip()}\n\n" if payload.agent_name else ""
    user_message = f"{name_hint}原文：\n{user_block}\n\n请输出润色后的最终文本，不要任何额外解释。"

    try:
        if m.provider == "anthropic":
            try:
                from anthropic import AsyncAnthropic  # type: ignore
            except ImportError:
                raise HTTPException(400, "anthropic SDK 未安装")
            kwargs = {"api_key": api_key}
            if m.base_url:
                kwargs["base_url"] = m.base_url
            client = AsyncAnthropic(**kwargs)
            resp = await client.messages.create(
                model=m.model_id, max_tokens=4000,
                system=instruction,
                messages=[{"role": "user", "content": user_message}],
            )
            text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
            finish_reason = getattr(resp, "stop_reason", "")
        else:
            from openai import AsyncOpenAI
            from ...runtime.agent_runner import AgentRunner
            base_url = m.base_url or AgentRunner.PROVIDER_BASE_URL.get(m.provider.lower())
            base_url = AgentRunner.normalize_base_url(base_url)
            client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            create_kwargs: dict = {
                "model": m.model_id, "max_tokens": 4000,
                "messages": [
                    {"role": "system", "content": instruction},
                    # `/no_think` is a qwen3 directive that skips the reasoning
                    # phase. Harmless on other providers (treated as plain text).
                    {"role": "user", "content": user_message + "\n/no_think"},
                ],
            }
            if m.extra_params_json:
                create_kwargs["extra_body"] = m.extra_params_json
            resp = await client.chat.completions.create(**create_kwargs)
            choice = resp.choices[0] if resp.choices else None
            msg = choice.message if choice else None
            text = (msg.content if msg else "") or ""
            # Some providers (DeepSeek-R1, qwen-thinking) put the answer in
            # reasoning_content; fall back to that if main content is empty.
            if not text and msg is not None:
                text = getattr(msg, "reasoning_content", "") or ""
            finish_reason = getattr(choice, "finish_reason", "")

        # Strip leaked reasoning blocks like <think>...</think> that some qwen
        # variants embed inline despite enable_thinking=False.
        import re as _re
        text = _re.sub(r"<think>[\s\S]*?</think>\s*", "", text or "", flags=_re.IGNORECASE).strip()

        if not text:
            hint = (
                "（上下文被推理过程消耗完了，请换一个非 reasoning 模型重试，"
                "或在该智能体配置里把默认模型换成普通对话模型）"
                if finish_reason == "length"
                else "（模型未返回内容，请检查模型配置或换一个模型）"
            )
            raise HTTPException(400, f"润色返回为空 {hint}")
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"润色失败: {e}")

    return {"ok": True, "text": text}
