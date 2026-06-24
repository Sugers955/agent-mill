"""Solution Pack execution engine.

Full-featured declarative DAG runtime for business workflows described in YAML.
This is intentionally SEPARATE from the existing composite Skill DAG executor:
- composite Skill = lightweight, synchronous, internal helper DAG
- Solution Pack = long-running, persisted, resumable business process with
  approvals, sub-agents, audit trace, and Pack-level progress streaming

MVP surface area implemented here:
- YAML parse + top-level validation
- DAG build + cycle detection
- 6 node executors (skill / parallel_group / aggregator / condition /
  sub_agent / human_approval) with stubs where external integration is not yet
  wired (e.g. notifications)
- Context snapshot / trace recording
- PackRun persistence hooks

This module DOES NOT tie directly to FastAPI; it is called by chat/runner and
returns streamable progress events.
"""
from __future__ import annotations
import asyncio
import ast
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator
import yaml
from sqlalchemy import select

from ..db.models import SolutionPack, PackRun, PackApproval, MCPConnector
from ..db.session import SessionLocal


# ---------------------------------------------------------------------------
# Public event shape (consumed by chat.py and persisted to message content_json)
# ---------------------------------------------------------------------------
@dataclass
class PackEvent:
    type: str   # pack_progress | pack_done | pack_waiting_approval | pack_error
    data: dict[str, Any]


# ---------------------------------------------------------------------------
# Execution Context — mirrored from the design doc
# ---------------------------------------------------------------------------
@dataclass
class ExecutionContext:
    pack_id: str
    run_id: str
    inputs: dict[str, Any]
    pack_code: str | None = None
    pack_db_id: int | None = None
    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    shared: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Pack Engine
# ---------------------------------------------------------------------------
class PackEngine:
    """High-level entry point for running / resuming Packs.

    Usage:
        async for ev in engine.start(pack_code, inputs, user_id, agent_id, conversation_id):
            ... emit SSE ...
    """

    def __init__(self, *, runner_factory=None):
        # runner_factory lets us call back into AgentRunner for skill execution
        self.runner_factory = runner_factory

    # ---------- YAML loading + validation ----------
    async def load_pack(self, pack_code: str) -> tuple[SolutionPack, dict[str, Any]]:
        async with SessionLocal() as db:
            row = (await db.execute(
                select(SolutionPack).where(SolutionPack.code == pack_code, SolutionPack.enabled.is_(True))
            )).scalar_one_or_none()
            if not row:
                raise ValueError(f"pack not found or disabled: {pack_code}")
            if row.spec_json:
                return row, row.spec_json
            spec = yaml.safe_load(row.yaml_text) or {}
            self.validate_pack(spec)
            row.spec_json = spec
            await db.commit()
            return row, spec

    def validate_pack(self, spec: dict[str, Any]) -> None:
        required = {"pack_id", "name", "version", "inputs", "outputs", "config", "nodes"}
        miss = required - set(spec.keys())
        if miss:
            raise ValueError(f"pack missing keys: {sorted(miss)}")
        if not isinstance(spec.get("nodes"), list) or not spec["nodes"]:
            raise ValueError("pack.nodes must be a non-empty list")
        ids: set[str] = set()
        for n in spec["nodes"]:
            nid = n.get("id")
            if not nid or not isinstance(nid, str):
                raise ValueError("each node must have string id")
            if nid in ids:
                raise ValueError(f"duplicate node id: {nid}")
            ids.add(nid)
        # cycle detect
        deps = {n["id"]: list(n.get("depends_on") or []) for n in spec["nodes"]}
        visiting, visited = set(), set()
        def dfs(node: str):
            if node in visited: return
            if node in visiting: raise ValueError(f"pack has cycle at node: {node}")
            visiting.add(node)
            for d in deps[node]:
                if d not in deps:
                    raise ValueError(f"node {node} depends on missing {d}")
                dfs(d)
            visiting.remove(node)
            visited.add(node)
        for nid in deps: dfs(nid)

    # ---------- Start / resume ----------
    async def start(self, pack_code: str, inputs: dict[str, Any], *, user_id: int | None,
                    agent_id: int | None, conversation_id: int | None) -> AsyncIterator[PackEvent]:
        pack_row, spec = await self.load_pack(pack_code)
        run_id = uuid.uuid4().hex
        ctx = ExecutionContext(
            pack_id=spec["pack_id"],
            run_id=run_id,
            inputs=inputs or {},
            pack_code=pack_row.code,
            pack_db_id=pack_row.id,
        )
        await self._persist_run(run_id, pack_db_id=pack_row.id, ctx=ctx, user_id=user_id, agent_id=agent_id,
                                conversation_id=conversation_id, status="running")
        async for ev in self._execute(spec, ctx, user_id=user_id, agent_id=agent_id,
                                      conversation_id=conversation_id):
            yield ev

    async def resume(self, run_id: str, *, approval_decision: str | None = None,
                     approval_reason: str | None = None, approver_id: int | None = None) -> AsyncIterator[PackEvent]:
        async with SessionLocal() as db:
            row = (await db.execute(select(PackRun).where(PackRun.run_id == run_id))).scalar_one_or_none()
            if not row:
                raise ValueError(f"run not found: {run_id}")
            spec_row = (await db.execute(select(SolutionPack).where(SolutionPack.id == row.pack_id))).scalar_one()
            spec = spec_row.spec_json or yaml.safe_load(spec_row.yaml_text) or {}
            ctx = ExecutionContext(
                pack_id=spec["pack_id"], run_id=run_id,
                inputs=row.inputs or {},
                pack_code=spec_row.code,
                pack_db_id=spec_row.id,
                nodes=(row.context_snapshot or {}).get("nodes", {}),
                shared=(row.context_snapshot or {}).get("shared", {}),
            )
        # Approval decisions are applied inside _execute() by looking at pending node states.
        async for ev in self._execute(spec, ctx, user_id=row.user_id, agent_id=row.agent_id,
                                      conversation_id=row.conversation_id,
                                      approval_decision=approval_decision,
                                      approval_reason=approval_reason,
                                      approver_id=approver_id):
            yield ev

    # ---------- Core DAG scheduler ----------
    async def _execute(self, spec: dict[str, Any], ctx: ExecutionContext, *, user_id: int | None,
                       agent_id: int | None, conversation_id: int | None,
                       approval_decision: str | None = None,
                       approval_reason: str | None = None,
                       approver_id: int | None = None) -> AsyncIterator[PackEvent]:
        nodes = {n["id"]: n for n in spec["nodes"]}
        deps = {nid: list(n.get("depends_on") or []) for nid, n in nodes.items()}

        # Initialise node state if first run
        for nid in nodes:
            ctx.nodes.setdefault(nid, {"status": "pending"})

        # Apply approval decision to any waiting human_approval node
        if approval_decision:
            for nid, st in ctx.nodes.items():
                if st.get("status") == "waiting_approval":
                    st["approval_decision"] = approval_decision
                    st["approval_reason"] = approval_reason
                    st["approver_id"] = approver_id

        max_parallel = int((spec.get("config") or {}).get("max_parallel") or 10)
        timeout_ms = int((spec.get("config") or {}).get("timeout_ms") or 300000)
        fail_strategy = (spec.get("config") or {}).get("fail_strategy") or "stop"

        started = asyncio.get_running_loop().time()

        # Very simple ready-queue scheduler. Parallelism is constrained globally.
        running: set[str] = set()
        completed = set(nid for nid, st in ctx.nodes.items() if st.get("status") in ("success", "failed", "skipped"))
        waiting = set(nid for nid, st in ctx.nodes.items() if st.get("status") == "waiting_approval")

        async def launch(nid: str):
            nonlocal completed, waiting
            node = nodes[nid]
            running.add(nid)
            ctx.nodes[nid].update({"status": "running", "started_at": self._now_ms()})
            await self._persist_context(ctx, status="running")
            yield PackEvent("pack_progress", {
                "run_id": ctx.run_id, "pack_id": ctx.pack_id,
                "node_id": nid, "status": "running", "node_type": node["type"],
            })
            try:
                result = await self._exec_node(node, ctx, user_id=user_id, agent_id=agent_id,
                                               conversation_id=conversation_id)
                status = result.get("status", "success")
                ctx.nodes[nid].update({
                    "status": status,
                    "output": result.get("output"),
                    "error": result.get("error"),
                    "finished_at": self._now_ms(),
                })
                if status == "waiting_approval":
                    waiting.add(nid)
                    await self._persist_context(ctx, status="waiting_approval")
                    yield PackEvent("pack_waiting_approval", {
                        "run_id": ctx.run_id, "pack_id": ctx.pack_id,
                        "node_id": nid,
                        "title": result.get("title") or node.get("name") or nid,
                        "message": result.get("message"),
                    })
                    return
                completed.add(nid)
                await self._persist_context(ctx, status="running")
                yield PackEvent("pack_progress", {
                    "run_id": ctx.run_id, "pack_id": ctx.pack_id,
                    "node_id": nid, "status": status, "node_type": node["type"],
                })
            except Exception as e:  # noqa: BLE001
                ctx.nodes[nid].update({"status": "failed", "error": str(e), "finished_at": self._now_ms()})
                completed.add(nid)
                await self._persist_context(ctx, status="failed" if fail_strategy == "stop" else "running")
                yield PackEvent("pack_progress", {
                    "run_id": ctx.run_id, "pack_id": ctx.pack_id,
                    "node_id": nid, "status": "failed", "error": str(e),
                })
                if fail_strategy == "stop":
                    raise
            finally:
                running.discard(nid)

        try:
            while True:
                elapsed_ms = int((asyncio.get_running_loop().time() - started) * 1000)
                if elapsed_ms > timeout_ms:
                    raise TimeoutError(f"pack timeout > {timeout_ms}ms")
                # Resume waiting approval if the node has a decision now
                for nid in list(waiting):
                    st = ctx.nodes[nid]
                    if st.get("approval_decision") in ("approved", "rejected"):
                        waiting.remove(nid)
                        completed.add(nid)
                        st["status"] = st["approval_decision"]
                if len(completed) == len(nodes):
                    break
                ready = [
                    nid for nid in nodes
                    if nid not in completed and nid not in running and nid not in waiting
                    and ctx.nodes[nid].get("status") in ("pending", "approved", "rejected")
                    and all(ctx.nodes[d].get("status") in ("success", "skipped", "approved", "rejected") for d in deps[nid])
                ]
                if not ready and not running:
                    # Stuck = either waiting approval or misconfigured flow
                    if waiting:
                        return
                    raise RuntimeError("pack has no ready nodes and no running nodes")
                # Launch up to max_parallel (serial gather to keep code simple while still allowing same-turn parallel)
                launch_now = ready[:max(0, max_parallel - len(running))]
                if launch_now:
                    # Run launched nodes concurrently
                    gens = [launch(nid) for nid in launch_now]
                    # Collect events from each node in sequence; implementation is simple,
                    # parallel node bodies still run concurrently via gather below.
                    tasks = [self._drain_node_events(g) for g in gens]
                    batches = await asyncio.gather(*tasks)
                    for batch in batches:
                        for ev in batch:
                            yield ev
                else:
                    await asyncio.sleep(0.05)
        except Exception as e:  # noqa: BLE001
            await self._persist_context(ctx, status="failed", error=str(e))
            yield PackEvent("pack_error", {
                "run_id": ctx.run_id, "pack_id": ctx.pack_id, "error": str(e),
            })
            return

        outputs = self._resolve_pack_outputs(spec, ctx)
        await self._persist_context(ctx, status="success", outputs=outputs)
        yield PackEvent("pack_done", {
            "run_id": ctx.run_id,
            "pack_id": ctx.pack_id,
            "status": "success",
            "outputs": outputs,
            "trace": self._build_trace(ctx, nodes),
        })

    async def _drain_node_events(self, agen: AsyncIterator[PackEvent]) -> list[PackEvent]:
        out: list[PackEvent] = []
        async for ev in agen:
            out.append(ev)
        return out

    # ---------- Node executors ----------
    async def _exec_node(self, node: dict[str, Any], ctx: ExecutionContext, *, user_id: int | None,
                         agent_id: int | None, conversation_id: int | None) -> dict[str, Any]:
        t = node["type"]
        if t == "skill":
            return await self._exec_skill_node(node, ctx, user_id=user_id, agent_id=agent_id, conversation_id=conversation_id)
        if t == "parallel_group":
            return await self._exec_parallel_group(node, ctx)
        if t == "aggregator":
            return await self._exec_aggregator(node, ctx)
        if t == "condition":
            return await self._exec_condition(node, ctx)
        if t == "sub_agent":
            return await self._exec_sub_agent(node, ctx, user_id=user_id, agent_id=agent_id, conversation_id=conversation_id)
        if t == "human_approval":
            return await self._exec_human_approval(node, ctx)
        raise ValueError(f"unsupported node type: {t}")

    async def _exec_skill_node(self, node: dict[str, Any], ctx: ExecutionContext, *, user_id: int | None,
                               agent_id: int | None, conversation_id: int | None) -> dict[str, Any]:
        if not self.runner_factory:
            raise RuntimeError("PackEngine.runner_factory not configured")
        runner = await self.runner_factory(user_id=user_id, agent_id=agent_id, conversation_id=conversation_id)
        skill_ref = str(node.get("skill_id") or "")
        skill_code = skill_ref.split("@", 1)[0]
        kwargs = self._render_inputs(node.get("inputs") or {}, ctx)
        if skill_code == "mcp_invoke":
            result = await self._exec_mcp_invoke(node, kwargs, runner)
        else:
            target_skill = await self._load_skill_by_code(skill_code)
            if target_skill is None:
                return {"status": "failed", "error": f"skill not found or disabled: {skill_code}"}
            if target_skill.type == "atomic" and (target_skill.source_json or {}).get("path"):
                result = await self._exec_atomic_skill_via_llm(node, kwargs, runner, target_skill)
            else:
                result = await runner._exec_skill(skill_code, kwargs)
        result = self._apply_node_outputs(node, result)
        return {"status": "success", "output": result}

    async def _load_skill_by_code(self, skill_code: str):
        from sqlalchemy import select
        from ..db.models import Skill
        from ..db.session import SessionLocal
        async with SessionLocal() as db:
            return (await db.execute(
                select(Skill).where(Skill.code == skill_code, Skill.enabled.is_(True))
            )).scalar_one_or_none()


    async def _exec_atomic_skill_via_llm(self, node: dict[str, Any], kwargs: dict[str, Any],
                                          runner, target_skill) -> dict[str, Any]:
        """Run a path-based atomic skill via a constrained mini LLM loop.

        Atomic skills ship as a SKILL.md instruction bundle plus helper scripts.
        Their proper execution requires an LLM that reads SKILL.md and chains the
        right tool calls (typically `run_skill_script` to produce real artifacts).
        Returning the bundle directly (the default _exec_skill behavior for atomic
        skills) is wrong inside a Pack node, because the next node would then see
        the SKILL.md text instead of the produced artifact.
        """
        import logging
        from .agent_runner import AgentContext, AgentRunner
        from sqlalchemy import select
        from ..db.models import Model
        from ..db.session import SessionLocal

        log = logging.getLogger("pack_engine")

        sub_model = None
        node_model_code = node.get("model")
        if node_model_code:
            async with SessionLocal() as db:
                sub_model = (await db.execute(
                    select(Model).where(Model.code == str(node_model_code))
                )).scalar_one_or_none()
        if sub_model is None:
            sub_model = runner.ctx.model

        node_mcp_names = [str(x) for x in (node.get("mcps") or [])]
        sub_mcps = [m for m in runner.ctx.mcps if m.name in node_mcp_names] if node_mcp_names else []

        sub_ctx = AgentContext(
            agent=runner.ctx.agent,
            skills=[target_skill],
            mcps=sub_mcps,
            packs=[],
            model=sub_model,
            fallback_model=runner.ctx.fallback_model,
            history=[],
        )
        sub_runner = AgentRunner(sub_ctx, user_id=runner._user_id)
        sub_runner._conversation_id = getattr(runner, '_conversation_id', None)

        prompt_parts: list[str] = [
            f"【Pack 子节点任务】节点『{node.get('name') or node.get('id')}』需要使用 Skill 『{target_skill.code}』。",
            "强制流程,逐步执行:",
            f"1) 先调用工具 _read_skill_file(skill='{target_skill.code}', path='SKILL.md') 阅读完整说明书。",
            "2) 严格按 SKILL.md 的『交付方式』调用对应工具(通常是 run_skill_script)生成真实交付物文件。",
            "3) 完成后用一两句中文汇报产物,不要再粘贴正文。",
            "硬性约束:",
            "- 必须严格按 SKILL.md 的『交付方式』指定的工具调用产出文件,不要自己换工具。",
            "- 不允许只输出说明文字而不生成真实文件。",
            "- 不允许跳过 SKILL.md,自行猜测如何执行。",
        ]
        if kwargs:
            import json as _json
            prompt_parts.append("节点输入参数(原样喂给 SKILL.md 流程):\n```json\n" +
                                _json.dumps(kwargs, ensure_ascii=False, indent=2) + "\n```")
        prompt = "\n\n".join(prompt_parts)

        text_chunks: list[str] = []
        produced_files: list[dict[str, Any]] = []
        tool_calls_seen: list[str] = []
        log.warning("pack-mini-loop START node=%s skill=%s model=%s mcps=%s kwargs=%s",
                     node.get("id"), target_skill.code,
                     getattr(sub_model, "code", None),
                     [m.name for m in sub_mcps],
                     list(kwargs.keys()) if isinstance(kwargs, dict) else type(kwargs).__name__)
        async for ev in sub_runner.stream(prompt, files=[]):
            if ev.type == "text" and isinstance(ev.data, dict):
                text_chunks.append(ev.data.get("text", "") or "")
            elif ev.type == "tool_use" and isinstance(ev.data, dict):
                tool_calls_seen.append(str(ev.data.get("name") or ""))
            elif ev.type == "file" and isinstance(ev.data, dict):
                produced_files.append(ev.data)
            elif ev.type == "error" and isinstance(ev.data, dict):
                raise RuntimeError(ev.data.get("message") or "atomic skill mini-loop failed")
        log.warning("pack-mini-loop END node=%s tools=%s files=%d text_len=%d",
                     node.get("id"), tool_calls_seen, len(produced_files),
                     sum(len(t) for t in text_chunks))

        for f in produced_files:
            url = str(f.get("download_url") or "")
            if not url:
                continue
            # Don't pre-register into _emitted_file_urls: the outer stream() finally
            # block is the only place that truly emits `file` SSE events to the UI.
            # Pre-registering here would make the outer loop skip these files,
            # which is exactly what hid Pack sub-skill PPT cards from the chat.
            if any(x.get("download_url") == url for x in runner._saved_files):
                continue
            runner._saved_files.append(f)

        text = "".join(text_chunks).strip()
        primary_file = produced_files[0] if produced_files else None
        result: dict[str, Any] = {
            "text": text,
            "result": text,
            "files": produced_files,
            "tools_used": tool_calls_seen,
        }
        if primary_file:
            result["file"] = primary_file
        return result


    async def _exec_parallel_group(self, node: dict[str, Any], ctx: ExecutionContext) -> dict[str, Any]:
        # Scheduler already handles concurrency globally; this node is mostly a join barrier.
        # We mark it success when its children have finished per wait_strategy.
        children = node.get("children") or []
        statuses = [ctx.nodes.get(cid, {}).get("status") for cid in children]
        wait = node.get("wait_strategy") or "all_success"
        if wait == "all_success":
            ok = all(s == "success" for s in statuses)
        elif wait == "first_success":
            ok = any(s == "success" for s in statuses)
        elif wait == "n_of_m":
            n = int(node.get("n") or 1)
            ok = sum(1 for s in statuses if s == "success") >= n
        else:
            ok = True
        return {"status": "success" if ok else "failed", "output": {"children": children}}

    async def _exec_aggregator(self, node: dict[str, Any], ctx: ExecutionContext) -> dict[str, Any]:
        sources = node.get("sources") or []
        merged: dict[str, Any] = {}
        for sid in sources:
            out = ctx.nodes.get(sid, {}).get("output")
            if isinstance(out, dict):
                merged.update(out)
        # basic computed fields
        compute = (node.get("compute") or {})
        if "risk_score" in compute:
            merged["risk_score"] = self._compute_risk_score(sources, ctx)
        out_key = node.get("output_key") or node["id"]
        ctx.shared[out_key] = merged
        return {"status": "success", "output": merged}

    async def _exec_condition(self, node: dict[str, Any], ctx: ExecutionContext) -> dict[str, Any]:
        mode = node.get("mode") or "rule"
        if mode == "rule":
            for rule in node.get("rules") or []:
                expr = rule.get("if") or ""
                if self._eval_condition(expr, ctx):
                    ctx.shared[f"branch__{node['id']}"] = rule.get("goto")
                    return {"status": "success", "output": {"goto": rule.get("goto")}}
            goto = node.get("default_goto")
            ctx.shared[f"branch__{node['id']}"] = goto
            return {"status": "success", "output": {"goto": goto}}
        # llm_judge placeholder: keep deterministic for now
        opts = node.get("judge_options") or []
        choice = opts[0] if opts else node.get("default_goto")
        ctx.shared[f"branch__{node['id']}"] = choice
        return {"status": "success", "output": {"goto": choice}}

    async def _exec_sub_agent(self, node: dict[str, Any], ctx: ExecutionContext, *, user_id: int | None,
                               agent_id: int | None, conversation_id: int | None) -> dict[str, Any]:
        # Minimal v1: run a registered agent goal by delegating to an AgentRunner with a composed prompt.
        if not self.runner_factory:
            raise RuntimeError("PackEngine.runner_factory not configured")
        runner = await self.runner_factory(user_id=user_id, agent_id=agent_id, conversation_id=conversation_id,
                                           override_agent_code=node.get("agent_id"))
        inherited = {k: self._resolve_ref(k, ctx) for k in (node.get("context_inherit") or [])}
        prompt = node.get("goal") or "完成子任务"
        if inherited:
            prompt += "\n\n上下文:\n" + yaml.safe_dump(inherited, allow_unicode=True, sort_keys=False)
        chunks: list[str] = []
        async for ev in runner.stream(prompt, files=[]):
            if ev.type == "text":
                chunks.append(ev.data.get("text", ""))
        return {"status": "success", "output": {"text": "".join(chunks)}}

    async def _exec_human_approval(self, node: dict[str, Any], ctx: ExecutionContext) -> dict[str, Any]:
        # Create/refresh an approval row and pause execution.
        title = (node.get("notify") or {}).get("message_template") or node.get("name") or node["id"]
        async with SessionLocal() as db:
            existing = (await db.execute(select(PackApproval).where(
                PackApproval.run_id == ctx.run_id, PackApproval.node_id == node["id"]
            ))).scalar_one_or_none()
            if existing:
                if existing.status in ("approved", "rejected"):
                    return {"status": existing.status, "output": {"decision": existing.status}}
            else:
                db.add(PackApproval(
                    run_id=ctx.run_id,
                    pack_id=ctx.pack_db_id or 0,
                    node_id=node["id"],
                    title=title[:256],
                    message=(node.get("notify") or {}).get("message_template"),
                    detail_json={"context": ctx.shared},
                    assigned_role=(node.get("notify") or {}).get("role"),
                    assigned_user_ids=(node.get("notify") or {}).get("user_ids"),
                ))
                await db.commit()
        return {"status": "waiting_approval", "title": title, "message": title}

    async def _exec_mcp_invoke(self, node: dict[str, Any], kwargs: dict[str, Any], runner) -> dict[str, Any]:
        import time

        mcp_name = str(kwargs.get("mcp_id") or "").strip()
        tool_name = str(kwargs.get("tool") or "").strip()
        call_args = kwargs.get("args") or {}
        extract = kwargs.get("extract")
        on_empty = str(kwargs.get("on_empty") or "null")
        if not mcp_name:
            mcps = node.get("mcps") or []
            if len(mcps) == 1:
                mcp_name = str(mcps[0])
        if not mcp_name:
            raise ValueError("mcp_invoke requires inputs.mcp_id or node.mcps[0]")
        if not tool_name:
            raise ValueError("mcp_invoke requires inputs.tool")
        if not isinstance(call_args, dict):
            raise ValueError("mcp_invoke inputs.args must be an object")

        async with SessionLocal() as db:
            mcp = (await db.execute(select(MCPConnector).where(
                MCPConnector.name == mcp_name,
                MCPConnector.enabled.is_(True),
            ))).scalar_one_or_none()
        if not mcp:
            raise ValueError(f"mcp not found or disabled: {mcp_name}")

        started = time.perf_counter()
        raw = await runner._call_mcp_tool_once(mcp, tool_name, call_args)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        value = raw
        if extract:
            value = self._extract_path(raw, str(extract))
            if value in (None, "", [], {}):
                if on_empty == "error":
                    raise ValueError(f"mcp_invoke extract empty: {extract}")
                if on_empty == "skip":
                    return {"raw": raw, "value": None, "mcp_id": mcp_name, "tool": tool_name, "elapsed_ms": elapsed_ms, "skipped": True}
                value = None
        return {"raw": raw, "value": value, "mcp_id": mcp_name, "tool": tool_name, "elapsed_ms": elapsed_ms}

    def _apply_node_outputs(self, node: dict[str, Any], result: Any) -> Any:
        outputs = node.get("outputs") or []
        if not outputs or not isinstance(outputs, list):
            return result
        if len(outputs) == 1:
            key = outputs[0]
            if isinstance(result, dict):
                if key in result and result[key] is not None:
                    return result
                # graceful fallback so {{ node.output.<alias> }} never silently becomes null
                fallback = result.get("result") or result.get("text") or result.get("output") or result
                merged = dict(result)
                merged[key] = fallback
                return merged
            return {key: result}
        mapped: dict[str, Any] = {}
        if isinstance(result, dict):
            for key in outputs:
                v = result.get(key)
                if v is None:
                    v = result.get("result") or result.get("text")
                mapped[key] = v
        else:
            for idx, key in enumerate(outputs):
                mapped[key] = result[idx] if isinstance(result, list) and idx < len(result) else None
        return mapped

    def _extract_path(self, data: Any, path: str) -> Any:
        import re

        cur = data
        for part in path.split('.'):
            if not part:
                continue
            m = re.match(r'^([A-Za-z0-9_\-]+)(\[(\d+)\])?$', part)
            if not m:
                return None
            key = m.group(1)
            idx = m.group(3)
            if isinstance(cur, dict):
                cur = cur.get(key)
            else:
                return None
            if idx is not None:
                if not isinstance(cur, list):
                    return None
                i = int(idx)
                cur = cur[i] if 0 <= i < len(cur) else None
        return cur

    # ---------- Helpers ----------
    def _render_inputs(self, tpl: Any, ctx: ExecutionContext) -> Any:
        if isinstance(tpl, str):
            return self._render_template(tpl, ctx)
        if isinstance(tpl, dict):
            return {k: self._render_inputs(v, ctx) for k, v in tpl.items()}
        if isinstance(tpl, list):
            return [self._render_inputs(v, ctx) for v in tpl]
        return tpl

    def _render_template(self, s: str, ctx: ExecutionContext) -> Any:
        # full-match ref → preserve native type
        import re
        m = re.fullmatch(r"\{\{\s*([^}]+)\s*\}\}", s)
        if m:
            return self._eval_ref(m.group(1), ctx)
        return re.sub(r"\{\{\s*([^}]+)\s*\}\}", lambda mm: str(self._eval_ref(mm.group(1), ctx) or ""), s)

    def _eval_ref(self, expr: str, ctx: ExecutionContext) -> Any:
        expr = expr.strip()
        # support "inputs.xxx" and "node_id.output.field" and default(...)
        if "|" in expr:
            main, pipe = [x.strip() for x in expr.split("|", 1)]
            val = self._eval_ref(main, ctx)
            if val is None and pipe.startswith("default(") and pipe.endswith(")"):
                raw = pipe[len("default("):-1].strip()
                if raw in {"null", "None"}: return None
                if raw in {"true", "True"}: return True
                if raw in {"false", "False"}: return False
                try: return int(raw)
                except ValueError: return raw.strip("'\"")
            return val
        if expr.startswith("inputs."):
            cur: Any = ctx.inputs
            for p in expr.split(".")[1:]:
                cur = cur.get(p) if isinstance(cur, dict) else None
            return cur
        # node refs: <node_id>.output[s].<field...> or shorthand <node_id>.<field>
        import re as _re
        m = _re.match(r"^([^.]+)\.outputs?(?:\.(.*))?$", expr)
        if m:
            node_id, rest = m.group(1), (m.group(2) or "")
            cur: Any = ctx.nodes.get(node_id, {}).get("output")
            for p in rest.split(".") if rest else []:
                if not p:
                    continue
                cur = cur.get(p) if isinstance(cur, dict) else None
            return cur
        parts = expr.split(".")
        if parts and parts[0] in ctx.nodes:
            cur: Any = ctx.nodes.get(parts[0], {}).get("output")
            for p in parts[1:]:
                cur = cur.get(p) if isinstance(cur, dict) else None
            return cur
        # shared refs e.g. aggregator.risk_score
        cur: Any = ctx.shared.get(parts[0]) if parts else None
        for p in parts[1:]:
            cur = cur.get(p) if isinstance(cur, dict) else None
        return cur

    def _resolve_ref(self, expr: str, ctx: ExecutionContext) -> Any:
        return self._eval_ref(expr, ctx)

    def _eval_condition(self, expr: str, ctx: ExecutionContext) -> bool:
        """Safe condition evaluator — no eval(), only supports simple comparisons."""
        import re
        import operator as op

        # Render {{ ... }} placeholders
        rendered = re.sub(r"\{\{\s*([^}]+)\s*\}\}", lambda m: repr(self._eval_ref(m.group(1), ctx)), expr)

        # Supported operators
        ops = {
            ">": op.gt, "<": op.lt, ">=": op.ge, "<=": op.le,
            "==": op.eq, "!=": op.ne,
        }

        # Try to match: <value> <op> <value>
        for op_str, op_func in ops.items():
            parts = rendered.split(op_str, 1)
            if len(parts) == 2:
                left_str, right_str = parts[0].strip(), parts[1].strip()
                try:
                    left = ast.literal_eval(left_str)
                    right = ast.literal_eval(right_str)
                    return bool(op_func(left, right))
                except (ValueError, SyntaxError):
                    continue

        return False

    def _compute_risk_score(self, sources: list[str], ctx: ExecutionContext) -> float:
        vals = []
        for sid in sources:
            out = ctx.nodes.get(sid, {}).get("output")
            if isinstance(out, dict):
                v = out.get("confidence") or out.get("risk_score")
                if isinstance(v, (int, float)):
                    vals.append(float(v))
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    def _resolve_pack_outputs(self, spec: dict[str, Any], ctx: ExecutionContext) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, cfg in (spec.get("outputs") or {}).items():
            out[key] = self._eval_ref(str(cfg.get("from") or ""), ctx)
        return out

    def _build_trace(self, ctx: ExecutionContext, nodes: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        trace = []
        for nid, st in ctx.nodes.items():
            trace.append({
                "node_id": nid,
                "node_type": nodes.get(nid, {}).get("type"),
                "status": st.get("status"),
                "started_at": st.get("started_at"),
                "finished_at": st.get("finished_at"),
            })
        trace.sort(key=lambda x: (x.get("started_at") or 0, x["node_id"]))
        return trace

    async def _persist_run(self, run_id: str, *, pack_db_id: int, ctx: ExecutionContext,
                           user_id: int | None, agent_id: int | None, conversation_id: int | None,
                           status: str) -> None:
        async with SessionLocal() as db:
            db.add(PackRun(
                run_id=run_id,
                pack_id=pack_db_id,
                user_id=user_id,
                agent_id=agent_id,
                conversation_id=conversation_id,
                status=status,
                inputs=ctx.inputs,
                context_snapshot={"nodes": ctx.nodes, "shared": ctx.shared},
                trace=[],
            ))
            await db.commit()

    async def _persist_context(self, ctx: ExecutionContext, *, status: str,
                               outputs: dict[str, Any] | None = None,
                               error: str | None = None) -> None:
        async with SessionLocal() as db:
            row = (await db.execute(select(PackRun).where(PackRun.run_id == ctx.run_id))).scalar_one_or_none()
            if not row:
                return
            row.status = status
            row.context_snapshot = {"nodes": ctx.nodes, "shared": ctx.shared}
            row.trace = self._build_trace(ctx, {})
            if outputs is not None:
                row.outputs = outputs
            if error is not None:
                row.error = error
            if status in ("success", "failed", "aborted"):
                row.finished_at = datetime.now(timezone.utc)
            await db.commit()

    @staticmethod
    def _now_ms() -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1000)
