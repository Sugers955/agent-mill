"""MCP (Model Context Protocol) client utilities.

Extracted from agent_runner.py to encapsulate MCP connection management,
tool invocation, and one-shot patterns.
"""
from __future__ import annotations
import json as _json
import re as _re
from contextlib import AsyncExitStack
from typing import Any


def prefix_mcp_actions(ui_schema: dict[str, Any], mcp_name: str) -> None:
    """Rewrite `action.tool` entries from bare names to `mcp__<server>__<tool>`.

    MCP authors often write `tool: "init_booking"` in their UI Schema actions
    without knowing about our `mcp__<server>__` namespacing. We rewrite in-place
    so the [UI_ACTION] router resolves back to THIS MCP, not a same-named tool
    elsewhere. Already-prefixed tool names (any `mcp__...`) are left alone.
    """
    prefix = f"mcp__{mcp_name}__"
    for a in (ui_schema.get("actions") or []):
        if not isinstance(a, dict):
            continue
        t = a.get("tool")
        if isinstance(t, str) and t and not t.startswith("mcp__"):
            a["tool"] = prefix + t


def mcp_tool_name(server: str, tool: str) -> str:
    """Generate `mcp__<server>__<tool>` format name, sanitized for OpenAI."""
    # OpenAI function names allow [a-zA-Z0-9_-], must be <= 64 chars.
    clean = _re.sub(r"[^a-zA-Z0-9_-]", "_", f"mcp__{server}__{tool}")
    return clean[:64]


async def open_mcp_session(stack: AsyncExitStack, mcp: Any) -> Any:
    """Open an MCP ClientSession for the given MCPConnector row."""
    from mcp import ClientSession
    cfg = mcp.config_json or {}
    if mcp.transport == "stdio":
        from mcp import StdioServerParameters
        from mcp.client.stdio import stdio_client
        params = StdioServerParameters(
            command=cfg.get("command") or "",
            args=cfg.get("args", []) or [],
            env=cfg.get("env") or None,
        )
        read, write = await stack.enter_async_context(stdio_client(params))
    elif mcp.transport == "sse":
        from mcp.client.sse import sse_client
        read, write = await stack.enter_async_context(
            sse_client(cfg.get("url"), headers=cfg.get("headers") or None)
        )
    elif mcp.transport == "http":
        from mcp.client.streamable_http import streamablehttp_client
        ctx = await stack.enter_async_context(
            streamablehttp_client(cfg.get("url"), headers=cfg.get("headers") or None)
        )
        read, write = ctx[0], ctx[1]
    else:
        raise ValueError(f"unsupported transport: {mcp.transport}")
    session = await stack.enter_async_context(ClientSession(read, write))
    await session.initialize()
    return session


async def call_mcp_tool(session: Any, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Call an MCP tool and convert result to JSON-serializable dict."""
    # Drop the OpenAI-style {"input": {...}} wrapper if the model added one
    call_args = args.get("input") if isinstance(args, dict) and "input" in args and len(args) == 1 else args
    if not isinstance(call_args, dict):
        call_args = {"value": call_args}
    result = await session.call_tool(tool_name, call_args)
    # Convert MCP CallToolResult → JSON-serialisable dict
    out_parts: list[str] = []
    for c in (result.content or []):
        text = getattr(c, "text", None)
        if text is not None:
            out_parts.append(text)
        else:
            out_parts.append(str(c))
    return {
        "isError": bool(getattr(result, "isError", False)),
        "content": "\n".join(out_parts),
    }


async def with_mcp_session(mcp: Any, fn: Any) -> Any:
    """Open + initialize an MCP session, run `fn(session)`, close. All in one task.

    Avoids the anyio "cancel scope in different task" error that occurs when an
    AsyncExitStack is held across an async generator's lifetime in FastAPI streams.
    """
    from mcp import ClientSession
    cfg = mcp.config_json or {}
    async with AsyncExitStack() as stack:
        if mcp.transport == "stdio":
            from mcp import StdioServerParameters
            from mcp.client.stdio import stdio_client
            params = StdioServerParameters(
                command=cfg.get("command") or "",
                args=cfg.get("args", []) or [],
                env=cfg.get("env") or None,
            )
            read, write = await stack.enter_async_context(stdio_client(params))
        elif mcp.transport == "sse":
            from mcp.client.sse import sse_client
            read, write = await stack.enter_async_context(
                sse_client(cfg.get("url"), headers=cfg.get("headers") or None)
            )
        elif mcp.transport == "http":
            from mcp.client.streamable_http import streamablehttp_client
            ctx = await stack.enter_async_context(
                streamablehttp_client(cfg.get("url"), headers=cfg.get("headers") or None)
            )
            read, write = ctx[0], ctx[1]
        else:
            raise ValueError(f"unsupported transport: {mcp.transport}")
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        return await fn(session)


async def list_mcp_tools_once(mcp: Any) -> list[dict[str, Any]]:
    """One-shot: connect, list tools, disconnect."""
    async def _do(session):
        tools_resp = await session.list_tools()
        return [
            {
                "name": t.name,
                "description": t.description or "",
                "input_schema": getattr(t, "inputSchema", None) or {},
            }
            for t in tools_resp.tools
        ]
    return await with_mcp_session(mcp, _do)


async def call_mcp_tool_once(mcp: Any, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """One-shot: connect, call tool, disconnect.

    Includes UI Schema extraction and MCP action prefix injection.
    """
    # Drop the OpenAI-style {"input": {...}} wrapper if the model added one
    call_args = args.get("input") if isinstance(args, dict) and "input" in args and len(args) == 1 else args
    if not isinstance(call_args, dict):
        call_args = {"value": call_args}

    async def _do(session):
        result = await session.call_tool(tool_name, call_args)
        out_parts: list[str] = []
        for c in (result.content or []):
            text = getattr(c, "text", None)
            if text is not None:
                out_parts.append(text)
            else:
                out_parts.append(str(c))
        content_str = "\n".join(out_parts)
        wrapped: dict[str, Any] = {
            "isError": bool(getattr(result, "isError", False)),
            "content": content_str,
        }
        # If the tool returned JSON whose top-level dict contains __ui__,
        # lift the schema (and surface fields) so the runtime's
        # extract_ui_schema() sees it. Tools may return JSON or plain text.
        stripped = content_str.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                parsed = _json.loads(stripped)
                if isinstance(parsed, dict):
                    if "__ui__" in parsed:
                        ui = parsed["__ui__"]
                        # Auto-prefix bare tool names in actions with mcp__<server>__
                        # so the [UI_ACTION] route resolves to THIS server, not a
                        # same-named tool from another MCP / Skill.
                        if isinstance(ui, dict):
                            prefix_mcp_actions(ui, mcp.name)
                        wrapped["__ui__"] = ui
                    wrapped["data"] = {k: v for k, v in parsed.items() if k != "__ui__"}
            except Exception:
                pass
        return wrapped
    return await with_mcp_session(mcp, _do)
