"""可视化工作流 API — CRUD + 编译 + 运行 + 状态查询。"""
from __future__ import annotations
import asyncio
import json
import yaml
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ...db.session import get_db
from ...db.models import User, WorkflowDefinition, WorkflowRun, SolutionPack
from ...deps import require_admin_or_operator
from pydantic import BaseModel

router = APIRouter(prefix="/api/admin/workflows", tags=["admin"])


class WorkflowCreate(BaseModel):
    name: str
    description: str | None = None
    category: str | None = None
    definition_json: dict = {}


@router.get("")
async def list_workflows(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_or_operator),
):
    rows = (await db.execute(
        select(WorkflowDefinition).order_by(WorkflowDefinition.id.desc())
    )).scalars().all()
    return rows


@router.post("")
async def create_workflow(
    payload: WorkflowCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_or_operator),
):
    wf = WorkflowDefinition(
        name=payload.name, description=payload.description,
        category=payload.category, definition_json=payload.definition_json,
        user_id=user.id,
    )
    db.add(wf)
    await db.commit()
    await db.refresh(wf)
    return wf


@router.get("/{wf_id}")
async def get_workflow(
    wf_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_or_operator),
):
    wf = (await db.execute(select(WorkflowDefinition).where(WorkflowDefinition.id == wf_id))).scalar_one_or_none()
    if not wf: raise HTTPException(404)
    return wf


@router.put("/{wf_id}")
async def update_workflow(
    wf_id: int,
    payload: WorkflowCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_or_operator),
):
    wf = (await db.execute(select(WorkflowDefinition).where(WorkflowDefinition.id == wf_id))).scalar_one_or_none()
    if not wf: raise HTTPException(404)
    wf.name = payload.name
    wf.description = payload.description
    wf.category = payload.category
    wf.definition_json = payload.definition_json
    wf.compiled_yaml = None  # clear cache
    await db.commit()
    await db.refresh(wf)
    return wf


@router.delete("/{wf_id}")
async def delete_workflow(
    wf_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_or_operator),
):
    wf = (await db.execute(select(WorkflowDefinition).where(WorkflowDefinition.id == wf_id))).scalar_one_or_none()
    if not wf: raise HTTPException(404)
    await db.delete(wf)
    await db.commit()
    return {"ok": True}


def _compile_definition(def_json: dict, wf_id: int, wf_name: str, wf_desc: str | None) -> str:
    """将画布 definition_json 编译为方案包 YAML 文本。"""
    nodes = {n["id"]: n for n in def_json.get("nodes", [])}
    edges = def_json.get("edges", [])

    dep_map: dict[str, list[str]] = {}
    for e in edges:
        dep_map.setdefault(e["target"], []).append(e["source"])

    pack_nodes = []
    for nid, n in nodes.items():
        node = {
            "id": nid,
            "type": n.get("type", "skill"),
            "name": n.get("label", nid),
            "depends_on": dep_map.get(nid, []),
        }
        if n.get("config"):
            node.update(n["config"])
        pack_nodes.append(node)

    spec = {
        "pack_id": f"wf_{wf_id}",
        "name": wf_name,
        "version": "1.0.0",
        "description": wf_desc or "",
        "inputs": {},
        "outputs": {},
        "config": {"max_parallel": 5, "timeout_ms": 300000, "fail_strategy": "stop"},
        "nodes": pack_nodes,
    }
    return yaml.dump(spec, allow_unicode=True, default_flow_style=False)


@router.post("/{wf_id}/compile")
async def compile_workflow(
    wf_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_or_operator),
):
    """将可视化画布数据编译为 SolutionPack YAML。"""
    wf = (await db.execute(select(WorkflowDefinition).where(WorkflowDefinition.id == wf_id))).scalar_one_or_none()
    if not wf: raise HTTPException(404)
    if not wf.definition_json:
        raise HTTPException(400, "画布数据为空")

    wf.compiled_yaml = _compile_definition(wf.definition_json, wf.id, wf.name, wf.description)
    await db.commit()
    return {"yaml": wf.compiled_yaml}


# ---------------------------------------------------------------------------
# 运行工作流 — 立即执行 + 异步运行
# ---------------------------------------------------------------------------

async def _execute_workflow_run(run_id: int, pack_code: str):
    """异步执行工作流，更新 WorkflowRun 状态。"""
    from ...runtime.pack_engine import PackEngine

    try:
        engine = PackEngine()
        result_data: dict = {"success": False, "events": []}

        async for event in engine.start(pack_code, inputs={}, user_id=None):
            result_data["events"].append({"type": event.type, "data": event.data})
            if event.type == "pack_done":
                result_data["success"] = True
                result_data["outputs"] = event.data
            elif event.type == "pack_error":
                result_data["error"] = event.data.get("error", "未知错误")

        async with SessionLocal() as db:
            run = (await db.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))).scalar_one_or_none()
            if run:
                run.status = "success" if result_data.get("success") else "failed"
                run.output_data = result_data
                run.finished_at = datetime.now(timezone.utc)
                if not result_data.get("success") and result_data.get("error"):
                    run.error_message = result_data["error"]
                await db.commit()
    except Exception as e:
        async with SessionLocal() as db:
            run = (await db.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))).scalar_one_or_none()
            if run:
                run.status = "failed"
                run.error_message = str(e)
                run.finished_at = datetime.now(timezone.utc)
                await db.commit()


@router.post("/{wf_id}/run")
async def run_workflow(
    wf_id: int,
    input_data: dict | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_or_operator),
):
    """编译并立即运行工作流，返回 run_id 供轮询状态。"""
    wf = (await db.execute(select(WorkflowDefinition).where(WorkflowDefinition.id == wf_id))).scalar_one_or_none()
    if not wf: raise HTTPException(404)

    # 编译（如果未编译或画布有变更）
    if not wf.compiled_yaml:
        if not wf.definition_json:
            raise HTTPException(400, "画布数据为空，请先编辑工作流")
        wf.compiled_yaml = _compile_definition(wf.definition_json, wf.id, wf.name, wf.description)

    # 创建/更新 SolutionPack
    pack_code = f"wf_{wf.id}"
    existing_pack = (await db.execute(
        select(SolutionPack).where(SolutionPack.code == pack_code)
    )).scalar_one_or_none()

    if existing_pack:
        existing_pack.yaml_text = wf.compiled_yaml
        existing_pack.spec_json = None
    else:
        sp = SolutionPack(code=pack_code, name=wf.name, yaml_text=wf.compiled_yaml)
        db.add(sp)

    # 创建运行记录
    run = WorkflowRun(
        workflow_id=wf.id,
        status="running",
        input_data=input_data or {},
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # 更新运行计数
    wf.run_count = (wf.run_count or 0) + 1
    await db.commit()

    # 异步执行（不阻塞响应，300 秒超时）
    async def _run_with_timeout():
        try:
            await asyncio.wait_for(_execute_workflow_run(run.id, pack_code), timeout=300)
        except asyncio.TimeoutError:
            async with SessionLocal() as db:
                r = (await db.execute(select(WorkflowRun).where(WorkflowRun.id == run.id))).scalar_one_or_none()
                if r and r.status == "running":
                    r.status = "failed"
                    r.error_message = "执行超时（超过 300 秒）"
                    r.finished_at = datetime.now(timezone.utc)
                    await db.commit()

    asyncio.create_task(_run_with_timeout())

    return {"run_id": run.id, "status": "running", "pack_code": pack_code}


# ---------------------------------------------------------------------------
# 运行状态查询
# ---------------------------------------------------------------------------

@router.get("/{wf_id}/runs")
async def list_workflow_runs(
    wf_id: int,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_or_operator),
):
    """查询工作流的运行历史。"""
    runs = (await db.execute(
        select(WorkflowRun)
        .where(WorkflowRun.workflow_id == wf_id)
        .order_by(WorkflowRun.started_at.desc())
        .limit(limit)
    )).scalars().all()

    return [{
        "id": r.id,
        "status": r.status,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        "error": r.error_message,
    } for r in runs]


@router.get("/runs/{run_id}")
async def get_workflow_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_or_operator),
):
    """查询单次运行的详细状态和结果。"""
    run = (await db.execute(
        select(WorkflowRun).where(WorkflowRun.id == run_id)
    )).scalar_one_or_none()
    if not run:
        raise HTTPException(404, "运行记录不存在")
    return {
        "id": run.id,
        "workflow_id": run.workflow_id,
        "status": run.status,
        "input": run.input_data,
        "output": run.output_data,
        "error": run.error_message,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }
