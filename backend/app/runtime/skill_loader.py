"""Skill loader: validate composite YAML, build virtual Skill descriptors.

Design notes:
- Atomic skills are loaded by SDK from a directory (`source_json.path`) or registered as
  in-process Python callables (`source_json.callable` -> dotted import path).
- Composite skills are described in YAML (steps + depends_on) and exposed to the Agent
  as a single virtual skill. When the agent invokes it, DAGExecutor runs the steps.
"""
from __future__ import annotations
from typing import Any
from fastapi import HTTPException


COMPOSITE_REQUIRED = {"name", "description", "steps"}
STEP_REQUIRED = {"id", "skill"}


def validate_composite_yaml(data: dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise HTTPException(400, "YAML 顶层必须是对象")
    missing = COMPOSITE_REQUIRED - set(data.keys())
    if missing:
        raise HTTPException(400, f"缺少字段: {sorted(missing)}")
    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        raise HTTPException(400, "steps 必须是非空数组")
    ids: set[str] = set()
    for i, st in enumerate(steps):
        if not isinstance(st, dict):
            raise HTTPException(400, f"step[{i}] 必须是对象")
        miss = STEP_REQUIRED - set(st.keys())
        if miss:
            raise HTTPException(400, f"step[{i}] 缺少: {sorted(miss)}")
        if st["id"] in ids:
            raise HTTPException(400, f"重复的 step id: {st['id']}")
        ids.add(st["id"])
    # depends_on must reference existing ids
    for st in steps:
        for dep in st.get("depends_on", []) or []:
            if dep not in ids:
                raise HTTPException(400, f"step {st['id']} 依赖不存在的 id: {dep}")
    # detect cycles via DFS
    graph = {st["id"]: list(st.get("depends_on", []) or []) for st in steps}
    visiting: set[str] = set()
    visited: set[str] = set()

    def dfs(node: str) -> None:
        if node in visited:
            return
        if node in visiting:
            raise HTTPException(400, f"step 循环依赖: {node}")
        visiting.add(node)
        for n in graph[node]:
            dfs(n)
        visiting.discard(node)
        visited.add(node)

    for n in graph:
        dfs(n)


def topo_layers(steps: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Return parallel-execution layers (Kahn's algorithm)."""
    by_id = {s["id"]: s for s in steps}
    indeg = {s["id"]: len(s.get("depends_on", []) or []) for s in steps}
    rev: dict[str, list[str]] = {sid: [] for sid in by_id}
    for s in steps:
        for dep in s.get("depends_on", []) or []:
            rev[dep].append(s["id"])
    layers: list[list[dict[str, Any]]] = []
    ready = [sid for sid, d in indeg.items() if d == 0]
    while ready:
        layers.append([by_id[sid] for sid in ready])
        next_ready: list[str] = []
        for sid in ready:
            for n in rev[sid]:
                indeg[n] -= 1
                if indeg[n] == 0:
                    next_ready.append(n)
        ready = next_ready
    return layers
