"""Task scheduling + execution.

Runs scheduled tasks in-process via APScheduler-free, lightweight asyncio.
Each task gets a per-task asyncio.Lock to enforce 'skip' concurrency, and
each run calls the existing AgentRunner with a fresh Conversation. SSE
events from the runner are consumed and persisted into the messages table
so the user can revisit the run as a regular conversation.

We intentionally do NOT depend on apscheduler — we maintain our own
asyncio.Task per cron entry that sleeps until next fire time.
"""
from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from .croniter_compat import next_fire_time
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..db.session import SessionLocal
from ..db.models import (
    Task, TaskRun, Notification, User, Conversation, Message, Agent,
    AgentSkill, AgentMCP, AgentPack, Skill, MCPConnector, SolutionPack, Model,
)
from ..runtime.agent_runner import AgentRunner
from .agent_context_service import build_agent_context
from . import mailer

logger = logging.getLogger(__name__)


# ---------- per-task lock registry ----------
_task_locks: dict[int, asyncio.Lock] = {}


def _lock_for(task_id: int) -> asyncio.Lock:
    lk = _task_locks.get(task_id)
    if lk is None:
        lk = asyncio.Lock()
        _task_locks[task_id] = lk
    return lk


# ---------- run a single task ----------
async def execute_task(task_id: int, *, triggered_by: str = "manual",
                        triggered_user_id: int | None = None) -> int | None:
    """Execute a task once. Returns the TaskRun id (or None if skipped/missing)."""
    async with SessionLocal() as db:
        # Lock the task row to prevent race conditions in concurrent execution
        task = (await db.execute(
            select(Task).where(Task.id == task_id).with_for_update()
        )).scalar_one_or_none()
        if not task:
            return None
        owner = (await db.execute(select(User).where(User.id == task.owner_user_id))).scalar_one_or_none()
        if not owner or owner.status != "active":
            return None
        if not task.enabled and triggered_by == "cron":
            return None

        # concurrency skip — now safe due to FOR UPDATE lock
        if task.concurrency_policy == "skip" and task.last_run_status == "running":
            run_no = await _next_run_no(db, task_id)
            run = TaskRun(task_id=task_id, run_no=run_no, triggered_by=triggered_by,
                          triggered_user_id=triggered_user_id, status="skipped",
                          error_message="上一次执行尚未完成，已按并发策略跳过本次")
            db.add(run)
            await db.commit()
            await db.refresh(run)
            return run.id

        # create conversation + run row
        conv = Conversation(user_id=owner.id, agent_id=task.agent_id,
                             title=f"[任务] {task.name}")
        db.add(conv)
        await db.flush()

        run_no = await _next_run_no(db, task_id)
        run = TaskRun(
            task_id=task_id, run_no=run_no, triggered_by=triggered_by,
            triggered_user_id=triggered_user_id, status="running",
            conversation_id=conv.id,
            started_at=datetime.now(timezone.utc),
        )
        db.add(run)
        task.last_run_id = None  # set after flush
        task.last_run_status = "running"
        task.last_run_at = run.started_at
        await db.commit()
        await db.refresh(run)
        task.last_run_id = run.id
        await db.commit()

        ctx = await build_agent_context(db, agent_id=task.agent_id, user_id=owner.id)

        # persist user message in the conversation
        user_msg = Message(conversation_id=conv.id, role="user",
                            content_json={"text": task.prompt_text or ""})
        db.add(user_msg)
        await db.commit()

        # consume runner stream
        text_parts: list[str] = []
        thinking_parts: list[str] = []
        tool_traces: list[dict] = []
        saved_files: list[dict] = []
        saved_uis: list[dict] = []
        tokens_in = tokens_out = 0
        had_error: str | None = None
        had_interaction = False
        # Tool names we treat as 'requires user interaction'
        INTERACTION_TOOLS = {"AskUserQuestion"}

        runner = AgentRunner(ctx, user_id=owner.id)

        async def _consume() -> None:
            nonlocal tokens_in, tokens_out, had_error, had_interaction
            async for ev in runner.stream(task.prompt_text or "", []):
                t = ev.type
                d = ev.data or {}
                if t == "text":
                    text_parts.append(d.get("text", ""))
                elif t == "thinking":
                    thinking_parts.append(d.get("text", ""))
                elif t in ("tool_use", "tool_result"):
                    tool_traces.append({"type": t, "data": d})
                    name = d.get("name") if t == "tool_use" else ""
                    if name and name in INTERACTION_TOOLS:
                        had_interaction = True
                elif t == "file":
                    saved_files.append(d if isinstance(d, dict) else {})
                elif t == "ui":
                    # UI surfaces require user click → treat as needing interaction
                    saved_uis.append(d if isinstance(d, dict) else {})
                    had_interaction = True
                elif t == "done":
                    tokens_in = d.get("tokens_in", 0) or 0
                    tokens_out = d.get("tokens_out", 0) or 0
                elif t == "error":
                    had_error = d.get("message") or "执行错误"

        timed_out = False
        try:
            await asyncio.wait_for(_consume(), timeout=max(10, task.max_runtime_seconds))
        except asyncio.TimeoutError:
            timed_out = True
        except asyncio.CancelledError:
            run.status = "cancelled"
            raise
        except Exception as e:
            had_error = f"{type(e).__name__}: {e}"

        # persist assistant message
        content_payload: dict[str, Any] = {"text": "".join(text_parts)}
        if thinking_parts:
            content_payload["thinking"] = "".join(thinking_parts)
        if saved_files:
            content_payload["files"] = saved_files
        if saved_uis:
            content_payload["uis"] = saved_uis
        am = Message(
            conversation_id=conv.id, role="assistant",
            content_json=content_payload,
            tool_calls_json={"trace": tool_traces} if tool_traces else None,
            tokens_in=tokens_in, tokens_out=tokens_out,
        )
        db.add(am)

        # finalize run
        run.finished_at = datetime.now(timezone.utc)
        run.duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000) if run.started_at else 0
        run.tokens_in = tokens_in
        run.tokens_out = tokens_out

        # status precedence: timeout > interaction > error > success
        if timed_out:
            run.status = "timeout"
            run.error_message = f"任务执行超过 {task.max_runtime_seconds} 秒，已强制中断"
        elif had_interaction:
            run.status = "failed"
            run.error_message = "任务需要用户交互（AskUserQuestion / UI 表单），定时任务已跳过本次"
        elif had_error:
            run.status = "failed"
            run.error_message = had_error
        else:
            run.status = "succeeded"

        # summary = trim of final assistant text
        text_full = ("".join(text_parts) or "").strip()
        run.summary = (text_full[:200] + ("…" if len(text_full) > 200 else "")) if text_full else None

        # update task aggregate
        task.last_run_status = run.status
        task.last_run_at = run.finished_at

        await db.commit()
        await db.refresh(run)

        # notify
        await _notify_run(db, task, run, owner)
        return run.id


async def _next_run_no(db: AsyncSession, task_id: int) -> int:
    from sqlalchemy import func as _f
    n = (await db.execute(
        select(_f.coalesce(_f.max(TaskRun.run_no), 0)).where(TaskRun.task_id == task_id)
    )).scalar_one()
    return int(n or 0) + 1


# ---------- notifications ----------
async def _notify_run(db: AsyncSession, task: Task, run: TaskRun, owner: User) -> None:
    on = task.notify_on or "always"
    if on == "success" and run.status != "succeeded":
        return
    if on == "failure" and run.status == "succeeded":
        return
    channels = list(task.notify_channels_json or [])
    notify_status: dict[str, Any] = {}
    title, body, link = _format_notification(task, run)

    if "inapp" in channels:
        n = Notification(
            user_id=owner.id, type="task_run",
            title=title, body=body, link_url=link,
            detail_json={"task_id": task.id, "run_id": run.id, "status": run.status},
        )
        db.add(n)
        notify_status["inapp"] = {"ok": True}

    if "email" in channels:
        to_addr = (task.notify_email_to or owner.email or "").strip()
        if not to_addr:
            notify_status["email"] = {"ok": False, "error": "未填写收件邮箱"}
        else:
            html = _format_email_html(task, run, link)
            res = await mailer.send_email(to_addr, title, body, html)
            notify_status["email"] = res

    run.notified_at = datetime.now(timezone.utc)
    run.notify_status_json = notify_status
    await db.commit()


def _format_notification(task: Task, run: TaskRun) -> tuple[str, str, str]:
    status_label = {
        "succeeded": "成功", "failed": "失败", "timeout": "超时",
        "cancelled": "已取消", "skipped": "已跳过",
    }.get(run.status, run.status or "")
    title = f"[任务] {task.name} · {status_label}"
    parts = []
    if run.summary:
        parts.append(run.summary)
    if run.error_message:
        parts.append(f"错误: {run.error_message}")
    if run.duration_ms:
        parts.append(f"耗时 {run.duration_ms / 1000:.1f}s")
    body = "\n".join(parts) if parts else "（无详细信息）"
    base = (settings.APP_BASE_URL or "").rstrip("/")
    link = f"{base}/tasks/{task.id}/runs/{run.id}" if base else ""
    return title, body, link


def _format_email_html(task: Task, run: TaskRun, link: str) -> str:
    color = {"succeeded": "#34a853", "failed": "#ea4335", "timeout": "#ea4335",
             "cancelled": "#9aa0a6", "skipped": "#9aa0a6"}.get(run.status, "#5f6368")
    summary = run.summary or "（无输出）"
    error = f'<p style="color:#ea4335;margin:6px 0">{run.error_message}</p>' if run.error_message else ""
    btn = f'<p><a href="{link}" style="display:inline-block;padding:8px 14px;background:#4285f4;color:#fff;border-radius:6px;text-decoration:none">查看详情</a></p>' if link else ""
    return f"""
<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:#202124;font-size:14px;line-height:1.6">
  <h2 style="margin:0 0 8px">[任务] {task.name}</h2>
  <p style="margin:0 0 12px">状态: <span style="color:{color};font-weight:600">{run.status}</span> · 耗时 {run.duration_ms / 1000:.1f}s</p>
  <pre style="background:#f1f3f4;padding:10px 12px;border-radius:6px;white-space:pre-wrap">{summary}</pre>
  {error}
  {btn}
</div>
"""


# ---------- scheduler core ----------
class _Scheduler:
    def __init__(self) -> None:
        self._tasks: dict[int, asyncio.Task] = {}
        self._stopped = asyncio.Event()

    def is_running(self, task_id: int) -> bool:
        t = self._tasks.get(task_id)
        return bool(t and not t.done())

    async def start(self) -> None:
        # Recover all enabled cron/once schedules
        async with SessionLocal() as db:
            rows = (await db.execute(select(Task).where(Task.enabled.is_(True)))).scalars().all()
            for t in rows:
                if t.schedule_type in ("cron", "once") and t.schedule_value:
                    self.schedule(t.id, t.schedule_type, t.schedule_value, t.timezone)

    async def stop(self) -> None:
        self._stopped.set()
        for t in list(self._tasks.values()):
            t.cancel()
        for t in list(self._tasks.values()):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass

    def cancel(self, task_id: int) -> None:
        t = self._tasks.pop(task_id, None)
        if t and not t.done():
            t.cancel()

    def schedule(self, task_id: int, schedule_type: str, schedule_value: str, tz: str) -> None:
        self.cancel(task_id)
        if schedule_type not in ("cron", "once") or not schedule_value:
            return
        coro = self._loop_one(task_id, schedule_type, schedule_value, tz)
        self._tasks[task_id] = asyncio.create_task(coro, name=f"task-{task_id}")

    async def _loop_one(self, task_id: int, stype: str, sval: str, tz: str) -> None:
        try:
            while not self._stopped.is_set():
                try:
                    delay = next_fire_time(stype, sval, tz)
                except Exception as e:
                    logger.warning("Task %s schedule parse failed: %s", task_id, e)
                    return
                if delay is None:
                    return  # one-shot already passed
                # sleep until fire (in chunks so we can react to stop)
                while delay > 0 and not self._stopped.is_set():
                    chunk = min(delay, 30)
                    await asyncio.sleep(chunk)
                    delay -= chunk
                if self._stopped.is_set():
                    return
                # check enabled flag still set before firing
                async with SessionLocal() as db:
                    t = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
                    if not t or not t.enabled:
                        return
                try:
                    await execute_task(task_id, triggered_by="cron", triggered_user_id=None)
                except Exception as e:
                    logger.exception("Task %s execute failed: %s", task_id, e)
                if stype == "once":
                    return
        except asyncio.CancelledError:
            return


_scheduler = _Scheduler()


def get_scheduler() -> _Scheduler:
    return _scheduler
