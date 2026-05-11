"""Favorites API — the personal "Space" where users bookmark Q&A pairs.

All routes scope strictly to `current_user.id` — admins/operators cannot see
other users' favorites either. Snapshots (question + answer text + agent name
+ model code) are captured at favorite time so deletions to the source
conversation never strand a favorite.
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, desc
from ..db.session import get_db
from ..db.models import Favorite, Message, Conversation, Agent, Model, User
from ..deps import current_user
from ..schemas import FavoriteCreate, FavoriteUpdate, FavoriteOut, FavoritePage

router = APIRouter(prefix="/api/favorites", tags=["favorites"])


def _to_out(fav: Favorite) -> FavoriteOut:
    """Map ORM row → response schema (renames files_json → files)."""
    return FavoriteOut(
        id=fav.id,
        conversation_id=fav.conversation_id,
        message_id=fav.message_id,
        question_text=fav.question_text,
        answer_text=fav.answer_text,
        files=list(fav.files_json or []),
        agent_id=fav.agent_id,
        agent_name=fav.agent_name,
        model_code=fav.model_code,
        note=fav.note,
        created_at=fav.created_at,
    )


async def _snapshot_from_message(db: AsyncSession, user_id: int, message_id: int) -> dict:
    """Reconstruct question + answer + agent + model from a single message id.

    The favorited message must be an assistant message owned by the caller's
    conversation. The question is taken from the most-recent user message
    that came before it in the same conversation.
    """
    msg = (await db.execute(select(Message).where(Message.id == message_id))).scalar_one_or_none()
    if not msg:
        raise HTTPException(404, "消息不存在")
    if msg.role != "assistant":
        raise HTTPException(400, "只能收藏智能体的回答")

    conv = (await db.execute(
        select(Conversation).where(Conversation.id == msg.conversation_id, Conversation.user_id == user_id)
    )).scalar_one_or_none()
    if not conv:
        raise HTTPException(403, "无权访问该消息")

    # The matching question = most-recent prior user message in same conv.
    q_msg = (await db.execute(
        select(Message)
        .where(Message.conversation_id == conv.id,
               Message.role == "user",
               Message.id < msg.id)
        .order_by(desc(Message.id))
        .limit(1)
    )).scalar_one_or_none()

    answer = (msg.content_json or {}).get("text") or ""
    files = (msg.content_json or {}).get("files") or []
    if not isinstance(files, list):
        files = []
    question = ""
    if q_msg:
        question = (q_msg.content_json or {}).get("text") or ""

    agent_name = None
    model_code = None
    agent = (await db.execute(select(Agent).where(Agent.id == conv.agent_id))).scalar_one_or_none()
    if agent:
        agent_name = agent.name
        if agent.default_model_id:
            m = (await db.execute(select(Model).where(Model.id == agent.default_model_id))).scalar_one_or_none()
            if m:
                model_code = m.code

    return {
        "conversation_id": conv.id,
        "message_id": msg.id,
        "question_text": question,
        "answer_text": answer,
        "files_json": files,
        "agent_id": conv.agent_id,
        "agent_name": agent_name,
        "model_code": model_code,
    }


@router.post("", response_model=FavoriteOut)
async def create_favorite(
    payload: FavoriteCreate,
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    # Idempotency: if already favorited, return the existing row instead of 409.
    existing = (await db.execute(
        select(Favorite).where(Favorite.user_id == user.id, Favorite.message_id == payload.message_id)
    )).scalar_one_or_none()
    if existing:
        if payload.note is not None and payload.note != existing.note:
            existing.note = payload.note
            await db.commit()
            await db.refresh(existing)
        return _to_out(existing)

    snap = await _snapshot_from_message(db, user.id, payload.message_id)
    fav = Favorite(
        user_id=user.id,
        note=payload.note,
        **snap,
    )
    db.add(fav)
    await db.commit()
    await db.refresh(fav)
    return _to_out(fav)


@router.get("", response_model=FavoritePage)
async def list_favorites(
    q: str | None = Query(None),
    agent_id: int | None = Query(None),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    filters = [Favorite.user_id == user.id]
    if q:
        like = f"%{q.strip()}%"
        filters.append(or_(
            Favorite.question_text.ilike(like),
            Favorite.answer_text.ilike(like),
            Favorite.note.ilike(like),
        ))
    if agent_id is not None:
        filters.append(Favorite.agent_id == agent_id)

    total = (await db.execute(select(func.count(Favorite.id)).where(*filters))).scalar_one()
    rows = (await db.execute(
        select(Favorite).where(*filters)
        .order_by(desc(Favorite.created_at))
        .limit(limit).offset(offset)
    )).scalars().all()
    return FavoritePage(items=[_to_out(r) for r in rows], total=total)


@router.patch("/{fid}", response_model=FavoriteOut)
async def update_favorite(
    fid: int, payload: FavoriteUpdate,
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    fav = (await db.execute(
        select(Favorite).where(Favorite.id == fid, Favorite.user_id == user.id)
    )).scalar_one_or_none()
    if not fav:
        raise HTTPException(404, "收藏不存在")
    if payload.note is not None:
        fav.note = payload.note
    await db.commit()
    await db.refresh(fav)
    return _to_out(fav)


@router.delete("/{fid}")
async def delete_favorite(
    fid: int,
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    fav = (await db.execute(
        select(Favorite).where(Favorite.id == fid, Favorite.user_id == user.id)
    )).scalar_one_or_none()
    if not fav:
        raise HTTPException(404, "收藏不存在")
    await db.delete(fav)
    await db.commit()
    return {"ok": True}


@router.delete("/by-message/{message_id}")
async def delete_favorite_by_message(
    message_id: int,
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    fav = (await db.execute(
        select(Favorite).where(Favorite.user_id == user.id, Favorite.message_id == message_id)
    )).scalar_one_or_none()
    if not fav:
        raise HTTPException(404, "收藏不存在")
    await db.delete(fav)
    await db.commit()
    return {"ok": True}


@router.get("/check")
async def check_favorites(
    message_ids: str = Query(..., description="Comma-separated message ids"),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    """Bulk lookup: which of these message ids the caller has favorited.

    Returns a dict { "<message_id>": favorite_id } for hits only.
    """
    try:
        ids = [int(x) for x in (message_ids or "").split(",") if x.strip()]
    except ValueError:
        raise HTTPException(400, "message_ids 必须是逗号分隔的整数")
    if not ids:
        return {}
    rows = (await db.execute(
        select(Favorite.id, Favorite.message_id)
        .where(Favorite.user_id == user.id, Favorite.message_id.in_(ids))
    )).all()
    return {str(mid): fid for fid, mid in rows}
