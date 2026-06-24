"""Task + TaskRun APIs.

Strict per-user scoping: every endpoint filters by `owner_user_id == current_user.id`.
Admins are NOT special here — they manage their own tasks only.
"""
from __future__ import annotations
import asyncio
import logging
from typing import Any
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..db.models import Task, TaskRun, Agent, User
from ..deps import current_user
from ..schemas import TaskIn, TaskOut, TaskRunOut, TaskRunPage
from ..services.task_runner import execute_task, get_scheduler
from ..services.croniter_compat import _next_cron_fire, next_fire_time

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _validate_schedule(stype: str, sval: str | None, tz: str) -> None:
    if stype == "manual":
        return
    if not sval:
        raise HTTPException(400, "请填写调度表达式")
    try:
        if stype == "cron":
            _next_cron_fire(sval, tz)
        elif stype == "once":
            res = next_fire_time("once", sval, tz)
            if res is None:
                raise HTTPException(400, "一次性调度时间已过")
        else:
            raise HTTPException(400, f"unsupported schedule_type: {stype}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"调度表达式无效: {e}")


def _to_out(t: Task, agent_name: str | None = None) -> TaskOut:
    out = TaskOut.model_validate(t, from_attributes=True)
    out.agent_name = agent_name
    out.notify_channels = list(t.notify_channels_json or [])
    return out


async def _agent_name_map(db: AsyncSession, agent_ids: list[int]) -> dict[int, str]:
    if not agent_ids:
        return {}
    rows = (await db.execute(select(Agent.id, Agent.name).where(Agent.id.in_(agent_ids)))).all()
    return {r[0]: r[1] for r in rows}


@router.get("")
async def list_tasks(
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    total = (await db.execute(
        select(func.count(Task.id)).where(Task.owner_user_id == user.id)
    )).scalar_one()
    rows = (await db.execute(
        select(Task).where(Task.owner_user_id == user.id)
        .order_by(desc(Task.id)).limit(limit).offset(offset)
    )).scalars().all()
    names = await _agent_name_map(db, [t.agent_id for t in rows])
    items = [_to_out(t, names.get(t.agent_id)) for t in rows]
    return {"items": items, "total": total}


@router.post("", response_model=TaskOut)
async def create_task(payload: TaskIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    # owner must be allowed to use the agent: simplest check — agent exists & enabled
    agent = (await db.execute(select(Agent).where(Agent.id == payload.agent_id))).scalar_one_or_none()
    if not agent or not agent.enabled:
        raise HTTPException(400, "智能体不可用")

    _validate_schedule(payload.schedule_type, payload.schedule_value, payload.timezone)

    t = Task(
        owner_user_id=user.id,
        agent_id=payload.agent_id,
        name=payload.name,
        description=payload.description,
        prompt_text=payload.prompt_text or "",
        schedule_type=payload.schedule_type,
        schedule_value=payload.schedule_value,
        timezone=payload.timezone,
        max_runtime_seconds=payload.max_runtime_seconds,
        concurrency_policy=payload.concurrency_policy,
        notify_channels_json=list(payload.notify_channels or []),
        notify_email_to=payload.notify_email_to,
        notify_on=payload.notify_on,
        enabled=payload.enabled,
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    if t.enabled and t.schedule_type in ("cron", "once") and t.schedule_value:
        get_scheduler().schedule(t.id, t.schedule_type, t.schedule_value, t.timezone)
    return _to_out(t, agent.name)


@router.post("/batch")
async def create_batch_tasks(
    body: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    """批量创建任务。验证所有 agent_id，任意一个无效则整个批量回滚。"""
    from sqlalchemy import select as sel
    from ..db.models import Agent

    tasks_data = body.get("tasks", [])
    if not tasks_data:
        raise HTTPException(400, "tasks 不能为空")

    # 验证所有 agent_id 存在且启用
    agent_ids = {t.get("agent_id") for t in tasks_data}
    stmt = sel(Agent.id).where(Agent.id.in_(agent_ids), Agent.enabled == True)  # noqa: E712
    result = await db.execute(stmt)
    valid_ids = set(result.scalars().all())
    invalid = agent_ids - valid_ids
    if invalid:
        raise HTTPException(400, f"以下 Agent 不存在或未启用: {invalid}")

    created = []
    for data in tasks_data:
        task = Task(
            owner_user_id=user.id,
            agent_id=data["agent_id"],
            name=data.get("name", f"批量任务-{len(created)+1}"),
            prompt_text=data.get("prompt_text", ""),
            schedule_type=data.get("schedule_type", "manual"),
        )
        db.add(task)
        created.append(task)

    await db.commit()
    for t in created:
        await db.refresh(t)

    return {
        "status": "created",
        "count": len(created),
        "task_ids": [t.id for t in created],
    }


@router.get("/{tid}", response_model=TaskOut)
async def get_task(tid: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    t = (await db.execute(select(Task).where(Task.id == tid, Task.owner_user_id == user.id))).scalar_one_or_none()
    if not t:
        raise HTTPException(404, "不存在")
    a = (await db.execute(select(Agent.name).where(Agent.id == t.agent_id))).scalar_one_or_none()
    return _to_out(t, a)


@router.patch("/{tid}", response_model=TaskOut)
async def update_task(tid: int, payload: TaskIn,
                       user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    t = (await db.execute(select(Task).where(Task.id == tid, Task.owner_user_id == user.id))).scalar_one_or_none()
    if not t:
        raise HTTPException(404, "不存在")
    if t.last_run_status == "running":
        raise HTTPException(400, "任务正在运行，请先取消后再编辑")
    agent = (await db.execute(select(Agent).where(Agent.id == payload.agent_id))).scalar_one_or_none()
    if not agent or not agent.enabled:
        raise HTTPException(400, "智能体不可用")
    _validate_schedule(payload.schedule_type, payload.schedule_value, payload.timezone)

    t.agent_id = payload.agent_id
    t.name = payload.name
    t.description = payload.description
    t.prompt_text = payload.prompt_text or ""
    t.schedule_type = payload.schedule_type
    t.schedule_value = payload.schedule_value
    t.timezone = payload.timezone
    t.max_runtime_seconds = payload.max_runtime_seconds
    t.concurrency_policy = payload.concurrency_policy
    t.notify_channels_json = list(payload.notify_channels or [])
    t.notify_email_to = payload.notify_email_to
    t.notify_on = payload.notify_on
    t.enabled = payload.enabled
    await db.commit()
    await db.refresh(t)

    sch = get_scheduler()
    sch.cancel(t.id)
    if t.enabled and t.schedule_type in ("cron", "once") and t.schedule_value:
        sch.schedule(t.id, t.schedule_type, t.schedule_value, t.timezone)
    return _to_out(t, agent.name)


@router.delete("/{tid}")
async def delete_task(tid: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    t = (await db.execute(select(Task).where(Task.id == tid, Task.owner_user_id == user.id))).scalar_one_or_none()
    if not t:
        raise HTTPException(404, "不存在")
    if t.last_run_status == "running":
        raise HTTPException(400, "任务正在运行，请先取消后再删除")
    get_scheduler().cancel(t.id)
    await db.delete(t)
    await db.commit()
    return {"ok": True}


@router.post("/{tid}/run", response_model=TaskRunOut)
async def manual_run(tid: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    t = (await db.execute(select(Task).where(Task.id == tid, Task.owner_user_id == user.id))).scalar_one_or_none()
    if not t:
        raise HTTPException(404, "不存在")
    # fire-and-forget; we return the latest run after enqueue. To give the UI
    # something to poll on right away we wait briefly for the row creation.
    asyncio.create_task(execute_task(tid, triggered_by="manual", triggered_user_id=user.id))
    # poll for the new row up to ~3s
    last = None
    for _ in range(30):
        await asyncio.sleep(0.1)
        last = (await db.execute(
            select(TaskRun).where(TaskRun.task_id == tid).order_by(desc(TaskRun.id)).limit(1)
        )).scalar_one_or_none()
        if last:
            break
    if not last:
        raise HTTPException(500, "任务启动超时")
    return TaskRunOut.model_validate(last, from_attributes=True)


@router.post("/{tid}/toggle", response_model=TaskOut)
async def toggle_task(tid: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    t = (await db.execute(select(Task).where(Task.id == tid, Task.owner_user_id == user.id))).scalar_one_or_none()
    if not t:
        raise HTTPException(404, "不存在")
    t.enabled = not t.enabled
    await db.commit()
    await db.refresh(t)
    sch = get_scheduler()
    sch.cancel(t.id)
    if t.enabled and t.schedule_type in ("cron", "once") and t.schedule_value:
        sch.schedule(t.id, t.schedule_type, t.schedule_value, t.timezone)
    a = (await db.execute(select(Agent.name).where(Agent.id == t.agent_id))).scalar_one_or_none()
    return _to_out(t, a)


@router.get("/{tid}/runs", response_model=TaskRunPage)
async def list_runs(tid: int, limit: int = 30, offset: int = 0,
                     user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    t = (await db.execute(select(Task).where(Task.id == tid, Task.owner_user_id == user.id))).scalar_one_or_none()
    if not t:
        raise HTTPException(404, "不存在")
    total = (await db.execute(select(func.count(TaskRun.id)).where(TaskRun.task_id == tid))).scalar_one()
    rows = (await db.execute(
        select(TaskRun).where(TaskRun.task_id == tid)
        .order_by(desc(TaskRun.id)).limit(limit).offset(offset)
    )).scalars().all()
    return TaskRunPage(
        items=[TaskRunOut.model_validate(r, from_attributes=True) for r in rows],
        total=int(total or 0),
    )


# ---- Single run detail / cancel ----
detail_router = APIRouter(prefix="/api/task-runs", tags=["task-runs"])


@detail_router.get("/{rid}", response_model=TaskRunOut)
async def get_run(rid: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    r = (await db.execute(select(TaskRun).where(TaskRun.id == rid))).scalar_one_or_none()
    if not r:
        raise HTTPException(404, "不存在")
    t = (await db.execute(select(Task).where(Task.id == r.task_id))).scalar_one_or_none()
    if not t or t.owner_user_id != user.id:
        raise HTTPException(404, "不存在")
    return TaskRunOut.model_validate(r, from_attributes=True)


@detail_router.post("/{rid}/cancel", response_model=TaskRunOut)
async def cancel_run(rid: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    r = (await db.execute(select(TaskRun).where(TaskRun.id == rid))).scalar_one_or_none()
    if not r:
        raise HTTPException(404, "不存在")
    t = (await db.execute(select(Task).where(Task.id == r.task_id))).scalar_one_or_none()
    if not t or t.owner_user_id != user.id:
        raise HTTPException(404, "不存在")
    if r.status not in ("pending", "running"):
        raise HTTPException(400, "该执行已结束，无需取消")
    # Best-effort: mark cancelled. We can't truly interrupt the in-flight runner
    # from another request without a process-level cancel token, but updating the
    # row prevents the run from being retried and gives the user a final state.
    r.status = "cancelled"
    r.finished_at = datetime.now(timezone.utc)
    if r.started_at:
        r.duration_ms = int((r.finished_at - r.started_at).total_seconds() * 1000)
    r.error_message = (r.error_message or "") + " | 用户取消"
    if t.last_run_id == r.id:
        t.last_run_status = "cancelled"
        t.last_run_at = r.finished_at
    await db.commit()
    await db.refresh(r)
    return TaskRunOut.model_validate(r, from_attributes=True)
