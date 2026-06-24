"""Bootstrap script: creates tables (via metadata.create_all) and seeds default roles + admin.

Supports both PostgreSQL and MySQL databases.
For production, prefer `alembic revision --autogenerate` + `alembic upgrade head`.
This script is a quick-start for first run.
"""
from __future__ import annotations
import asyncio
from sqlalchemy import select, text
from app.core.config import settings
from app.core.security import hash_password
from app.db.session import engine, SessionLocal, Base
from app.db.models import Role, User


DEFAULT_ROLES = [
    {"code": "admin", "name": "超级管理员", "description": "全部权限"},
    {"code": "operator", "name": "运营管理员", "description": "可配置 Skill / MCP / 智能体 / 模型 / Solution Pack / 日志"},
    {"code": "user", "name": "普通用户", "description": "仅使用智能体"},
]


def is_mysql() -> bool:
    """检测是否使用 MySQL 数据库"""
    return settings.DB_TYPE == "mysql" or "mysql" in settings.DATABASE_URL


async def alter_table_add_column(conn, table: str, column: str, definition: str):
    """跨数据库的 ALTER TABLE ADD COLUMN IF NOT EXISTS"""
    if is_mysql():
        # MySQL: 先检查列是否存在，再添加
        result = await conn.execute(text(
            f"SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = '{table}' AND column_name = '{column}'"
        ))
        exists = result.scalar() > 0
        if not exists:
            await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
    else:
        # PostgreSQL 原生支持
        await conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {definition}")


async def create_index_if_not_exists(conn, index_name: str, table: str, columns: str):
    """跨数据库的 CREATE INDEX IF NOT EXISTS"""
    if is_mysql():
        # MySQL: 先检查索引是否存在，再创建
        result = await conn.execute(text(
            f"SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name = '{table}' AND index_name = '{index_name}'"
        ))
        exists = result.scalar() > 0
        if not exists:
            await conn.execute(text(f"CREATE INDEX {index_name} ON {table} ({columns})"))
    else:
        # PostgreSQL 原生支持
        await conn.exec_driver_sql(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({columns})")


async def main():
    # ── 1. 创建表结构 ──
    print("📦 初始化数据库表结构...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # 跨数据库兼容的列添加
        if is_mysql():
            await alter_table_add_column(conn, "agents", "is_default", "BOOLEAN NOT NULL DEFAULT false")
            await alter_table_add_column(conn, "agents", "max_turns", "INTEGER NOT NULL DEFAULT 15")
            await alter_table_add_column(conn, "agents", "effort", "VARCHAR(16) NOT NULL DEFAULT 'medium'")
            await alter_table_add_column(conn, "agents", "icon_url", "VARCHAR(512)")
            await alter_table_add_column(conn, "skills", "icon_url", "VARCHAR(512)")
            await alter_table_add_column(conn, "mcp_connectors", "icon_url", "VARCHAR(512)")
            await alter_table_add_column(conn, "models", "extra_params_json", "JSON NOT NULL DEFAULT (JSON_OBJECT())")
            await alter_table_add_column(conn, "users", "department_id", "INTEGER REFERENCES departments(id) ON DELETE SET NULL")
            await create_index_if_not_exists(conn, "ix_users_department_id", "users", "department_id")
            
            # SystemConfig 表
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS system_configs (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    `key` VARCHAR(128) NOT NULL UNIQUE,
                    value JSON NOT NULL,
                    description VARCHAR(256),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX ix_system_configs_key (`key`)
                )
            """))
            
            for table, column, definition in [
                ("uploaded_files", "parse_status", "VARCHAR(16) NOT NULL DEFAULT 'pending'"),
                ("uploaded_files", "parse_engine", "VARCHAR(32)"),
                ("uploaded_files", "parsed_markdown", "TEXT"),
                ("uploaded_files", "parsed_chars", "INTEGER NOT NULL DEFAULT 0"),
                ("uploaded_files", "parse_error", "TEXT"),
                ("uploaded_files", "parsed_at", "TIMESTAMP NULL"),
                ("uploaded_files", "last_used_at", "TIMESTAMP NULL"),
                ("users", "email", "VARCHAR(256)"),
            ]:
                await alter_table_add_column(conn, table, column, definition)
            await create_index_if_not_exists(conn, "ix_uploaded_files_last_used_at", "uploaded_files", "last_used_at")
        else:
            for stmt in [
                "ALTER TABLE agents ADD COLUMN IF NOT EXISTS is_default BOOLEAN NOT NULL DEFAULT false",
                "ALTER TABLE agents ADD COLUMN IF NOT EXISTS max_turns INTEGER NOT NULL DEFAULT 15",
                "ALTER TABLE agents ADD COLUMN IF NOT EXISTS effort VARCHAR(16) NOT NULL DEFAULT 'medium'",
                "ALTER TABLE agents ADD COLUMN IF NOT EXISTS icon_url VARCHAR(512)",
                "ALTER TABLE skills ADD COLUMN IF NOT EXISTS icon_url VARCHAR(512)",
                "ALTER TABLE mcp_connectors ADD COLUMN IF NOT EXISTS icon_url VARCHAR(512)",
                "ALTER TABLE models ADD COLUMN IF NOT EXISTS extra_params_json JSONB NOT NULL DEFAULT '{}'::jsonb",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS department_id INTEGER REFERENCES departments(id) ON DELETE SET NULL",
                "CREATE INDEX IF NOT EXISTS ix_users_department_id ON users (department_id)",
                "ALTER TABLE uploaded_files ADD COLUMN IF NOT EXISTS parse_status VARCHAR(16) NOT NULL DEFAULT 'pending'",
                "ALTER TABLE uploaded_files ADD COLUMN IF NOT EXISTS parse_engine VARCHAR(32)",
                "ALTER TABLE uploaded_files ADD COLUMN IF NOT EXISTS parsed_markdown TEXT",
                "ALTER TABLE uploaded_files ADD COLUMN IF NOT EXISTS parsed_chars INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE uploaded_files ADD COLUMN IF NOT EXISTS parse_error TEXT",
                "ALTER TABLE uploaded_files ADD COLUMN IF NOT EXISTS parsed_at TIMESTAMPTZ",
                "ALTER TABLE uploaded_files ADD COLUMN IF NOT EXISTS last_used_at TIMESTAMPTZ",
                "CREATE INDEX IF NOT EXISTS ix_uploaded_files_last_used_at ON uploaded_files (last_used_at)",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(256)",
                "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS summary TEXT",
            ]:
                await conn.exec_driver_sql(stmt)
            
            # SystemConfig 表（PostgreSQL）
            await conn.exec_driver_sql("""
                CREATE TABLE IF NOT EXISTS system_configs (
                    id SERIAL PRIMARY KEY,
                    key VARCHAR(128) NOT NULL UNIQUE,
                    value JSONB NOT NULL DEFAULT '{}',
                    description VARCHAR(256),
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            await conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_system_configs_key ON system_configs (key)")
    print("✅ 表结构初始化完成")
    
    # ── 2. 创建默认角色 ──
    print("👤 初始化角色...")
    async with SessionLocal() as db:
        for r in DEFAULT_ROLES:
            existing = (await db.execute(select(Role).where(Role.code == r["code"]))).scalar_one_or_none()
            if not existing:
                db.add(Role(**r))
        await db.commit()
    print("✅ 角色初始化完成")
    
    # ── 3. 创建管理员账号 ──
    print("🔑 初始化管理员账号...")
    async with SessionLocal() as db:
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
            print(f"✅ 创建管理员: {settings.SEED_ADMIN_USERNAME} / {settings.SEED_ADMIN_PASSWORD}")
        else:
            print("✅ 管理员账号已存在")
    
    # ── 4. 播种演示数据 ──
    print("\n🌱 播种演示数据...")
    from app.db.seed_demo import seed
    result = await seed()
    print(f"✅ 演示数据完成: {result['departments']} 部门, {result['models']} 模型, {result['skills']} 技能, {result['agents']} 数字员工")

    # ── 5. 播种演示对话和统计数据 ──
    print("\n📊 播种演示统计数据...")
    from app.db.seed_conversations import seed_conversations
    from app.db.seed_call_logs import seed_call_logs
    conv_result = await seed_conversations()
    log_result = await seed_call_logs()
    print(f"✅ 对话数据: {conv_result}")
    print(f"✅ 统计数据: {log_result}")


if __name__ == "__main__":
    asyncio.run(main())
