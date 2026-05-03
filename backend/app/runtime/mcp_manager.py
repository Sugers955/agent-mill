"""MCP connector manager - converts DB rows to Claude Agent SDK MCP server configs,
and provides a live `list_tools` helper using the official `mcp` Python SDK.
"""
from __future__ import annotations
import asyncio
from contextlib import AsyncExitStack
from typing import Any
from ..db.models import MCPConnector


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
