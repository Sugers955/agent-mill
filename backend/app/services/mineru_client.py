"""MinerU cloud API client (mineru.net).

Submits a file → polls task → returns markdown. Designed to be swap-friendly
with a self-hosted FastAPI variant via env (MINERU_BASE_URL).
"""
from __future__ import annotations
import asyncio
import logging
import os
from pathlib import Path
from typing import Any
import httpx

from ..core.config import settings

logger = logging.getLogger(__name__)


class MinerUError(Exception):
    pass


class MinerUClient:
    """Minimal async client. Cloud flow:

    1. POST /api/v4/file-urls/batch  → request a presigned upload URL + batch_id
    2. PUT the file bytes to the presigned URL
    3. Poll  GET /api/v4/extract-results/batch/{batch_id}  until state=done
    4. Download the produced markdown URL

    The exact endpoint shapes evolve; we keep them isolated here.
    """

    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 timeout: int | None = None):
        self.base_url = (base_url or settings.MINERU_BASE_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.MINERU_API_KEY
        self.timeout = timeout or settings.MINERU_TIMEOUT_SEC

    def _headers(self) -> dict[str, str]:
        h = {"Accept": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    async def parse(self, file_path: str | Path, file_name: str) -> str:
        """Submit a local file → return parsed markdown text."""
        if not self.api_key:
            raise MinerUError("MINERU_API_KEY 未配置")
        path = Path(file_path)
        if not path.exists():
            raise MinerUError(f"file not found: {file_path}")

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            # 1) Request a presigned upload URL
            req_url = f"{self.base_url}/api/v4/file-urls/batch"
            req_body = {
                "enable_formula": True,
                "enable_table": True,
                "language": "ch",
                "files": [{"name": file_name, "is_ocr": True}],
            }
            logger.info("MinerU: POST %s  file=%s", req_url, file_name)
            r = await client.post(req_url, json=req_body, headers=self._headers())
            logger.info("MinerU: file-urls/batch status=%s body=%s", r.status_code, r.text[:500])
            if r.status_code >= 400:
                raise MinerUError(f"file-urls/batch HTTP {r.status_code}: {r.text[:300]}")
            data = r.json()
            if data.get("code") not in (0, 200, "0", None):
                raise MinerUError(f"file-urls/batch returned: {data}")
            payload = data.get("data") or {}
            batch_id = payload.get("batch_id")
            urls = payload.get("file_urls") or []
            if not batch_id or not urls:
                raise MinerUError(f"missing batch_id or file_urls in response: {data}")
            upload_url = urls[0]
            logger.info("MinerU: batch_id=%s upload_url=%s…", batch_id, upload_url[:80])

            # 2) Upload file content via PUT (presigned). No auth header.
            with path.open("rb") as fh:
                blob = fh.read()
            up = await client.put(upload_url, content=blob)
            logger.info("MinerU: upload PUT status=%s", up.status_code)
            if up.status_code >= 400:
                raise MinerUError(f"upload PUT HTTP {up.status_code}: {up.text[:200]}")

            # 3) Poll extract-results
            poll_url = f"{self.base_url}/api/v4/extract-results/batch/{batch_id}"
            logger.info("MinerU: polling %s", poll_url)
            deadline = asyncio.get_running_loop().time() + self.timeout
            interval = 2.0
            while asyncio.get_running_loop().time() < deadline:
                pr = await client.get(poll_url, headers=self._headers())
                if pr.status_code >= 400:
                    raise MinerUError(f"poll HTTP {pr.status_code}: {pr.text[:300]}")
                pdata = pr.json()
                results = ((pdata.get("data") or {}).get("extract_result") or [])
                if results:
                    item = results[0]
                    state = (item.get("state") or "").lower()
                    logger.info("MinerU: poll state=%s item=%s", state, str(item)[:300])
                    if state == "done":
                        # Either a markdown_url or full_zip_url is returned. Prefer markdown_url.
                        md_url = item.get("full_md_link") or item.get("markdown_url") or item.get("md_url")
                        zip_url = item.get("full_zip_url")
                        if md_url:
                            mr = await client.get(md_url)
                            mr.raise_for_status()
                            return mr.text
                        if zip_url:
                            return await self._fetch_md_from_zip(client, zip_url)
                        raise MinerUError(f"done but no markdown URL: {item}")
                    if state == "failed":
                        raise MinerUError(f"MinerU task failed: {item.get('err_msg') or item}")
                await asyncio.sleep(interval)
            raise MinerUError(f"MinerU 解析超时 (>{self.timeout}s)")

    @staticmethod
    async def _fetch_md_from_zip(client: httpx.AsyncClient, zip_url: str) -> str:
        import io, zipfile
        zr = await client.get(zip_url)
        zr.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(zr.content)) as zf:
            md_names = [n for n in zf.namelist() if n.lower().endswith(".md")]
            if not md_names:
                raise MinerUError("zip 内未找到 .md")
            md_names.sort(key=lambda n: -len(zf.read(n)))  # pick largest
            return zf.read(md_names[0]).decode("utf-8", errors="replace")
