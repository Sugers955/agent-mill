"""DAG executor for composite skills.

Uses asyncio.gather per topological layer for parallelism.
Template variable substitution: only on string leaves of `input` dicts,
syntax: {{step_id.field}} or {{trigger.field}}. NEVER eval'd.
"""
from __future__ import annotations
import asyncio
import re
from typing import Any, Awaitable, Callable
from .skill_loader import topo_layers

VAR_RE = re.compile(r"\{\{\s*([a-zA-Z_][\w.]*)\s*\}\}")


def _resolve_path(ctx: dict[str, Any], path: str) -> Any:
    cur: Any = ctx
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _substitute(value: Any, ctx: dict[str, Any]) -> Any:
    if isinstance(value, str):
        # full-match: return raw object (preserves type)
        m = VAR_RE.fullmatch(value.strip())
        if m:
            return _resolve_path(ctx, m.group(1))
        return VAR_RE.sub(lambda mm: str(_resolve_path(ctx, mm.group(1)) or ""), value)
    if isinstance(value, dict):
        return {k: _substitute(v, ctx) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute(v, ctx) for v in value]
    return value


SkillCallable = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


class DAGExecutor:
    """Execute a composite skill's DAG.

    `skill_runner(skill_code, input_dict) -> output_dict` is provided by the runtime
    and is responsible for actually invoking atomic skills (or nested composites).
    """

    def __init__(self, skill_runner: SkillCallable):
        self.run_skill = skill_runner

    async def execute(self, definition: dict[str, Any], trigger: dict[str, Any]) -> dict[str, Any]:
        steps = definition.get("steps", [])
        ctx: dict[str, Any] = {"trigger": trigger}
        for layer in topo_layers(steps):
            results = await asyncio.gather(*(self._run_step(st, ctx) for st in layer))
            for st, out in zip(layer, results):
                ctx[st["id"]] = out
        # final result: last step output, or all step outputs
        last = steps[-1]["id"] if steps else None
        return {
            "final": ctx.get(last) if last else None,
            "steps": {sid: ctx[sid] for sid in ctx if sid != "trigger"},
        }

    async def _run_step(self, step: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        skill_code = step["skill"]
        input_data = _substitute(step.get("input", {}) or {}, ctx)
        return await self.run_skill(skill_code, input_data)
