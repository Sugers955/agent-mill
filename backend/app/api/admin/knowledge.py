"""知识库 API — 知识库/文档/检索 CRUD。"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ...db.session import get_db
from ...db.models import User, KnowledgeBase, KBDocument, KBChunk, UploadedFile
from ...deps import require_admin_or_operator
from ...services.knowledge_service import KnowledgeService
from pydantic import BaseModel

router = APIRouter(prefix="/api/admin/knowledge", tags=["admin"])


class KBCreate(BaseModel):
    name: str
    description: str | None = None


class SearchIn(BaseModel):
    kb_id: int
    query: str
    top_k: int = 5


@router.get("/bases")
async def list_kb(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_or_operator),
):
    rows = (await db.execute(
        select(KnowledgeBase).order_by(KnowledgeBase.id.desc())
    )).scalars().all()
    return rows


@router.post("/bases")
async def create_kb(
    payload: KBCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_or_operator),
):
    kb = KnowledgeBase(name=payload.name, description=payload.description, owner_id=user.id)
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    return kb


@router.delete("/bases/{kb_id}")
async def delete_kb(
    kb_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_or_operator),
):
    kb = (await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))).scalar_one_or_none()
    if not kb:
        raise HTTPException(404)
    
    # operator 角色需要审批
    from ..operation_approvals import create_approval_internal
    
    db_user = (await db.execute(select(User).where(User.id == user.id))).scalar_one_or_none()
    if db_user and db_user.role and db_user.role.code == "operator":
        approval = await create_approval_internal(
            db=db,
            user=user,
            operation_type="delete_knowledge_base",
            target_id=kb.id,
            target_name=kb.name,
            detail_json={"kb_name": kb.name, "document_count": kb.document_count},
        )
        if approval.status == "pending":
            return {"message": "已提交审批，等待管理员批准", "approval_id": approval.id}
    
    # admin 直接执行
    await db.delete(kb)
    await db.commit()
    return {"ok": True}


@router.get("/bases/{kb_id}/documents")
async def list_docs(
    kb_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_or_operator),
):
    rows = (await db.execute(
        select(KBDocument).where(KBDocument.kb_id == kb_id).order_by(KBDocument.id.desc())
    )).scalars().all()
    return rows


@router.post("/bases/{kb_id}/documents")
async def add_document(
    kb_id: int,
    file_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_or_operator),
):
    kb = (await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))).scalar_one_or_none()
    if not kb:
        raise HTTPException(404, "知识库不存在")
    file = (await db.execute(select(UploadedFile).where(UploadedFile.id == file_id))).scalar_one_or_none()
    if not file:
        raise HTTPException(404, "文件不存在")

    doc = KBDocument(kb_id=kb_id, file_id=file_id, title=file.name, status="pending")
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    if file.parse_status == "done" and file.parsed_markdown:
        svc = KnowledgeService(db)
        await svc.embed_document(doc.id, file.parsed_markdown)

    return doc


@router.post("/search")
async def search_kb(
    payload: SearchIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_or_operator),
):
    svc = KnowledgeService(db)
    results = await svc.search(payload.kb_id, payload.query, payload.top_k)
    return {"results": results}
