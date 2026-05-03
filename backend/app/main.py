from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .api import auth, chat, files
from .api.admin import users as admin_users, models as admin_models, mcp as admin_mcp, \
    skills as admin_skills, agents as admin_agents, logs as admin_logs


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="H3C Agent", version="0.1.0", lifespan=lifespan)

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
app.include_router(admin_users.router)
app.include_router(admin_models.router)
app.include_router(admin_mcp.router)
app.include_router(admin_skills.router)
app.include_router(admin_agents.router)
app.include_router(admin_logs.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
