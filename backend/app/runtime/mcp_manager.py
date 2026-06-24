"""MCP connector manager - converts DB rows to Claude Agent SDK MCP server configs,
and provides a live `list_tools` helper using the official `mcp` Python SDK.
"""
from __future__ import annotations
import asyncio
import re
from contextlib import AsyncExitStack
from typing import Any
from ..db.models import MCPConnector

# Allowed MCP stdio commands (binary names or full paths)
_ALLOWED_MCP_COMMANDS: set[str] = {
    # Add safe MCP server commands here, e.g.:
    # "npx", "node", "python", "python3",
}

# Blocked dangerous commands/args patterns
_BLOCKED_MCP_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(rm|dd|mkfs|format|shutdown|reboot|halt)\b"),
    re.compile(r"[;&|`$]"),  # shell metacharacters
    re.compile(r"\.\./"),     # path traversal
]


def validate_mcp_config(config: dict, transport: str) -> str | None:
    """Validate MCP configuration. Returns error message or None."""
    if transport == "stdio":
        cmd = config.get("command", "")
        args = config.get("args", [])
        if not cmd:
            return "stdio transport requires 'command'"
        # Check command is in whitelist (empty whitelist = reject all)
        if cmd not in _ALLOWED_MCP_COMMANDS:
            return f"command '{cmd}' not in whitelist"
        # Check args for dangerous patterns
        full_cmd = f"{cmd} {' '.join(str(a) for a in args)}"
        for pattern in _BLOCKED_MCP_PATTERNS:
            if pattern.search(full_cmd):
                return f"command contains blocked pattern: {pattern.pattern}"
    elif transport in ("sse", "http"):
        url = config.get("url", "")
        if not url:
            return f"{transport} transport requires 'url'"
        # Block internal network access (basic check)
        if re.search(r"localhost|127\.0\.0\.1|0\.0\.0\.0|10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.", url):
            return "internal network URLs are not allowed"
    return None


def to_sdk_config(mcp: MCPConnector) -> dict[str, Any]:
    cfg = mcp.config_json or {}
    if mcp.transport == "stdio":
        return {
            "type": "stdio",
            "command": cfg.get("command"),
            "args": cfg.get("args", []),
            "env": cfg.get("env", {}),
        }
    if mcp.transport == "sse":
        return {"type": "sse", "url": cfg.get("url"), "headers": cfg.get("headers", {})}
    if mcp.transport == "http":
        return {"type": "http", "url": cfg.get("url"), "headers": cfg.get("headers", {})}
    raise ValueError(f"unknown transport: {mcp.transport}")


def build_mcp_servers(mcps: list[MCPConnector]) -> dict[str, Any]:
    return {m.name: to_sdk_config(m) for m in mcps if m.enabled}


async def list_mcp_tools(mcp: MCPConnector, timeout: float = 15.0) -> dict[str, Any]:
    """Connect to the MCP server and return its server info + tool list.

    Returns: {"server": {"name": str, "version": str}, "tools": [...]}
    """
    cfg = mcp.config_json or {}

    async def _do() -> dict[str, Any]:
        from mcp import ClientSession
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
                # streamablehttp returns (read, write, get_session_id)
                read, write = ctx[0], ctx[1]
            else:
                raise ValueError(f"unsupported transport: {mcp.transport}")

            session = await stack.enter_async_context(ClientSession(read, write))
            init_result = await session.initialize()
            tools_result = await session.list_tools()
            tools = []
            for t in tools_result.tools:
                tools.append({
                    "name": t.name,
                    "description": t.description or "",
                    "input_schema": getattr(t, "inputSchema", None) or {},
                })
            server_info = getattr(init_result, "serverInfo", None)
            return {
                "server": {
                    "name": getattr(server_info, "name", mcp.name) if server_info else mcp.name,
                    "version": getattr(server_info, "version", "") if server_info else "",
                },
                "tools": tools,
            }

    return await asyncio.wait_for(_do(), timeout=timeout)
