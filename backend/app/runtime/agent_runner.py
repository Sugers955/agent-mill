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
import yaml
from dataclasses import dataclass
from typing import Any, AsyncIterator
from ..db.models import Agent, Skill, MCPConnector, Model, Message
from ..core.crypto import decrypt_str
from .dag_executor import DAGExecutor
from .mcp_manager import build_mcp_servers


@dataclass
class AgentContext:
    agent: Agent
    skills: list[Skill]
    mcps: list[MCPConnector]
    model: Model | None
    fallback_model: Model | None
    history: list[Message]


@dataclass
class StreamEvent:
    type: str  # "text" | "tool_use" | "tool_result" | "error" | "done" | "usage"
    data: Any


class AgentRunner:
    """Wraps Claude Agent SDK invocation with our skill/MCP/model config."""

    def __init__(self, ctx: AgentContext):
        self.ctx = ctx
        self._tokens_in = 0
        self._tokens_out = 0

    async def _run_atomic_skill(self, skill: Skill, input_data: dict[str, Any]) -> dict[str, Any]:
        """Invoke an atomic skill out-of-band (used by composite DAG only)."""
        src = skill.source_json or {}
        if "callable" in src:
            # dotted path import: module.submod:func
            import importlib
            mod_path, _, func_name = src["callable"].partition(":")
            mod = importlib.import_module(mod_path)
            func = getattr(mod, func_name)
            result = func(**input_data) if not asyncio.iscoroutinefunction(func) else await func(**input_data)
            if not isinstance(result, dict):
                result = {"value": result}
            return result
        # path-based atomic skill: in MVP we only return a placeholder; real execution
        # happens via the SDK when the agent invokes it directly.
        return {"note": "atomic skill executed via SDK", "skill": skill.code, "input": input_data}

    async def _run_skill_by_code(self, skill_code: str, input_data: dict[str, Any]) -> dict[str, Any]:
        skill = next((s for s in self.ctx.skills if s.code == skill_code), None)
        if not skill:
            return {"error": f"skill not found: {skill_code}"}
        if skill.type == "atomic":
            return await self._run_atomic_skill(skill, input_data)
        # composite (nested)
        definition = yaml.safe_load(skill.source_json.get("yaml", "")) or {}
        executor = DAGExecutor(self._run_skill_by_code)
        return await executor.execute(definition, input_data)

    def _system_prompt(self) -> str:
        parts = [self.ctx.agent.system_prompt or ""]
        if self.ctx.skills:
            parts.append("\n## 你可使用的 Skills\n")
            for s in self.ctx.skills:
                tag = "组合" if s.type == "composite" else "原子"
                parts.append(f"- **{s.code}** ({tag}): {s.description or '(无描述)'}")
        return "\n".join(parts).strip()

    def _build_openai_tools(self) -> list[dict[str, Any]]:
        """Expose composite + callable skills as OpenAI function-calling tools.

        Path-based atomic skills require filesystem access and are only described in
        the system prompt (not invocable from OpenAI-compatible providers).
        """
        tools: list[dict[str, Any]] = []
        for s in self.ctx.skills:
            if s.type == "composite" or (s.type == "atomic" and (s.source_json or {}).get("callable")):
                tools.append({
                    "type": "function",
                    "function": {
                        "name": s.code,
                        "description": s.description or s.name,
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "input": {"type": "object", "description": "Skill 输入(任意 JSON 对象)"},
                            },
                            "additionalProperties": True,
                        },
                    },
                })
        return tools

    async def _exec_skill(self, skill_code: str, args: dict[str, Any]) -> dict[str, Any]:
        skill = next((s for s in self.ctx.skills if s.code == skill_code), None)
        if not skill:
            return {"error": f"unknown skill: {skill_code}"}
        # The model often passes args as {"input": {...}} or directly as the trigger dict.
        trigger = args.get("input") if isinstance(args, dict) and "input" in args else args
        if not isinstance(trigger, dict):
            trigger = {"value": trigger}
        return await self._run_skill_by_code(skill_code, trigger)

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
        try:
            if provider == "anthropic":
                async for ev in self._stream_via_sdk(user_text, files or []):
                    yield ev
            else:
                async for ev in self._stream_via_openai(user_text, files or []):
                    yield ev
        except ImportError as e:
            yield StreamEvent("error", {"message": f"SDK 未安装: {e}"})
        except Exception as e:  # noqa: BLE001
            yield StreamEvent("error", {"message": f"agent 执行错误: {e}"})
        finally:
            yield StreamEvent("done", {
                "tokens_in": self._tokens_in,
                "tokens_out": self._tokens_out,
                "latency_ms": int((time.time() - start) * 1000),
            })

    PROVIDER_BASE_URL: dict[str, str] = {
        "deepseek": "https://api.deepseek.com/v1",
        "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "glm": "https://open.bigmodel.cn/api/paas/v4",
    }

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
        import json as _json

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

        system = self._system_prompt() or "You are a helpful assistant."
        prompt = user_text
        if files:
            prompt += "\n\n[附件]\n" + "\n".join(f"- {f['name']} ({f['path']})" for f in files)

        tools = self._build_openai_tools()
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]

        # multi-turn loop: model may call skill tools, we execute and feed results back
        MAX_ITER = 8
        for _ in range(MAX_ITER):
            create_kwargs: dict[str, Any] = {
                "model": model.model_id,
                "messages": messages,
                "stream": True,
                "stream_options": {"include_usage": True},
            }
            if tools:
                create_kwargs["tools"] = tools

            stream = await client.chat.completions.create(**create_kwargs)

            # accumulate this turn
            text_buf = ""
            tool_calls_acc: dict[int, dict[str, Any]] = {}  # index -> {id, name, arguments}
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
                                    # surface as a streaming tool_use start (we'll re-emit on finish with full input)
                                    if slot.get("id") and slot.get("name"):
                                        yield StreamEvent("tool_use", {
                                            "id": slot["id"], "name": slot["name"], "input": {},
                                        })
                    if choice.finish_reason:
                        finish_reason = choice.finish_reason

            # if no tool calls, we're done
            if not tool_calls_acc:
                return

            # record assistant message with tool_calls to feed back
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
            messages.append(assistant_msg)

            # execute each tool call
            for slot in tool_calls_acc.values():
                if not (slot.get("id") and slot.get("name")):
                    continue
                try:
                    args = _json.loads(slot["arguments"] or "{}")
                except Exception:
                    args = {"raw": slot["arguments"]}
                # emit final tool_use with full input
                yield StreamEvent("tool_use", {"id": slot["id"], "name": slot["name"], "input": args})
                try:
                    result = await self._exec_skill(slot["name"], args)
                except Exception as e:  # noqa: BLE001
                    result = {"error": str(e)}
                result_str = _json.dumps(result, ensure_ascii=False, default=str)
                yield StreamEvent("tool_result", {"tool_use_id": slot["id"], "content": result_str})
                messages.append({
                    "role": "tool", "tool_call_id": slot["id"],
                    "content": result_str,
                })
            # loop back: feed tool results to the model for the next turn

        yield StreamEvent("error", {"message": f"Skill 调用循环超过 {MAX_ITER} 轮,已强制中断"})

    async def _stream_via_sdk(self, user_text: str, files: list[dict[str, Any]]) -> AsyncIterator[StreamEvent]:
        from claude_agent_sdk import query, ClaudeAgentOptions  # type: ignore

        model = self.ctx.model
        if not model:
            yield StreamEvent("error", {"message": "未配置默认模型"})
            return

        # Build SDK options
        mcp_servers = build_mcp_servers(self.ctx.mcps)
        # Skills: SDK uses `skills` (list of skill names) + `add_dirs` (where to find them)
        # We accept atomic skills with a directory path under STORAGE/skills/
        from pathlib import Path as _Path
        skill_names: list[str] = []
        skill_dirs: set[str] = set()
        for s in self.ctx.skills:
            if s.type == "atomic":
                p = (s.source_json or {}).get("path")
                if p:
                    pp = _Path(p)
                    skill_names.append(pp.name)
                    skill_dirs.add(str(pp.parent))

        options_kwargs: dict[str, Any] = {
            "model": model.model_id,
            "system_prompt": self._system_prompt(),
            "include_partial_messages": True,
        }
        if mcp_servers:
            options_kwargs["mcp_servers"] = mcp_servers
        if skill_names:
            options_kwargs["skills"] = skill_names
        if skill_dirs:
            options_kwargs["add_dirs"] = list(skill_dirs)
        if model.api_key_enc:
            options_kwargs["api_key"] = decrypt_str(model.api_key_enc)
        if model.base_url:
            options_kwargs["base_url"] = model.base_url

        # Filter to only kwargs the installed SDK actually accepts
        sdk_arg_names = ClaudeAgentOptions.__init__.__code__.co_varnames
        options = ClaudeAgentOptions(**{k: v for k, v in options_kwargs.items() if k in sdk_arg_names})

        prompt = user_text
        if files:
            prompt += "\n\n[附件]\n" + "\n".join(f"- {f['name']} ({f['path']})" for f in files)

        # Track current streaming tool_use block (id-keyed input JSON accumulator)
        current_tool_id: str | None = None
        current_tool_name: str | None = None
        current_tool_input_buf: str = ""

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
                        yield StreamEvent("tool_result", {
                            "tool_use_id": getattr(block, "tool_use_id", ""),
                            "content": str(getattr(block, "content", "")),
                        })

            # ---- complete assistant message: only used as a fallback if partials were skipped ----
            elif mtype == "AssistantMessage":
                # If partials are working, we already streamed text. Skip text re-emit.
                # We still surface tool_result blocks here defensively (some SDK versions place them here).
                for block in getattr(msg, "content", []) or []:
                    btype = type(block).__name__
                    if btype == "ToolResultBlock":
                        yield StreamEvent("tool_result", {
                            "tool_use_id": getattr(block, "tool_use_id", ""),
                            "content": str(getattr(block, "content", "")),
                        })

            elif mtype == "ResultMessage":
                usage = getattr(msg, "usage", None) or {}
                if isinstance(usage, dict):
                    self._tokens_in = usage.get("input_tokens", 0)
                    self._tokens_out = usage.get("output_tokens", 0)
