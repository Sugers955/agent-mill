from __future__ import annotations
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .api import auth, chat, files, tasks as tasks_api, notifications as notifications_api
from .api import downloads as downloads_api
from .api import favorites as favorites_api
from .api.admin import users as admin_users, models as admin_models, mcp as admin_mcp, \
    skills as admin_skills, agents as admin_agents, logs as admin_logs, \
    departments as admin_departments, packs as admin_packs, approvals as admin_approvals
from .services.file_cleanup import cleanup_loop
from .services.task_runner import get_scheduler
from .db.session import engine, Base


async def _auto_migrate() -> None:
    """Idempotent schema sync on boot.

    create_all creates any tables missing in the DB (e.g. tasks/task_runs/notifications)
    and then we run a few column-level ADD COLUMN IF NOT EXISTS for fields added to
    existing tables (like users.email). Safe to run every boot.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for stmt in [
            # users.email (needed for task email notifications)
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(256)",
            # agents: max_turns / effort (Claude SDK tuning — added in an earlier change)
            "ALTER TABLE agents ADD COLUMN IF NOT EXISTS max_turns INTEGER NOT NULL DEFAULT 15",
            "ALTER TABLE agents ADD COLUMN IF NOT EXISTS effort VARCHAR(16) NOT NULL DEFAULT 'medium'",
            # capability summary (Skill / MCP) — auto-generated, user-friendly Chinese description
            "ALTER TABLE skills ADD COLUMN IF NOT EXISTS user_summary TEXT",
            "ALTER TABLE skills ADD COLUMN IF NOT EXISTS user_summary_updated_at TIMESTAMP WITH TIME ZONE",
            "ALTER TABLE mcp_connectors ADD COLUMN IF NOT EXISTS user_summary TEXT",
            "ALTER TABLE mcp_connectors ADD COLUMN IF NOT EXISTS tool_summaries_json JSON",
            "ALTER TABLE mcp_connectors ADD COLUMN IF NOT EXISTS user_summary_updated_at TIMESTAMP WITH TIME ZONE",
            # favorites: snapshot of generated files attached to the answer
            "ALTER TABLE favorites ADD COLUMN IF NOT EXISTS files_json JSON",
            # agents: per-agent parsed-content cap. NULL = use global default.
            "ALTER TABLE agents ADD COLUMN IF NOT EXISTS parsed_content_limit INTEGER",
        ]:
            try:
                await conn.exec_driver_sql(stmt)
            except Exception:
                # Non-fatal — log-only; a fresh DB may not have the parent table yet
                # on the very first boot before create_all, which is fine.
                pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await _auto_migrate()
    except Exception:
        # Don't block startup on migration errors; surface them via /api/health failures instead
        pass
    cleanup = asyncio.create_task(cleanup_loop())
    sch = get_scheduler()
    try:
        await sch.start()
    except Exception:
        pass
    try:
        yield
    finally:
        cleanup.cancel()
        try:
            await cleanup
        except (asyncio.CancelledError, Exception):
            pass
        try:
            await sch.stop()
        except Exception:
            pass


app = FastAPI(title="Agent Mill", version="0.1.0", lifespan=lifespan)

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(files.router)
app.include_router(downloads_api.router)
app.include_router(tasks_api.router)
app.include_router(tasks_api.detail_router)
app.include_router(notifications_api.router)
app.include_router(favorites_api.router)
app.include_router(admin_users.router)
app.include_router(admin_models.router)
app.include_router(admin_mcp.router)
app.include_router(admin_skills.router)
app.include_router(admin_agents.router)
app.include_router(admin_logs.router)
app.include_router(admin_departments.router)
app.include_router(admin_packs.router)
app.include_router(admin_approvals.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
