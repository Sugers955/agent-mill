"""Capability summarizer.

为 Skill / MCPConnector 生成「面向用户、面向中文使用者」的能力摘要。

设计要点:
- 输出严格中文,口径友好,不出现技术名词(参数名/字段名/工具名/英文术语)
- Skill: 优先读 SKILL.md,其次 README.md,再不济用 description+name
- MCP: 拉一次工具列表,把 server 整体描述 + 每个 tool 的中文短语一并请 LLM
- 用 models 表里 ID 最小且 enabled=True 的 Model 作为摘要模型,无显式配置
- 失败安静记日志,不抛异常打断上传流程
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.crypto import decrypt_str
from ..db.models import MCPConnector, Model, Skill
from ..db.session import SessionLocal


log = logging.getLogger("capability_summarizer")


_PROVIDER_BASE_URL = {
    "deepseek": "https://api.deepseek.com/v1",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "glm": "https://open.bigmodel.cn/api/paas/v4",
}


def _normalize_base_url(url: str | None) -> str | None:
    if not url:
        return url
    import re
    u = url.rstrip("/")
    if re.search(r"/v\d+$", u) or "/api/" in u or "/compatible-mode" in u:
        return u
    return u + "/v1"


async def _pick_summarizer_model(db: AsyncSession) -> Model | None:
    return (await db.execute(
        select(Model).where(Model.enabled.is_(True)).order_by(Model.id.asc()).limit(1)
    )).scalar_one_or_none()


async def _call_llm_for_summary(model: Model, prompt: str) -> str:
    """Call an OpenAI-compatible chat endpoint and return the message content.

    For provider == 'anthropic' we still use OpenAI-compatible if base_url and
    api_key are set, but for now we only support OpenAI-compatible providers
    (which is how all summarizer-eligible models in this project are configured).
    """
    from openai import AsyncOpenAI

    api_key = decrypt_str(model.api_key_enc) if model.api_key_enc else ""
    if not api_key:
        raise RuntimeError(f"摘要模型 {model.code} 未配置 API Key")
    base_url = _normalize_base_url(model.base_url or _PROVIDER_BASE_URL.get(model.provider.lower()))
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    resp = await client.chat.completions.create(
        model=model.model_id,
        messages=[
            {"role": "system", "content": "你是一名面向中文最终用户的能力简介撰写专家。"
                                          "用户不是程序员,你写出来的描述必须简洁、亲切、避免任何技术术语。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=600,
    )
    return (resp.choices[0].message.content or "").strip()


def _read_skill_doc(skill: Skill) -> str | None:
    src = skill.source_json or {}
    path_str = src.get("path")
    if not path_str:
        return None
    root = Path(path_str)
    for fname in ("SKILL.md", "skill.md", "README.md", "readme.md"):
        f = root / fname
        if f.exists() and f.is_file():
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:  # noqa: BLE001
                continue
            return text[:8000]
    return None


def _build_skill_prompt(skill: Skill, doc_text: str | None) -> str:
    parts: list[str] = []
    parts.append(f"以下是一个能力模块的元信息。请用一段 60-120 字的中文给最终用户介绍它能帮你做什么,"
                 f"不要出现工具名、参数名、英文专业术语,语气自然、像在向同事解释。")
    parts.append(f"模块名称: {skill.name}")
    if skill.description:
        parts.append(f"管理员备注: {skill.description}")
    if doc_text:
        parts.append("详细文档(节选):\n" + doc_text)
    parts.append("请直接输出最终中文介绍正文,不要任何前后缀、引号或 Markdown 标题。")
    return "\n\n".join(parts)


def _build_mcp_prompt(mcp: MCPConnector, tools: list[dict[str, Any]]) -> str:
    tool_lines: list[str] = []
    for t in tools[:30]:  # cap to avoid blowing the context
        name = t.get("name") or "(unnamed)"
        desc = (t.get("description") or "").strip().replace("\n", " ")
        if len(desc) > 200:
            desc = desc[:200] + "…"
        tool_lines.append(f"- {name}: {desc}")
    tool_block = "\n".join(tool_lines) if tool_lines else "(暂未列出工具)"
    return (
        "以下是一个外部能力服务及它对外暴露的工具清单。请输出 JSON 对象,字段如下:\n"
        '{ "summary": "中文整体介绍 60-120 字", '
        '"tools": [ {"name": "<原工具名>", "label": "<中文短名 不超过 16 字>", "description": "<中文一句话说明 不超过 60 字>"} ] }\n'
        "硬性要求:\n"
        "- summary 是给最终用户看的,口语化,不要英文术语和参数名,不要出现 MCP / API / endpoint 这些字眼\n"
        "- 每个工具都要在 tools 列表里出现一行\n"
        "- description 不要照抄英文,翻译并改写成自然中文\n"
        "- 输出必须是合法 JSON,不要包裹 ``` 代码块\n\n"
        f"服务名称: {mcp.name}\n"
        f"工具清单:\n{tool_block}"
    )


async def summarize_skill(skill_id: int) -> None:
    """Generate and persist `Skill.user_summary`.

    Safe to call multiple times. Errors are logged, not raised.
    """
    try:
        async with SessionLocal() as db:
            skill = (await db.execute(select(Skill).where(Skill.id == skill_id))).scalar_one_or_none()
            if not skill:
                log.warning("summarize_skill: skill %s not found", skill_id)
                return
            model = await _pick_summarizer_model(db)
            if not model:
                log.warning("summarize_skill: no enabled summarizer model")
                return
            doc_text = _read_skill_doc(skill)
            prompt = _build_skill_prompt(skill, doc_text)
            content = await _call_llm_for_summary(model, prompt)
            if not content:
                log.warning("summarize_skill: empty content for skill %s", skill.code)
                return
            skill.user_summary = content
            skill.user_summary_updated_at = datetime.now(timezone.utc)
            await db.commit()
            log.info("summarize_skill: ok skill=%s len=%d", skill.code, len(content))
    except Exception as e:  # noqa: BLE001
        log.exception("summarize_skill failed for %s: %s", skill_id, e)


async def summarize_mcp(mcp_id: int) -> None:
    """Generate and persist MCP user_summary + per-tool labels.

    The tool list is fetched live from the MCP server (one-shot connect/list/disconnect)
    via AgentRunner._list_mcp_tools_once. Failures degrade gracefully.
    """
    try:
        async with SessionLocal() as db:
            mcp = (await db.execute(select(MCPConnector).where(MCPConnector.id == mcp_id))).scalar_one_or_none()
            if not mcp:
                log.warning("summarize_mcp: mcp %s not found", mcp_id)
                return
            model = await _pick_summarizer_model(db)
            if not model:
                log.warning("summarize_mcp: no enabled summarizer model")
                return
        # Fetch tools via the existing one-shot helper
        from ..runtime.agent_runner import AgentRunner
        try:
            tools = await AgentRunner._list_mcp_tools_once(mcp)
        except Exception as e:  # noqa: BLE001
            log.warning("summarize_mcp: list tools failed for %s: %s", mcp.name, e)
            tools = []
        prompt = _build_mcp_prompt(mcp, tools)
        raw = await _call_llm_for_summary(model, prompt)
        if not raw:
            log.warning("summarize_mcp: empty content for mcp %s", mcp.name)
            return
        # Best-effort JSON parse; if the model wrapped in fences, strip them
        body = raw.strip()
        if body.startswith("```"):
            body = body.strip("`")
            if body.lower().startswith("json"):
                body = body[4:].lstrip()
        summary_text: str
        tool_summaries: dict[str, Any] | None = None
        try:
            data = json.loads(body)
            summary_text = str(data.get("summary") or "").strip()
            if isinstance(data.get("tools"), list):
                # Merge LLM-generated label/description with the live input_schema
                # so the runtime can use this as a hot cache (skip real-time MCP
                # enumeration on each chat request). Without input_schema the
                # cache is useless to the LLM tool-calling layer.
                live_by_name = {t.get("name"): t for t in (tools or []) if t.get("name")}
                enriched: list[dict[str, Any]] = []
                for it in data["tools"]:
                    if not isinstance(it, dict):
                        continue
                    raw_name = it.get("name")
                    live = live_by_name.get(raw_name) if raw_name else None
                    enriched.append({
                        "name": raw_name,
                        "label": it.get("label") or raw_name,
                        # Prefer the LLM-rewritten Chinese description for UI; keep
                        # the raw English desc separately for the LLM tool call.
                        "description": it.get("description") or "",
                        "raw_description": (live or {}).get("description") or "",
                        "input_schema": (live or {}).get("input_schema") or {"type": "object"},
                    })
                # Also include any live tools the LLM forgot to mention, so the
                # cache covers ALL callable tools (otherwise the chat path will
                # miss them and fall back to real-time enumeration anyway).
                seen = {it["name"] for it in enriched if it.get("name")}
                for t in (tools or []):
                    if t.get("name") and t["name"] not in seen:
                        enriched.append({
                            "name": t["name"],
                            "label": t["name"],
                            "description": t.get("description") or "",
                            "raw_description": t.get("description") or "",
                            "input_schema": t.get("input_schema") or {"type": "object"},
                        })
                tool_summaries = {
                    "items": enriched,
                    "cached_at": datetime.now(timezone.utc).isoformat(),
                }
        except Exception:
            summary_text = raw
        async with SessionLocal() as db:
            mcp2 = (await db.execute(select(MCPConnector).where(MCPConnector.id == mcp_id))).scalar_one_or_none()
            if not mcp2:
                return
            mcp2.user_summary = summary_text
            mcp2.tool_summaries_json = tool_summaries
            mcp2.user_summary_updated_at = datetime.now(timezone.utc)
            await db.commit()
            log.info("summarize_mcp: ok mcp=%s tools=%d", mcp2.name,
                     len(tool_summaries.get("items", [])) if tool_summaries else 0)
    except Exception as e:  # noqa: BLE001
        log.exception("summarize_mcp failed for %s: %s", mcp_id, e)
