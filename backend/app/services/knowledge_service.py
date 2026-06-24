"""知识库服务 — 文档分块、Embedding、ZVec 向量检索。"""
# ponytail: ZVec 是嵌入式向量库，每个知识库一个独立集合目录。
# 百亿级规模才需要考虑独立向量服务（Qdrant/Milvus）。
from __future__ import annotations
import os
import logging
import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.crypto import decrypt_str
from ..core.config import settings

logger = logging.getLogger(__name__)

VECTOR_STORAGE = os.path.join(settings.STORAGE_ROOT, "vectors")
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def chunk_text(text: str) -> list[str]:
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end])
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def _get_collection_path(kb_id: int) -> str:
    return os.path.join(VECTOR_STORAGE, str(kb_id))


def _collection_exists(kb_id: int) -> bool:
    coll_path = _get_collection_path(kb_id)
    import glob
    return len(glob.glob(os.path.join(coll_path, "manifest*"))) > 0


class KnowledgeService:
    """知识库服务——分块、Embedding、ZVec 检索。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_embedding_model(self) -> tuple[str, str] | None:
        row = (await self.db.execute(
            text("SELECT base_url, api_key_enc FROM models WHERE provider = 'openai-compatible' AND enabled = 1 LIMIT 1")
        )).fetchone()
        if not row:
            row = (await self.db.execute(
                text("SELECT base_url, api_key_enc FROM models WHERE enabled = 1 LIMIT 1")
            )).fetchone()
        if not row:
            return None
        base_url = row.base_url or "https://api.openai.com/v1"
        api_key = decrypt_str(row.api_key_enc) if row.api_key_enc else ""
        return base_url, api_key

    async def embed(self, text: str) -> list[float]:
        model_info = await self._get_embedding_model()
        if not model_info:
            raise ValueError(
                "未配置 Embedding 模型。请在「模型配置」中设置 OpenAI 兼容的 API Key 和 embedding_model，"
                "否则知识库无法进行语义搜索。"
            )
        base_url, api_key = model_info
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{base_url}/embeddings",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": "text-embedding-3-small", "input": text},
            )
            r.raise_for_status()
            return r.json()["data"][0]["embedding"]

    async def embed_document(self, doc_id: int, content: str) -> dict:
        """为文档分块 → 生成 Embedding → 存入 MySQL + ZVec。
        
        Returns:
            dict: 包含 chunks, status, error, embedding_warning 字段
        """
        import zvec
        from ..db.models import KBChunk, KBDocument, KnowledgeBase

        doc = (await self.db.execute(select(KBDocument).where(KBDocument.id == doc_id))).scalar_one()
        chunks = chunk_text(content)
        results = []
        embedding_warning = None

        # 尝试生成 embedding，失败时不静默降级
        try:
            vectors = await self._embed_batch(chunks)
        except Exception as e:
            logger.error("Embedding 生成失败: %s", e)
            return {
                "chunks": len(chunks),
                "status": "error",
                "error": f"Embedding 生成失败: {str(e)}。知识库搜索将不可用。",
                "embedding_warning": None,
            }

        # 打开 ZVec 集合
        coll_path = _get_collection_path(doc.kb_id)
        vec_dim = 1536  # text-embedding-3-small

        if _collection_exists(doc.kb_id):
            coll = zvec.open(coll_path)
        else:
            schema = zvec.CollectionSchema(
                name=f"kb_{doc.kb_id}",
                vectors=zvec.VectorSchema("embedding", zvec.DataType.VECTOR_FP32, vec_dim),
            )
            coll = zvec.create_and_open(path=coll_path, schema=schema)

        for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
            row = KBChunk(
                document_id=doc_id,
                kb_id=doc.kb_id,
                content=chunk,
                chunk_index=i,
            )
            self.db.add(row)
            await self.db.flush()

            coll.insert(zvec.Doc(
                id=str(row.id),
                vectors={"embedding": vec},
            ))
            results.append({"index": i, "size": len(chunk)})

        doc.status = "ready"
        doc.chunk_count = len(chunks)
        doc.char_count = len(content)

        kb = (await self.db.execute(select(KnowledgeBase).where(KnowledgeBase.id == doc.kb_id))).scalar_one()
        ready_count = (await self.db.execute(
            select(KBDocument).where(KBDocument.kb_id == doc.kb_id, KBDocument.status == "ready")
        )).scalars().all().__len__()
        kb.document_count = ready_count
        kb.chunk_count = (await self.db.execute(
            select(KBChunk).where(KBChunk.kb_id == doc.kb_id)
        )).scalars().all().__len__()

        await self.db.commit()
        return {
            "chunks": len(chunks),
            "status": "ok",
            "results": results,
            "embedding_warning": embedding_warning,
        }

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量生成 embedding，失败时抛出异常。"""
        if not texts:
            return []
        model_info = await self._get_embedding_model()
        if not model_info:
            raise ValueError(
                "未配置 Embedding 模型。请在「模型配置」中设置 OpenAI 兼容的 API Key 和 embedding_model，"
                "否则知识库无法进行语义搜索。"
            )
        base_url, api_key = model_info
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{base_url}/embeddings",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": "text-embedding-3-small", "input": texts},
            )
            r.raise_for_status()
            data = r.json()["data"]
            return [item["embedding"] for item in data]

    async def search(self, kb_id: int, query: str, top_k: int = 5) -> list[dict]:
        """语义搜索知识库（ZVec 检索 → MySQL 回查内容）。"""
        import zvec
        from ..db.models import KBChunk

        coll_path = _get_collection_path(kb_id)
        if not _collection_exists(kb_id):
            return []

        coll = zvec.open(coll_path)
        query_vec = await self.embed(query)

        results = coll.query(
            queries=zvec.Query("embedding", vector=query_vec),
            topk=top_k,
        )
        if not results:
            return []

        ids = [int(r.id) for r in results]
        rows = (await self.db.execute(
            select(KBChunk).where(KBChunk.id.in_(ids))
        )).scalars().all()
        content_map = {r.id: r for r in rows}

        output = []
        for r in results:
            row = content_map.get(int(r.id))
            if row:
                output.append({
                    "score": round(r.score, 4),
                    "content": row.content,
                    "chunk_index": row.chunk_index,
                    "document_id": row.document_id,
                    "kb_chunk_id": row.id,
                })
        return output
