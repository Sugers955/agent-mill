"""Bootstrap script: creates tables (via metadata.create_all) and seeds default roles + admin.

For production, prefer `alembic revision --autogenerate` + `alembic upgrade head`.
This script is a quick-start for first run.
"""
from __future__ import annotations
import asyncio
from sqlalchemy import select
from app.core.config import settings
from app.core.security import hash_password
from app.db.session import engine, SessionLocal, Base
from app.db.models import Role, User


DEFAULT_ROLES = [
    {"code": "admin", "name": "超级管理员", "description": "全部权限"},
    {"code": "operator", "name": "运营管理员", "description": "可配置 Skill/MCP/Agent"},
    {"code": "user", "name": "普通用户", "description": "仅使用智能体"},
]


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # idempotent column add for existing installations
        await conn.exec_driver_sql(
            "ALTER TABLE agents ADD COLUMN IF NOT EXISTS is_default BOOLEAN NOT NULL DEFAULT false"
        )
    async with SessionLocal() as db:
        # roles
        for r in DEFAULT_ROLES:
            existing = (await db.execute(select(Role).where(Role.code == r["code"]))).scalar_one_or_none()
            if not existing:
                db.add(Role(**r))
        await db.commit()

        # admin user
        admin_role = (await db.execute(select(Role).where(Role.code == "admin"))).scalar_one()
        existing = (await db.execute(
            select(User).where(User.username == settings.SEED_ADMIN_USERNAME))).scalar_one_or_none()
        if not existing:
            db.add(User(
                username=settings.SEED_ADMIN_USERNAME,
                password_hash=hash_password(settings.SEED_ADMIN_PASSWORD),
                display_name="管理员",
                role_id=admin_role.id,
            ))
            await db.commit()
            print(f"创建管理员账号: {settings.SEED_ADMIN_USERNAME} / {settings.SEED_ADMIN_PASSWORD}")
        else:
            print("管理员账号已存在,跳过")


if __name__ == "__main__":
    asyncio.run(main())
