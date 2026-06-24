"""UI Schema types + helpers.

Schemas are dict-based at runtime (kept loose so adapters / Skills / MCPs can
emit them without a hard Pydantic dependency). This file documents the shape
and provides a single entry point `extract_ui_schema(tool_result)` used by the
runtime to decide whether a tool result should surface as a UI message.

Schema reference: see project docs / README "UI Schema 渲染引擎".
"""
from __future__ import annotations
from typing import Any, Iterable
import secrets
import time

# Top-level component types the frontend ComponentRegistry knows about.
# Frontend ignores unknown types and falls back to JSON pre-block.
KNOWN_COMPONENT_TYPES: set[str] = {
    "CardList",
    "DynamicForm",
    "ConfirmDialog",
    "DataTable",
    "StatusTimeline",
}


def make_surface_id(tool_name: str | None = None) -> str:
    base = (tool_name or "ui").replace(".", "_").replace("/", "_")[:32]
    ts = int(time.time() * 1000)
    rand = secrets.token_hex(4)
    return f"{base}_{ts}_{rand}"


def extract_ui_schema(tool_result: Any, *, tool_name: str | None = None) -> dict | None:
    """Return a normalised UI message dict if the tool result contains one.

    Conventions accepted:
    1. result has a `__ui__` key whose value is the schema (or list of schemas)
    2. result IS the schema itself (has `message_type == 'ui'` at top level)
    Otherwise returns None.
    """
    if not isinstance(tool_result, dict):
        return None
    candidate = None
    if "__ui__" in tool_result and isinstance(tool_result["__ui__"], (dict, list)):
        candidate = tool_result["__ui__"]
    elif tool_result.get("message_type") == "ui":
        candidate = tool_result
    if candidate is None:
        return None
    # Allow lists too, but we normalise to a single dict (first one) for now.
    if isinstance(candidate, list):
        candidate = candidate[0] if candidate else None
    if not isinstance(candidate, dict):
        return None
    return _normalise(candidate, tool_name=tool_name)


def _normalise(schema: dict, *, tool_name: str | None) -> dict:
    out = dict(schema)
    out.setdefault("message_type", "ui")
    out.setdefault("surface_id", make_surface_id(tool_name))
    out.setdefault("data_model", {})
    out.setdefault("components", [])
    out.setdefault("actions", [])
    return out


def strip_ui_for_model(tool_result: dict) -> dict:
    """Return a copy of the tool result safe to feed back to the LLM.

    Removes the `__ui__` blob (which may be huge) and replaces it with a tiny
    summary so the model knows a UI was rendered without re-reading the data.
    Also strips runtime-only flags like `__halt__`.
    """
    if not isinstance(tool_result, dict):
        return tool_result
    if "__ui__" not in tool_result and tool_result.get("message_type") != "ui":
        return tool_result
    cleaned = {k: v for k, v in tool_result.items() if k not in ("__ui__", "__halt__")}
    cleaned.setdefault("__ui_rendered__", True)
    return cleaned


def whitelist_tool_names(skills: Iterable, mcp_tool_routes: dict) -> set[str]:
    """Return the set of tool names allowed by [UI_ACTION] route guard.

    Includes Skill codes + MCP exposed tool names. Used by chat.py to validate
    user-submitted [UI_ACTION] calls — frontend must not call arbitrary tools.
    """
    names: set[str] = set()
    for s in skills:
        if getattr(s, "code", None):
            names.add(s.code)
    names.update(mcp_tool_routes.keys())
    # Built-in helpers also allowed
    names.update({
        "save_output_file", "_read_skill_file", "run_skill_script",
        "load_widget_guidelines",
        "ask_user_pick", "ask_user_form",
    })
    return names
