"""Agent runtime: bridges our config to the Claude Agent SDK.

This file isolates the SDK call so the rest of the app stays decoupled from SDK API
changes. The streaming generator yields events the API layer turns into SSE messages.

Note: claude-agent-sdk's exact public surface evolves. We use a thin facade so we can
adapt without rewriting callers.
"""
from __future__ import annotations
import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator
from ..db.models import Agent, Skill, MCPConnector, Model, Message
from ..core.crypto import decrypt_str
from .mcp_manager import build_mcp_servers
from .widget_guidelines import (
    handle_widget_tool_call,
)
from .prompt_builder import (
    build_system_prompt,
    render_attachments,
    wants_widget,
    agent_has_drawing_skill,
    EFFORT_THINKING_BUDGET,
    EFFORT_OPENAI_REASONING,
    effort_to_thinking_budget,
    effort_to_openai_reasoning,
)
from .skill_executor import (
    run_skill_by_code,
    load_skill_bundle,
    read_skill_file,
    run_skill_script,
    save_output_file,
    extract_fallback_files_async,
    register_skill_files,
)
from .mcp_client import (
    prefix_mcp_actions as _prefix_mcp_actions,
    mcp_tool_name,
    open_mcp_session,
    call_mcp_tool,
    with_mcp_session,
    list_mcp_tools_once,
    call_mcp_tool_once,
)
from .tool_registry import (
    build_openai_tools as _build_openai_tools_fn,
    build_ask_user_pick as _build_ask_user_pick_fn,
    build_ask_user_form as _build_ask_user_form_fn,
)












def _move_scripts_to_end(html: str) -> str:
    """Move every <script>...</script> block to just before </body>.

    Mirrors the widget iframe receiver's "DOM first, scripts last" strategy.
    Without this, a saved standalone .html file breaks when the model wrote
    its <script> at the top of the body — DOM elements referenced via
    document.getElementById are not yet in the tree, and onclick handlers
    can fire before the script's let/const declarations finish.

    Idempotent: if there's no <body>, returns html unchanged.
    """
    import re as _re
    if "<body" not in html.lower():
        return html
    # Extract all <script>...</script> blocks (with their attrs)
    script_pattern = _re.compile(r"<script\b[^>]*>[\s\S]*?</script>", _re.IGNORECASE)
    scripts = script_pattern.findall(html)
    if not scripts:
        return html
    stripped = script_pattern.sub("", html)
    # Insert scripts just before </body>; if no </body>, append at end.
    body_close = _re.search(r"</body\s*>", stripped, _re.IGNORECASE)
    block = "\n" + "\n".join(scripts) + "\n"
    if body_close:
        i = body_close.start()
        return stripped[:i] + block + stripped[i:]
    return stripped + block


@dataclass
class AgentContext:
    agent: Agent
    skills: list[Skill]
    mcps: list[MCPConnector]
    packs: list[Any]  # SolutionPack rows
    model: Model | None
    fallback_model: Model | None
    history: list[Message]
    memory_context: str = ""  # 记忆上下文，注入 system prompt
    conversation_summary: str = ""  # 对话历史摘要（压缩后）
    _knowledge_context: str = ""  # 知识库上下文，内部使用


@dataclass
class StreamEvent:
    type: str  # "text" | "tool_use" | "tool_result" | "error" | "done" | "usage"
    data: Any


class AgentRunner:
    """Wraps Claude Agent SDK invocation with our skill/MCP/model config."""

    def __init__(self, ctx: AgentContext, user_id: int | None = None):
        self.ctx = ctx
        self._tokens_in = 0
        self._tokens_out = 0
        self._user_id = user_id
        self._conversation_id: int | None = None
        # Files saved during this run (to surface as file events to the UI)
        self._saved_files: list[dict[str, Any]] = []
        self._emitted_file_urls: set[str] = set()
        # UI Schemas emitted during this run (for chat.py to persist into history)
        self._saved_ui: list[dict[str, Any]] = []
        # Buffer of assistant text used by the stream-tail fallback extractor
        self._fallback_text_buf: list[str] = []
        # Set to True the moment the model calls `load_widget_guidelines` —
        # signals "I'm rendering via widget pipeline this turn", so any later
        # save_output_file with widget-shaped content is rejected to avoid
        # the duplicated output-1.txt file card next to the rendered widget.
        self._widget_pipeline_active: bool = False

    def _system_prompt(self, user_text: str | None = None) -> str:
        return build_system_prompt(
            agent=self.ctx.agent,
            skills=self.ctx.skills,
            model=None,
            user_text=user_text,
            memory_context=self.ctx.memory_context,
            knowledge_context=getattr(self.ctx, '_knowledge_context', ''),
        )

    def _build_openai_tools(self, user_text: str | None = None) -> list[dict[str, Any]]:
        return _build_openai_tools_fn(self.ctx.skills, self.ctx.packs)

    async def _pack_runner_factory(self, user_id: int | None = None, agent_id: int | None = None,
                                   conversation_id: int | None = None, override_agent_code: str | None = None):
        """Factory used by PackEngine to create sub-runners for different agents.
        
        When override_agent_code is provided, loads the specified agent's configuration
        and creates a new AgentRunner with that agent's context.
        """
        self._conversation_id = conversation_id
        
        # 如果没有指定不同的 Agent，返回 self
        if not override_agent_code or override_agent_code == self.ctx.agent.code:
            return self
        
        # 加载指定 Agent 的配置
        from sqlalchemy import select
        from ..db.models import Agent, AgentSkill, AgentMCP, Skill, MCPConnector, Model
        from ..db.session import SessionLocal
        
        async with SessionLocal() as db:
            # 查找目标 Agent
            target_agent = (await db.execute(
                select(Agent).where(Agent.code == override_agent_code, Agent.enabled == True)
            )).scalar_one_or_none()
            
            if not target_agent:
                logger.warning("Sub-agent not found: %s, falling back to parent", override_agent_code)
                return self
            
            # 加载目标 Agent 的 Skills
            skill_ids = [r[0] for r in (await db.execute(
                select(AgentSkill.skill_id).where(AgentSkill.agent_id == target_agent.id)
            )).all()]
            skills = list((await db.execute(
                select(Skill).where(Skill.id.in_(skill_ids), Skill.enabled.is_(True))
            )).scalars().all()) if skill_ids else []
            
            # 加载目标 Agent 的 MCPs
            mcp_ids = [r[0] for r in (await db.execute(
                select(AgentMCP.mcp_id).where(AgentMCP.agent_id == target_agent.id)
            )).all()]
            mcps = list((await db.execute(
                select(MCPConnector).where(MCPConnector.id.in_(mcp_ids), MCPConnector.enabled.is_(True))
            )).scalars().all()) if mcp_ids else []
            
            # 加载目标 Agent 的模型
            model = (await db.execute(
                select(Model).where(Model.id == target_agent.default_model_id)
            )).scalar_one_or_none() if target_agent.default_model_id else None
        
        # 创建新的 AgentContext
        from .agent_runner import AgentContext
        sub_ctx = AgentContext(
            agent=target_agent,
            skills=skills,
            mcps=mcps,
            packs=[],
            model=model,
            fallback_model=None,
            history=[],
        )
        
        # 创建新的 AgentRunner
        sub_runner = AgentRunner(sub_ctx, user_id=user_id or self._user_id)
        logger.info("Created sub-runner for agent: %s (user=%d)", override_agent_code, user_id or self._user_id)
        
        return sub_runner

    async def _exec_skill(self, skill_code: str, args: dict[str, Any]) -> dict[str, Any]:
        # built-in helper for reading skill bundle files
        if skill_code == "_read_skill_file":
            return await read_skill_file(self.ctx.skills, args.get("skill", ""), args.get("path", ""))

        # Universal output saver
        if skill_code == "save_output_file":
            return await save_output_file(
                filename=str(args.get("filename") or "output"),
                content=args.get("content") or "",
                user_id=self._user_id,
                saved_files=self._saved_files,
                mime=args.get("mime") or None,
                encoding=args.get("encoding") or "utf-8",
            )

        # Built-in user-interaction tools — produce a UI Schema with submit_as='message'
        # so a user click sends a synthetic user message back to the LLM next turn.
        if skill_code == "ask_user_pick":
            return _build_ask_user_pick_fn(args)
        if skill_code == "ask_user_form":
            return _build_ask_user_form_fn(args)

        # Run a bundled Skill python script
        if skill_code == "run_skill_script":
            return await run_skill_script(
                skills=self.ctx.skills,
                skill_code=str(args.get("skill") or ""),
                script=str(args.get("script") or ""),
                kwargs=args.get("kwargs") or {},
                output_filename=str(args.get("output_filename") or "output.bin"),
                user_id=self._user_id,
            )

        # Solution Pack runner (special tool injected as run_pack__<pack_code>)
        if skill_code.startswith("run_pack__"):
            from .pack_engine import PackEngine
            pack_code = skill_code.replace("run_pack__", "", 1)
            engine = PackEngine(runner_factory=self._pack_runner_factory)
            final = None
            async for ev in engine.start(pack_code, inputs=args or {},
                                         user_id=self._user_id,
                                         agent_id=getattr(self.ctx.agent, 'id', None),
                                         conversation_id=getattr(self, '_conversation_id', None)):
                final = ev.data
                if ev.type == 'pack_waiting_approval':
                    return {
                        'status': 'waiting_approval',
                        'run_id': ev.data.get('run_id'),
                        'pack_id': ev.data.get('pack_id'),
                        'message': ev.data.get('message') or '方案包等待审批',
                    }
                if ev.type == 'pack_error':
                    return {
                        'status': 'failed',
                        'run_id': ev.data.get('run_id'),
                        'pack_id': ev.data.get('pack_id'),
                        'error': ev.data.get('error'),
                    }
            return {
                'status': 'success',
                'run_id': (final or {}).get('run_id'),
                'pack_id': (final or {}).get('pack_id'),
                'outputs': (final or {}).get('outputs') or {},
                'trace': (final or {}).get('trace') or [],
            }

        # generative-UI widget guidelines loader
        if skill_code == "load_widget_guidelines":
            self._widget_pipeline_active = True
            return {"guidelines": handle_widget_tool_call(args)}

        skill = next((s for s in self.ctx.skills if s.code == skill_code), None)
        if not skill:
            return {"error": f"unknown skill: {skill_code}"}

        # path-based atomic skill: return SKILL.md + file listing so the model can follow instructions
        if skill.type == "atomic" and (skill.source_json or {}).get("path"):
            return await load_skill_bundle(skill)

        # callable / composite: actually execute
        trigger = args.get("input") if isinstance(args, dict) and "input" in args else args
        if not isinstance(trigger, dict):
            trigger = {"value": trigger}
        result = await run_skill_by_code(self.ctx.skills, skill_code, trigger)
        result = await register_skill_files(result, self._user_id)
        return result

    async def _register_mcp_files(self, result: dict[str, Any]) -> dict[str, Any]:
        """Register files produced by an MCP tool call so they surface as
        downloadable cards in the chat UI.

        Each entry in `_files` may supply the content in one of three ways
        (tried in order):
          1. path       — absolute local path (same-host MCP only)
          2. content    — plain text string (written as UTF-8)
          3. content_b64 — base64-encoded bytes (written as binary)

        Looks for `_files` at the top level of `result` or nested under
        `result["data"]` (where `_call_mcp_tool_once` places parsed JSON).
        """
        if not isinstance(result, dict):
            return result
        candidates: list[tuple[dict, str]] = []
        if isinstance(result.get("_files"), list):
            candidates.append((result, "_files"))
        data = result.get("data")
        if isinstance(data, dict) and isinstance(data.get("_files"), list):
            candidates.append((data, "_files"))
        if not candidates:
            return result

        import base64 as _b64
        import mimetypes as _mt
        import uuid as _uuid
        from pathlib import Path as _P
        from ..core.config import settings
        from ..db.session import SessionLocal
        from ..services.downloads import register_file

        registered: list[dict[str, Any]] = []
        for container, key in candidates:
            files = container.get(key) or []
            async with SessionLocal() as db:
                for f in files:
                    if not isinstance(f, dict):
                        continue
                    name = str(f.get("name") or "file").strip()
                    mime = f.get("mime") or _mt.guess_type(name)[0] or "application/octet-stream"
                    try:
                        # ---- resolve content bytes ----
                        file_bytes: bytes | None = None
                        fp = str(f.get("path") or "").strip()
                        if fp:
                            abs_p = _P(fp).expanduser().resolve()
                            if abs_p.is_file():
                                file_bytes = abs_p.read_bytes()
                        if file_bytes is None and f.get("content_b64"):
                            file_bytes = _b64.b64decode(f["content_b64"])
                        if file_bytes is None and f.get("content") is not None:
                            file_bytes = str(f["content"]).encode("utf-8")
                        if file_bytes is None:
                            registered.append({"error": f"no content for file: {name}"})
                            continue

                        # ---- write to outputs dir ----
                        out_root = _P(settings.STORAGE_ROOT) / "outputs" / str(self._user_id or "anon")
                        out_root.mkdir(parents=True, exist_ok=True)
                        safe = _P(name).name or "output"
                        target = out_root / f"{_uuid.uuid4().hex[:8]}-{safe}"
                        target.write_bytes(file_bytes)

                        # ---- register download token ----
                        tok = await register_file(
                            db,
                            file_path=str(target),
                            file_name=name,
                            user_id=self._user_id,
                            mime=mime,
                        )
                        await db.commit()
                        info = {
                            "name": tok.file_name, "size": tok.size, "mime": tok.mime,
                            "download_url": f"/api/downloads/{tok.token}",
                            "preview_url": f"/api/downloads/{tok.token}",
                        }
                        registered.append(info)
                        self._saved_files.append(info)
                    except Exception as e:  # noqa: BLE001
                        registered.append({"error": f"register failed: {e}"})
            container.pop(key, None)
        if registered:
            # Strip download/preview URLs from what the model sees — the UI
            # renders file cards via _saved_files SSE events. Exposing raw
            # /api/downloads/ URLs causes the model to write them into reply
            # text as markdown links, which break when opened in the browser
            # without an auth header.
            result["files"] = [
                {k: v for k, v in f.items() if k not in ("download_url", "preview_url")}
                for f in registered
            ]
        return result

    async def _maybe_register_files_from_tool_result(self, content: str) -> None:
        """Anthropic-SDK path: tool_result content is a raw string. If the MCP
        tool returned JSON with a `_files` array, parse it and register the
        files so they appear as download cards. No-op for non-JSON content."""
        if not content or not self._user_id:
            return
        s = content.strip()
        if not (s.startswith("{") and s.endswith("}")):
            return
        try:
            import json as _json
            parsed = _json.loads(s)
        except Exception:
            return
        if not isinstance(parsed, dict):
            return
        await self._register_mcp_files(parsed)

    async def exec_ui_action(self, tool: str, params: dict[str, Any]) -> AsyncIterator[StreamEvent]:
        """Execute a single tool call directly (no LLM), used for [UI_ACTION] routing.

        Streams tool_use → tool_result/ui → done. Cheap: no model tokens spent.
        Caller MUST validate `tool` against the agent's whitelist before calling.
        """
        import json as _json
        import time as _t
        start = _t.time()
        if self.ctx.model:
            yield StreamEvent("meta", {
                "agent_name": self.ctx.agent.name,
                "agent_code": self.ctx.agent.code,
                "model_code": self.ctx.model.code,
                "model_id": self.ctx.model.model_id,
                "provider": self.ctx.model.provider,
                "ui_action": True,
            })
        call_id = f"ui_{int(_t.time()*1000)}"
        yield StreamEvent("tool_use", {"id": call_id, "name": tool, "input": params})
        try:
            # Resolve MCP tool first (UI may target an MCP-exposed tool)
            mcp_match = None
            for m in self.ctx.mcps:
                # Names like mcp__<server>__<raw>
                if tool.startswith(f"mcp__{m.name}__"):
                    raw = tool[len(f"mcp__{m.name}__"):]
                    mcp_match = (m, raw)
                    break
            if mcp_match:
                m, raw = mcp_match
                result = await call_mcp_tool_once(m, raw, params)
                result = await self._register_mcp_files(result)
            else:
                result = await self._exec_skill(tool, params)
        except Exception as e:  # noqa: BLE001
            result = {"error": str(e)}

        from ..ui_schema.types import extract_ui_schema, strip_ui_for_model
        ui_schema = extract_ui_schema(result, tool_name=tool)
        if ui_schema:
            yield StreamEvent("ui", ui_schema)
            self._saved_ui.append(ui_schema)
            result = strip_ui_for_model(result)
        yield StreamEvent("tool_result", {"tool_use_id": call_id, "content": _json.dumps(result, ensure_ascii=False, default=str)})
        # Surface any saved files registered during execution
        for f in self._saved_files:
            url = str(f.get("download_url") or "")
            if url and url in self._emitted_file_urls:
                continue
            if url:
                self._emitted_file_urls.add(url)
            yield StreamEvent("file", f)
        yield StreamEvent("done", {
            "tokens_in": 0, "tokens_out": 0,
            "latency_ms": int((_t.time() - start) * 1000),
            "ui_action": True,
        })

    async def stream(self, user_text: str, files: list[dict[str, Any]] | None = None) -> AsyncIterator[StreamEvent]:
        """Yield streaming events.

        Routes by provider:
        - anthropic                         → Claude Agent SDK (full Skills/MCP support)
        - deepseek/qwen/glm/openai/openai-compatible → OpenAI-compatible chat-completions stream
        """
        start = time.time()
        # Always emit a meta event first so the frontend knows which agent/model is being used
        if self.ctx.model:
            yield StreamEvent("meta", {
                "agent_name": self.ctx.agent.name,
                "agent_code": self.ctx.agent.code,
                "model_code": self.ctx.model.code,
                "model_id": self.ctx.model.model_id,
                "provider": self.ctx.model.provider,
            })
        provider = (self.ctx.model.provider if self.ctx.model else "anthropic").lower()
        primary_failed: tuple[type, str] | None = None
        primary_streamed_text = False
        try:
            try:
                inner = (self._stream_via_sdk(user_text, files or []) if provider == "anthropic"
                         else self._stream_via_openai(user_text, files or []))
                async for ev in inner:
                    # Accumulate text for the fallback extractor (runs in finally)
                    if ev.type == "text":
                        txt = ev.data.get("text", "") if isinstance(ev.data, dict) else ""
                        self._fallback_text_buf.append(txt)
                        if txt:
                            primary_streamed_text = True
                    yield ev
            except ImportError as e:
                yield StreamEvent("error", {"message": f"SDK 未安装: {e}"})
            except Exception as e:  # noqa: BLE001
                primary_failed = (type(e), str(e))

            # Fallback: only if the primary call errored AND it hadn't yet streamed
            # any visible text/tool output to the user. Mid-stream model swaps look
            # broken (the user already saw partial output from model A), so we skip
            # the swap in that case and surface the original error.
            if primary_failed is not None:
                fb = self.ctx.fallback_model
                if fb and not primary_streamed_text:
                    yield StreamEvent("text", {
                        "text": f"\n\n> ⚠️ 主模型调用失败（{primary_failed[1][:120]}），已自动切换到降级模型 **{fb.code}** 重试…\n\n",
                    })
                    # Swap model + reset per-call counters so usage attribution makes
                    # sense for the retry. Provider may differ → re-route SDK/OpenAI path.
                    self.ctx.model = fb
                    self._tokens_in = 0
                    self._tokens_out = 0
                    yield StreamEvent("meta", {
                        "agent_name": self.ctx.agent.name,
                        "agent_code": self.ctx.agent.code,
                        "model_code": fb.code,
                        "model_id": fb.model_id,
                        "provider": fb.provider,
                        "fallback": True,
                    })
                    fb_provider = (fb.provider or "").lower()
                    try:
                        fb_inner = (self._stream_via_sdk(user_text, files or []) if fb_provider == "anthropic"
                                    else self._stream_via_openai(user_text, files or []))
                        async for ev in fb_inner:
                            if ev.type == "text":
                                self._fallback_text_buf.append(ev.data.get("text", "") if isinstance(ev.data, dict) else "")
                            yield ev
                    except Exception as e2:  # noqa: BLE001
                        yield StreamEvent("error", {
                            "message": f"降级模型也失败: {e2}（原始错误: {primary_failed[1][:120]}）",
                        })
                else:
                    yield StreamEvent("error", {"message": f"agent 执行错误: {primary_failed[1]}"})
        finally:
            # If the model dumped a large code block to text instead of calling
            # save_output_file, extract & persist it as a fallback.
            if self._fallback_text_buf:
                await extract_fallback_files_async("".join(self._fallback_text_buf), self._user_id, self._saved_files)
            # Emit any saved files BEFORE done so the UI gets file cards in order
            for f in self._saved_files:
                url = str(f.get("download_url") or "")
                if url and url in self._emitted_file_urls:
                    continue
                if url:
                    self._emitted_file_urls.add(url)
                yield StreamEvent("file", f)
            yield StreamEvent("done", {
                "tokens_in": self._tokens_in,
                "tokens_out": self._tokens_out,
                "latency_ms": int((time.time() - start) * 1000),
                "files": list(self._saved_files),
            })

    PROVIDER_BASE_URL: dict[str, str] = {
        "deepseek": "https://api.deepseek.com/v1",
        "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "glm": "https://open.bigmodel.cn/api/paas/v4",
    }

    def _render_attachments(self, files: list[dict[str, Any]]) -> str:
        limit_override = getattr(self.ctx.agent, "parsed_content_limit", None)
        return render_attachments(files, parsed_limit=limit_override)

    @staticmethod
    def normalize_base_url(url: str | None) -> str | None:
        """Append /v1 if base_url has no version suffix (common user mistake)."""
        if not url:
            return url
        import re
        u = url.rstrip("/")
        # already has /vN or a known API path -> leave alone
        if re.search(r"/v\d+$", u) or "/api/" in u or "/compatible-mode" in u:
            return u
        return u + "/v1"

    async def _stream_via_openai(self, user_text: str, files: list[dict[str, Any]]) -> AsyncIterator[StreamEvent]:
        from openai import AsyncOpenAI
        from contextlib import AsyncExitStack
        import json as _json

        # Wall-clock start so the `done` event can report latency_ms even when
        # we hit the halt-after-tools branch (which references `start` below).
        start = time.time()

        model = self.ctx.model
        if not model:
            yield StreamEvent("error", {"message": "未配置默认模型"})
            return
        api_key = decrypt_str(model.api_key_enc) if model.api_key_enc else ""
        if not api_key:
            yield StreamEvent("error", {"message": "模型 API Key 未配置"})
            return
        base_url = model.base_url or self.PROVIDER_BASE_URL.get(model.provider.lower())
        base_url = self.normalize_base_url(base_url)
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)

        system = self._system_prompt(user_text) or "You are a helpful assistant."
        prompt = user_text
        if files:
            prompt += self._render_attachments(files)

        tools = self._build_openai_tools(user_text)
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        # Replay prior turns so the model has conversation context.
        # Important: for assistant turns that called tools (esp. interactive ones
        # like ask_user_form / ask_user_pick), we MUST replay the tool_calls
        # and their tool responses so the model understands why the next user
        # message is a form submission / pick selection and not a fresh query.
        for h in (self.ctx.history or []):
            cj = h.content_json if isinstance(h.content_json, dict) else {}
            text = cj.get("text") or ""
            if h.role == "user":
                if text:
                    messages.append({"role": "user", "content": text})
            elif h.role == "assistant":
                trace = []
                if isinstance(h.tool_calls_json, dict):
                    trace = h.tool_calls_json.get("trace") or []
                # Collect tool_use entries on this assistant turn, in order.
                tool_uses: list[dict[str, Any]] = []
                tool_results_by_id: dict[str, Any] = {}
                _seen_tool_ids: set[str] = set()
                for t in trace:
                    if not isinstance(t, dict):
                        continue
                    tt = t.get("type"); d = t.get("data") or {}
                    if tt == "tool_use":
                        tid = d.get("id") or d.get("name") or f"t_{len(tool_uses)}"
                        if tid in _seen_tool_ids:
                            continue
                        _seen_tool_ids.add(tid)
                        tool_uses.append({
                            "id": tid, "name": d.get("name") or "",
                            "arguments": d.get("input") or {},
                        })
                    elif tt == "tool_result":
                        tid = d.get("tool_use_id")
                        if tid is not None:
                            tool_results_by_id[str(tid)] = d.get("content")
                if tool_uses:
                    messages.append({
                        "role": "assistant",
                        "content": text or None,
                        "tool_calls": [
                            {
                                "id": str(tu["id"]),
                                "type": "function",
                                "function": {
                                    "name": tu["name"],
                                    "arguments": _json.dumps(tu["arguments"] or {}, ensure_ascii=False),
                                },
                            }
                            for tu in tool_uses
                        ],
                    })
                    for tu in tool_uses:
                        result = tool_results_by_id.get(str(tu["id"]), "")
                        if not isinstance(result, str):
                            result = _json.dumps(result, ensure_ascii=False, default=str)
                        # Cap individual tool_result to avoid bloating the context
                        # window when replaying history (e.g. MCP returning large docs).
                        if len(result) > 6000:
                            result = result[:6000] + f"…[历史摘要已截断, 原始长度 {len(result)} 字符]"
                        messages.append({"role": "tool", "tool_call_id": str(tu["id"]), "content": result})
                elif text:
                    messages.append({"role": "assistant", "content": text})
        messages.append({"role": "user", "content": prompt})

        # ---- MCP integration: cached tool list + parallel fallback ----
        # Hot path: read each MCP's tool list from `tool_summaries_json` (admin
        # populates this via "重新生成介绍" / on connector save). This avoids
        # per-request connect+initialize+list_tools handshakes which dominate
        # TTFT when an agent has multiple MCP servers.
        # If a server's cache is empty/missing, fall back to real-time list —
        # but parallelized across MCPs so we pay max(latency) instead of sum.
        mcp_tool_routes: dict[str, tuple[str, "MCPConnector"]] = {}  # exposed -> (raw_tool, mcp row)

        def _ingest_tool_list(mcp, tools_list: list[dict[str, Any]]) -> None:
            for t in tools_list:
                name = t.get("name")
                if not name:
                    continue
                exposed = mcp_tool_name(mcp.name, name)
                mcp_tool_routes[exposed] = (name, mcp)
                # Prefer raw_description (live tool description) for the
                # function-calling system; fall back to the LLM-rewritten
                # `description` if no raw is cached.
                desc = t.get("raw_description") or t.get("description") or name
                tools.append({
                    "type": "function",
                    "function": {
                        "name": exposed,
                        "description": f"[MCP:{mcp.name}] {desc}",
                        "parameters": t.get("input_schema") or {"type": "object"},
                    },
                })

        mcps_needing_live: list = []
        for mcp in self.ctx.mcps:
            cache = (mcp.tool_summaries_json or {}).get("items") if mcp.tool_summaries_json else None
            # Only trust cache entries that include input_schema — older caches
            # without it can't drive function calls; force a live refresh.
            usable_cache = (
                isinstance(cache, list)
                and cache
                and any(isinstance(it, dict) and it.get("input_schema") for it in cache)
            )
            if usable_cache:
                _ingest_tool_list(mcp, [it for it in cache if isinstance(it, dict)])
            else:
                mcps_needing_live.append(mcp)

        if mcps_needing_live:
            import logging as _lg
            _log = _lg.getLogger(__name__)
            async def _safe_list(m):
                try:
                    return m, await list_mcp_tools_once(m), None
                except Exception as e:  # noqa: BLE001
                    return m, [], e
            results = await asyncio.gather(*[_safe_list(m) for m in mcps_needing_live])
            for m, tools_list, err in results:
                if err is not None:
                    _log.warning("MCP %s tool enumeration failed: %s", m.name, err)
                    continue
                _ingest_tool_list(m, tools_list)

        # multi-turn loop: model may call skill / mcp tools, we execute and feed results back
        MAX_ITER = max(1, int(getattr(self.ctx.agent, "max_turns", 15) or 15))
        # Effort → reasoning_effort (OpenAI / DeepSeek / Qwen reasoning models honor
        # this; ignored by providers that don't). xhigh/max fall back to "high"
        # for OpenAI compat since only low/medium/high are universally accepted.
        effort_oa = effort_to_openai_reasoning(
            (getattr(self.ctx.agent, "effort", "medium") or "medium").lower()
        )
        for _ in range(MAX_ITER):
                create_kwargs: dict[str, Any] = {
                    "model": model.model_id,
                    "messages": messages,
                    "stream": True,
                    "stream_options": {"include_usage": True},
                }
                if tools:
                    create_kwargs["tools"] = tools
                if model.extra_params_json:
                    create_kwargs["extra_body"] = model.extra_params_json
                # reasoning_effort is only supported by OpenAI and DeepSeek.
                # Local / openai-compatible servers (vllm, ollama, etc.) return 500
                # on unknown parameters, so only send it to known providers.
                _REASONING_EFFORT_PROVIDERS = {"openai", "deepseek"}
                if effort_oa and (model.provider or "").lower() in _REASONING_EFFORT_PROVIDERS:
                    create_kwargs["reasoning_effort"] = effort_oa

                stream = await client.chat.completions.create(**create_kwargs)

                # accumulate this turn
                text_buf = ""
                reasoning_buf = ""
                tool_calls_acc: dict[int, dict[str, Any]] = {}
                emitted_starts: set[str] = set()
                finish_reason: str | None = None

                async for chunk in stream:
                    if chunk.usage:
                        self._tokens_in += chunk.usage.prompt_tokens or 0
                        self._tokens_out += chunk.usage.completion_tokens or 0
                    for choice in chunk.choices or []:
                        delta = getattr(choice, "delta", None)
                        if delta:
                            reasoning = getattr(delta, "reasoning_content", None)
                            if reasoning:
                                reasoning_buf += reasoning
                                yield StreamEvent("thinking", {"text": reasoning})
                            if delta.content:
                                text_buf += delta.content
                                yield StreamEvent("text", {"text": delta.content})
                            for tc in getattr(delta, "tool_calls", None) or []:
                                idx = tc.index if tc.index is not None else 0
                                slot = tool_calls_acc.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                                if tc.id:
                                    slot["id"] = tc.id
                                fn = getattr(tc, "function", None)
                                if fn:
                                    if fn.name:
                                        slot["name"] = fn.name
                                    if fn.arguments:
                                        slot["arguments"] += fn.arguments
                                if slot["id"] and slot["name"] and slot["id"] not in emitted_starts:
                                    yield StreamEvent("tool_use", {
                                        "id": slot["id"], "name": slot["name"], "input": {},
                                    })
                                    emitted_starts.add(slot["id"])
                        if choice.finish_reason:
                            finish_reason = choice.finish_reason

                if not tool_calls_acc:
                    return

                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": text_buf or None,
                    "tool_calls": [
                        {
                            "id": s["id"], "type": "function",
                            "function": {"name": s["name"], "arguments": s["arguments"] or "{}"},
                        }
                        for s in sorted(tool_calls_acc.values(), key=lambda x: x.get("id", ""))
                        if s.get("id") and s.get("name")
                    ],
                }
                if reasoning_buf:
                    assistant_msg["reasoning_content"] = reasoning_buf
                messages.append(assistant_msg)

                # execute each tool call (route MCP tools to MCP server, others to skill executor)
                halt_after_tools = False
                for slot in tool_calls_acc.values():
                    if not (slot.get("id") and slot.get("name")):
                        continue
                    try:
                        args = _json.loads(slot["arguments"] or "{}")
                    except Exception:
                        args = {"raw": slot["arguments"]}
                    yield StreamEvent("tool_use", {"id": slot["id"], "name": slot["name"], "input": args})
                    try:
                        if slot["name"] in mcp_tool_routes:
                            raw_tool, mcp_row = mcp_tool_routes[slot["name"]]
                            result = await call_mcp_tool_once(mcp_row, raw_tool, args)
                            result = await self._register_mcp_files(result)
                        else:
                            result = await self._exec_skill(slot["name"], args)
                    except Exception as e:  # noqa: BLE001
                        result = {"error": str(e)}
                    # If the tool result carries a UI Schema, surface it directly to the
                    # frontend ComponentRegistry. The model still sees a small summary
                    # so it knows a UI was rendered; we don't feed back the whole schema.
                    from ..ui_schema.types import extract_ui_schema, strip_ui_for_model
                    ui_schema = extract_ui_schema(result, tool_name=slot["name"])
                    # Capture halt intent BEFORE strip (which scrubs runtime-only flags).
                    halts_loop = bool(isinstance(result, dict) and result.get("__halt__"))
                    if ui_schema:
                        yield StreamEvent("ui", ui_schema)
                        self._saved_ui.append(ui_schema)
                        result = strip_ui_for_model(result)
                    # `__halt__` tools (ask_user_pick / ask_user_form) must stop the
                    # loop immediately so the user can actually interact — otherwise
                    # the model sees the tool_result and cheerfully self-answers
                    # while the UI is still waiting for a click.
                    if halts_loop:
                        halt_after_tools = True
                    result_str = _json.dumps(result, ensure_ascii=False, default=str)
                    yield StreamEvent("tool_result", {"tool_use_id": slot["id"], "content": result_str})
                    if isinstance(result, dict) and isinstance(result.get("file"), dict):
                        file_info = result["file"]
                        url = str(file_info.get("download_url") or "")
                        if url and url not in self._emitted_file_urls:
                            self._emitted_file_urls.add(url)
                            yield StreamEvent("file", file_info)
                    messages.append({
                        "role": "tool", "tool_call_id": slot["id"],
                        "content": result_str,
                    })
                if halt_after_tools:
                    # End this turn. The next user action (form submit / pick) will
                    # come in as a fresh [UI_MSG] and the model picks up the thread
                    # with full tool_calls + tool_result history replayed.
                    yield StreamEvent("done", {
                        "tokens_in": self._tokens_in,
                        "tokens_out": self._tokens_out,
                        "latency_ms": int((time.time() - start) * 1000),
                        "files": list(self._saved_files),
                    })
                    return

        yield StreamEvent("error", {"message": f"工具调用循环超过 {MAX_ITER} 轮,已强制中断"})

    def _build_skill_sandbox(self) -> "Path | None":
        """Per-Agent Skill sandbox for the Anthropic SDK path.

        Per the official docs (https://code.claude.com/docs/en/agent-sdk/skills) the
        SDK discovers skills via filesystem scanning of `<cwd>/.claude/skills/` (when
        `setting_sources` includes `"project"`). To isolate skills per-agent we build
        a temporary cwd whose `.claude/skills/` only contains symlinks to the skills
        selected for THIS agent. Other agents' skill directories are NOT linked, so
        the model has no path to reach them — even via Read/Bash.

        Composite/callable skills are not filesystem-based; they're surfaced via the
        system prompt only on the Anthropic path.

        Returns the sandbox root, or None if there are no path-based skills (caller
        will skip the cwd/setting_sources options entirely).
        Caller must rmtree the returned path when the SDK call completes.
        """
        from pathlib import Path as _Path
        import tempfile
        path_skills = [s for s in self.ctx.skills
                       if s.type == "atomic" and (s.source_json or {}).get("path")]
        if not path_skills:
            return None
        sandbox = _Path(tempfile.mkdtemp(prefix=f"agent-mill-{self.ctx.agent.id}-"))
        skills_root = sandbox / ".claude" / "skills"
        skills_root.mkdir(parents=True, exist_ok=True)
        for s in path_skills:
            src = _Path(s.source_json["path"]).resolve()
            if not src.exists() or not src.is_dir():
                continue
            link = skills_root / src.name
            try:
                link.symlink_to(src)
            except FileExistsError:
                pass
            except OSError:
                # Fallback: filesystem doesn't allow symlinks → copy
                import shutil as _sh
                _sh.copytree(src, link, symlinks=False, dirs_exist_ok=True)
        return sandbox

    async def _stream_via_sdk(self, user_text: str, files: list[dict[str, Any]]) -> AsyncIterator[StreamEvent]:
        from claude_agent_sdk import query, ClaudeAgentOptions  # type: ignore
        import shutil as _shutil

        model = self.ctx.model
        if not model:
            yield StreamEvent("error", {"message": "未配置默认模型"})
            return

        # Build SDK options
        mcp_servers = build_mcp_servers(self.ctx.mcps)

        # Per-Agent Skill sandbox (filesystem isolation per official SDK docs).
        sandbox = self._build_skill_sandbox()

        # === Tool whitelist (security hardening) ===
        # Read-only + Skill + WebSearch are safe defaults. Bash/Write/Edit/NotebookEdit/
        # WebFetch are GLOBALLY DENIED — even if a SKILL.md instructs the model to
        # `bash xxx`, the SDK will refuse because Bash is not in allowed_tools.
        # MCP tools are added per-server: `mcp__<server>` allows all that server's tools.
        allowed_tools: list[str] = ["Read", "Glob", "Grep", "Skill", "WebSearch"]
        for mcp in self.ctx.mcps:
            if mcp.enabled:
                allowed_tools.append(f"mcp__{mcp.name}")

        options_kwargs: dict[str, Any] = {
            "model": model.model_id,
            "system_prompt": self._system_prompt(user_text),
            "include_partial_messages": True,
            # Auto-approve tools that ARE in allowed_tools (no CLI prompt) — anything not
            # in allowed_tools is denied entirely, regardless of permission_mode.
            "permission_mode": "bypassPermissions",
            "allowed_tools": allowed_tools,
            "max_turns": max(1, int(getattr(self.ctx.agent, "max_turns", 15) or 15)),
            # Belt-and-suspenders: explicitly disallow the dangerous trio in case some
            # SDK version honors disallowed_tools as an extra deny list.
            "disallowed_tools": ["Bash", "Write", "Edit", "NotebookEdit", "WebFetch"],
        }
        if mcp_servers:
            options_kwargs["mcp_servers"] = mcp_servers
        if sandbox is not None:
            options_kwargs["cwd"] = str(sandbox)
            options_kwargs["setting_sources"] = ["project"]
        if model.api_key_enc:
            options_kwargs["api_key"] = decrypt_str(model.api_key_enc)
        if model.base_url:
            options_kwargs["base_url"] = model.base_url

        # Effort → extended-thinking budget. The SDK exposes this via env var or
        # an `extra_args` passthrough depending on version, so we set it on
        # both options and an env hint for the spawned CLI process.
        effort = (getattr(self.ctx.agent, "effort", "medium") or "medium").lower()
        thinking_budget = _effort_to_thinking_budget(effort)
        if thinking_budget:
            options_kwargs["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget}
            try:
                import os as _os
                _os.environ.setdefault("CLAUDE_THINKING_BUDGET", str(thinking_budget))
            except Exception:
                pass

        # Filter to only kwargs the installed SDK actually accepts
        sdk_arg_names = ClaudeAgentOptions.__init__.__code__.co_varnames
        options = ClaudeAgentOptions(**{k: v for k, v in options_kwargs.items() if k in sdk_arg_names})

        prompt = user_text
        if files:
            prompt += self._render_attachments(files)

        # Prepend prior conversation as a transcript so the model has context.
        # (Claude Agent SDK's query() takes a single prompt; we concatenate.)
        if self.ctx.history:
            transcript_parts = []
            for h in self.ctx.history:
                txt = (h.content_json or {}).get("text") if isinstance(h.content_json, dict) else None
                if not txt:
                    continue
                role = "用户" if h.role == "user" else "助手"
                transcript_parts.append(f"{role}: {txt}")
            if transcript_parts:
                transcript = "\n\n".join(transcript_parts)
                prompt = (
                    "以下是此前的对话历史(供你理解上下文,不要在回答里重复):\n\n"
                    f"{transcript}\n\n---\n\n用户: {prompt}"
                )

        # Track current streaming tool_use block (id-keyed input JSON accumulator)
        current_tool_id: str | None = None
        current_tool_name: str | None = None
        current_tool_input_buf: str = ""

        try:
            async for msg in query(prompt=prompt, options=options):
                mtype = type(msg).__name__

                # ---- partial streaming events (token-level) ----
                if mtype == "StreamEvent" or mtype == "SDKPartialAssistantMessage":
                    event = getattr(msg, "event", None) or {}
                    et = event.get("type")
                    if et == "content_block_start":
                        cb = event.get("content_block", {}) or {}
                        if cb.get("type") == "tool_use":
                            current_tool_id = cb.get("id")
                            current_tool_name = cb.get("name")
                            current_tool_input_buf = ""
                            yield StreamEvent("tool_use", {
                                "id": current_tool_id, "name": current_tool_name, "input": {},
                            })
                        elif cb.get("type") == "thinking":
                            # thinking block start - nothing to emit yet
                            pass
                    elif et == "content_block_delta":
                        delta = event.get("delta", {}) or {}
                        dt = delta.get("type")
                        if dt == "text_delta":
                            chunk = delta.get("text", "")
                            if chunk:
                                yield StreamEvent("text", {"text": chunk})
                        elif dt == "thinking_delta":
                            chunk = delta.get("thinking", "")
                            if chunk:
                                yield StreamEvent("thinking", {"text": chunk})
                        elif dt == "input_json_delta":
                            current_tool_input_buf += delta.get("partial_json", "")
                    elif et == "content_block_stop":
                        if current_tool_id is not None:
                            try:
                                import json as _json
                                parsed = _json.loads(current_tool_input_buf) if current_tool_input_buf else {}
                            except Exception:
                                parsed = {"raw": current_tool_input_buf}
                            # update step with final input
                            yield StreamEvent("tool_use", {
                                "id": current_tool_id, "name": current_tool_name, "input": parsed,
                            })
                            current_tool_id = None
                            current_tool_name = None
                            current_tool_input_buf = ""
                    # message_start / message_delta / message_stop ignored

                # ---- user-side messages carry tool results from SDK's tool execution loop ----
                elif mtype == "UserMessage":
                    for block in getattr(msg, "content", []) or []:
                        btype = type(block).__name__
                        if btype == "ToolResultBlock":
                            tr_content = str(getattr(block, "content", ""))
                            await self._maybe_register_files_from_tool_result(tr_content)
                            yield StreamEvent("tool_result", {
                                "tool_use_id": getattr(block, "tool_use_id", ""),
                                "content": tr_content,
                            })

                # ---- complete assistant message: only used as a fallback if partials were skipped ----
                elif mtype == "AssistantMessage":
                    # If partials are working, we already streamed text. Skip text re-emit.
                    # We still surface tool_result blocks here defensively (some SDK versions place them here).
                    for block in getattr(msg, "content", []) or []:
                        btype = type(block).__name__
                        if btype == "ToolResultBlock":
                            tr_content = str(getattr(block, "content", ""))
                            await self._maybe_register_files_from_tool_result(tr_content)
                            yield StreamEvent("tool_result", {
                                "tool_use_id": getattr(block, "tool_use_id", ""),
                                "content": tr_content,
                            })

                elif mtype == "ResultMessage":
                    usage = getattr(msg, "usage", None) or {}
                    if isinstance(usage, dict):
                        self._tokens_in = usage.get("input_tokens", 0)
                        self._tokens_out = usage.get("output_tokens", 0)
        finally:
            if sandbox is not None:
                _shutil.rmtree(sandbox, ignore_errors=True)
