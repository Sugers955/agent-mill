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
from .api import feedback as feedback_api
from .api.webhooks import im as webhook_im
from .api.webhooks import incoming as webhook_incoming
from .api.admin import users as admin_users, models as admin_models, mcp as admin_mcp, \
    skills as admin_skills, agents as admin_agents, logs as admin_logs, \
    departments as admin_departments, packs as admin_packs, approvals as admin_approvals, \
    quotas as admin_quotas, stats as admin_stats, memories as admin_memories, \
    task_templates as admin_task_templates
from .services.file_cleanup import cleanup_loop
from .services.task_runner import get_scheduler
from .db.session import engine, Base, SessionLocal

logger = logging.getLogger(__name__)


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
            # ponytail: MySQL <8.0.29 不支持 ADD COLUMN IF NOT EXISTS，走 try/except
            "ALTER TABLE agents ADD COLUMN IF NOT EXISTS kb_id INTEGER NULL",
            # models: unit price for cost calculation
            "ALTER TABLE models ADD COLUMN IF NOT EXISTS unit_price_per_1k_tokens INTEGER NOT NULL DEFAULT 0",
            # user_quotas: create table if not exists (user-level monthly token quota)
            """CREATE TABLE IF NOT EXISTS user_quotas (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE UNIQUE,
                monthly_limit INTEGER NOT NULL DEFAULT 0,
                alert_threshold INTEGER NOT NULL DEFAULT 80,
                last_alert_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            )""",
            # agent_memories: agent persistent memory
            """CREATE TABLE IF NOT EXISTS agent_memories (
                id SERIAL PRIMARY KEY,
                agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                memory_type VARCHAR(32) NOT NULL,
                content TEXT NOT NULL,
                source_conversation_id INTEGER REFERENCES conversations(id) ON DELETE SET NULL,
                importance DOUBLE PRECISION NOT NULL DEFAULT 0.5,
                access_count INTEGER NOT NULL DEFAULT 0,
                last_accessed_at TIMESTAMP WITH TIME ZONE,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            )""",
            "CREATE INDEX IF NOT EXISTS idx_agent_memories_agent_user ON agent_memories(agent_id, user_id)",
            # task_templates: 任务模板
            """CREATE TABLE IF NOT EXISTS task_templates (
                id SERIAL PRIMARY KEY,
                name VARCHAR(128) NOT NULL,
                description TEXT,
                agent_id INTEGER NOT NULL REFERENCES agents(id),
                prompt_template TEXT NOT NULL,
                variables_json JSON NOT NULL DEFAULT '[]',
                schedule_json JSON,
                notify_config_json JSON,
                usage_count INTEGER NOT NULL DEFAULT 0,
                created_by INTEGER REFERENCES users(id),
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            )""",
            # webhook_configs: Webhook 配置
            """CREATE TABLE IF NOT EXISTS webhook_configs (
                id SERIAL PRIMARY KEY,
                name VARCHAR(128) NOT NULL,
                secret VARCHAR(128) NOT NULL,
                agent_id INTEGER NOT NULL REFERENCES agents(id),
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                description TEXT,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            )""",
        ]:
            try:
                await conn.exec_driver_sql(stmt)
            except Exception as e:
                # Non-fatal — log-only; a fresh DB may not have the parent table yet
                # on the very first boot before create_all, which is fine.
                logger.debug("Migration stmt failed (non-fatal): %s — %s", stmt[:80], e)

        # conversations.summary — 对话历史摘要（压缩后）
        try:
            # MySQL 不支持 ADD COLUMN IF NOT EXISTS，需要先检查
            from .db.init_db import is_mysql
            if is_mysql():
                result = await conn.exec_driver_sql(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_schema = DATABASE() AND table_name = 'conversations' AND column_name = 'summary'"
                )
                exists = result.fetchone()[0] > 0
                if not exists:
                    await conn.exec_driver_sql("ALTER TABLE conversations ADD COLUMN summary TEXT")
            else:
                await conn.exec_driver_sql("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS summary TEXT")
        except Exception as e:
            logger.debug("Migration stmt failed (non-fatal): conversations.summary — %s", e)

        # message_feedback — 用户反馈表（点赞/点踩）
        try:
            from .db.init_db import is_mysql
            if is_mysql():
                # MySQL: 检查表是否存在
                result = await conn.exec_driver_sql(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema = DATABASE() AND table_name = 'message_feedback'"
                )
                exists = result.fetchone()[0] > 0
                if not exists:
                    await conn.exec_driver_sql("""
                        CREATE TABLE message_feedback (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            user_id INT NOT NULL,
                            message_id BIGINT NOT NULL,
                            agent_id INT NOT NULL,
                            conversation_id INT NOT NULL,
                            rating VARCHAR(16) NOT NULL COMMENT 'like=点赞 / dislike=点踩',
                            reason VARCHAR(500) COMMENT '点踩原因',
                            analyzed BOOLEAN NOT NULL DEFAULT FALSE COMMENT '是否已分析',
                            analysis_result JSON COMMENT '分析结果',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                            INDEX ix_message_feedback_user_id (user_id),
                            INDEX ix_message_feedback_message_id (message_id),
                            INDEX ix_message_feedback_agent_id (agent_id),
                            INDEX ix_message_feedback_conversation_id (conversation_id),
                            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                            FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE,
                            FOREIGN KEY (agent_id) REFERENCES agents(id),
                            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户反馈表'
                    """)
            else:
                await conn.exec_driver_sql("""
                    CREATE TABLE IF NOT EXISTS message_feedback (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        message_id BIGINT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
                        agent_id INTEGER NOT NULL REFERENCES agents(id),
                        conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                        rating VARCHAR(16) NOT NULL,
                        reason VARCHAR(500),
                        analyzed BOOLEAN NOT NULL DEFAULT FALSE,
                        analysis_result JSONB,
                        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                    )
                """)
        except Exception as e:
            logger.debug("Migration stmt failed (non-fatal): message_feedback — %s", e)

        # 修复反馈表 agent_id 为可空（兼容已删除的 Agent）
        try:
            from .db.init_db import is_mysql
            if is_mysql():
                await conn.exec_driver_sql(
                    "ALTER TABLE message_feedback MODIFY agent_id INT NULL"
                )
            else:
                await conn.exec_driver_sql(
                    "ALTER TABLE message_feedback ALTER COLUMN agent_id DROP NOT NULL"
                )
        except Exception as e:
            logger.debug("Migration stmt failed (non-fatal): message_feedback.agent_id nullable — %s", e)

        # agent_messages — Agent 间消息表
        try:
            from .db.init_db import is_mysql
            if is_mysql():
                result = await conn.exec_driver_sql(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema = DATABASE() AND table_name = 'agent_messages'"
                )
                exists = result.fetchone()[0] > 0
                if not exists:
                    await conn.exec_driver_sql("""
                        CREATE TABLE agent_messages (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            from_agent_id INT NOT NULL,
                            to_agent_id INT NOT NULL,
                            conversation_id INT,
                            message_type VARCHAR(32) NOT NULL COMMENT 'delegate=委托 / query=查询 / notify=通知',
                            content TEXT NOT NULL COMMENT '消息内容',
                            context_json JSON COMMENT '传递的上下文数据',
                            status VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/processing/completed/failed',
                            result_json JSON COMMENT '执行结果',
                            priority INT NOT NULL DEFAULT 0 COMMENT '优先级',
                            reply_to_id INT COMMENT '回复的消息 ID',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                            INDEX ix_agent_messages_from_agent (from_agent_id),
                            INDEX ix_agent_messages_to_agent (to_agent_id),
                            INDEX ix_agent_messages_status (status),
                            FOREIGN KEY (from_agent_id) REFERENCES agents(id),
                            FOREIGN KEY (to_agent_id) REFERENCES agents(id),
                            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Agent间消息表'
                    """)
            else:
                await conn.exec_driver_sql("""
                    CREATE TABLE IF NOT EXISTS agent_messages (
                        id SERIAL PRIMARY KEY,
                        from_agent_id INTEGER NOT NULL REFERENCES agents(id),
                        to_agent_id INTEGER NOT NULL REFERENCES agents(id),
                        conversation_id INTEGER REFERENCES conversations(id) ON DELETE SET NULL,
                        message_type VARCHAR(32) NOT NULL,
                        content TEXT NOT NULL,
                        context_json JSONB,
                        status VARCHAR(16) NOT NULL DEFAULT 'pending',
                        result_json JSONB,
                        priority INTEGER NOT NULL DEFAULT 0,
                        reply_to_id INTEGER REFERENCES agent_messages(id),
                        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                    )
                """)
        except Exception as e:
            logger.debug("Migration stmt failed (non-fatal): agent_messages — %s", e)

        # audit_logs — 审计日志表
        try:
            from .db.init_db import is_mysql
            if is_mysql():
                result = await conn.exec_driver_sql(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema = DATABASE() AND table_name = 'audit_logs'"
                )
                exists = result.fetchone()[0] > 0
                if not exists:
                    await conn.exec_driver_sql("""
                        CREATE TABLE audit_logs (
                            id BIGINT AUTO_INCREMENT PRIMARY KEY,
                            user_id INT,
                            action VARCHAR(64) NOT NULL COMMENT '操作类型',
                            resource_type VARCHAR(32) NOT NULL COMMENT '资源类型',
                            resource_id VARCHAR(64) COMMENT '资源 ID',
                            detail_json JSON COMMENT '操作详情',
                            ip_address VARCHAR(45) COMMENT '客户端 IP',
                            user_agent VARCHAR(512) COMMENT 'User-Agent',
                            status VARCHAR(16) NOT NULL DEFAULT 'success' COMMENT 'success/failed/denied',
                            error_message TEXT COMMENT '错误信息',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            INDEX ix_audit_logs_user_id (user_id),
                            INDEX ix_audit_logs_action (action),
                            INDEX ix_audit_logs_created_at (created_at),
                            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='审计日志表'
                    """)
            else:
                await conn.exec_driver_sql("""
                    CREATE TABLE IF NOT EXISTS audit_logs (
                        id BIGSERIAL PRIMARY KEY,
                        user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                        action VARCHAR(64) NOT NULL,
                        resource_type VARCHAR(32) NOT NULL,
                        resource_id VARCHAR(64),
                        detail_json JSONB,
                        ip_address VARCHAR(45),
                        user_agent VARCHAR(512),
                        status VARCHAR(16) NOT NULL DEFAULT 'success',
                        error_message TEXT,
                        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                    )
                """)
        except Exception as e:
            logger.debug("Migration stmt failed (non-fatal): audit_logs — %s", e)

        # alert_rules — 告警规则表
        try:
            await conn.exec_driver_sql("""
                CREATE TABLE IF NOT EXISTS alert_rules (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(128) NOT NULL,
                    description TEXT,
                    metric VARCHAR(32) NOT NULL,
                    `condition` VARCHAR(8) NOT NULL DEFAULT 'gte',
                    threshold FLOAT NOT NULL,
                    window_minutes INT NOT NULL DEFAULT 5,
                    cooldown_minutes INT NOT NULL DEFAULT 30,
                    notification_channels JSON,
                    enabled TINYINT(1) NOT NULL DEFAULT 1,
                    user_id INT,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX ix_alert_rules_enabled (enabled),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='告警规则'
            """)
        except Exception as e:
            logger.debug("Migration stmt failed (non-fatal): alert_rules — %s", e)

        # alert_events — 告警事件表
        try:
            await conn.exec_driver_sql("""
                CREATE TABLE IF NOT EXISTS alert_events (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    rule_id BIGINT NOT NULL,
                    triggered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    metric_value FLOAT NOT NULL,
                    metric_detail JSON,
                    status VARCHAR(16) NOT NULL DEFAULT 'firing',
                    resolved_at TIMESTAMP NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX ix_alert_events_rule_id (rule_id),
                    INDEX ix_alert_events_status (status),
                    INDEX ix_alert_events_triggered_at (triggered_at),
                    FOREIGN KEY (rule_id) REFERENCES alert_rules(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='告警事件'
            """)
        except Exception as e:
            logger.debug("Migration stmt failed (non-fatal): alert_events — %s", e)

        # operation_approvals — 操作审批表
        try:
            await conn.exec_driver_sql("""
                CREATE TABLE IF NOT EXISTS operation_approvals (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    operation_type VARCHAR(64) NOT NULL,
                    target_id INT,
                    target_name VARCHAR(256),
                    requested_by INT NOT NULL,
                    reason TEXT,
                    status VARCHAR(16) NOT NULL DEFAULT 'pending',
                    decided_by INT,
                    decided_at TIMESTAMP NULL,
                    decision_reason TEXT,
                    detail_json JSON,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX ix_op_approvals_type (operation_type),
                    INDEX ix_op_approvals_status (status),
                    FOREIGN KEY (requested_by) REFERENCES users(id),
                    FOREIGN KEY (decided_by) REFERENCES users(id) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='操作审批'
            """)
        except Exception as e:
            logger.debug("Migration stmt failed (non-fatal): operation_approvals — %s", e)

        # 知识库表
        for kb_stmt in [
            """CREATE TABLE IF NOT EXISTS kb_knowledge_bases (
                id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(256) NOT NULL,
                description TEXT, owner_id INT NOT NULL, status VARCHAR(16) DEFAULT 'active',
                document_count INT DEFAULT 0, chunk_count INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (owner_id) REFERENCES users(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库'""",
            """CREATE TABLE IF NOT EXISTS kb_documents (
                id INT AUTO_INCREMENT PRIMARY KEY, kb_id INT NOT NULL,
                file_id INT, title VARCHAR(512), status VARCHAR(16) DEFAULT 'pending',
                char_count INT DEFAULT 0, chunk_count INT DEFAULT 0, error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX ix_kb_docs_kb (kb_id),
                FOREIGN KEY (kb_id) REFERENCES kb_knowledge_bases(id) ON DELETE CASCADE,
                FOREIGN KEY (file_id) REFERENCES uploaded_files(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库文档'""",
            """CREATE TABLE IF NOT EXISTS kb_chunks (
                id INT AUTO_INCREMENT PRIMARY KEY, document_id INT NOT NULL,
                kb_id INT NOT NULL, content TEXT NOT NULL, chunk_index INT DEFAULT 0,
                embedding TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX ix_kb_chunks_doc (document_id), INDEX ix_kb_chunks_kb (kb_id),
                FOREIGN KEY (document_id) REFERENCES kb_documents(id) ON DELETE CASCADE,
                FOREIGN KEY (kb_id) REFERENCES kb_knowledge_bases(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库分块'""",
        ]:
            try:
                await conn.exec_driver_sql(kb_stmt)
            except Exception as e:
                logger.debug("Migration stmt failed (non-fatal): kb — %s", e)

        # agent_templates — Agent 模板表
        try:
            await conn.exec_driver_sql("""
                CREATE TABLE IF NOT EXISTS agent_templates (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    code VARCHAR(64) NOT NULL UNIQUE,
                    name VARCHAR(128) NOT NULL,
                    description TEXT,
                    category VARCHAR(32) NOT NULL,
                    icon VARCHAR(64),
                    yaml_text TEXT NOT NULL,
                    is_builtin TINYINT(1) DEFAULT 1,
                    usage_count INT DEFAULT 0,
                    agent_count INT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX ix_agent_templates_category (category)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent 模板'
            """)
        except Exception as e:
            logger.debug("Migration stmt failed (non-fatal): agent_templates — %s", e)

        # workflow_definitions — 可视化工作流
        try:
            await conn.exec_driver_sql("""
                CREATE TABLE IF NOT EXISTS workflow_definitions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(128) NOT NULL,
                    description TEXT,
                    category VARCHAR(32),
                    definition_json JSON,
                    compiled_yaml TEXT,
                    status VARCHAR(16) DEFAULT 'draft',
                    enabled TINYINT(1) DEFAULT 1,
                    run_count INT DEFAULT 0,
                    user_id INT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='可视化工作流'
            """)
        except Exception as e:
            logger.debug("Migration stmt failed (non-fatal): workflow_definitions — %s", e)

        # Composite indexes for query performance
        for idx_stmt in [
            "CREATE INDEX IF NOT EXISTS ix_messages_conv_id_created ON messages (conversation_id, created_at)",
            "CREATE INDEX IF NOT EXISTS ix_call_logs_user_id_created ON call_logs (user_id, created_at)",
            "CREATE INDEX IF NOT EXISTS ix_call_logs_agent_id_created ON call_logs (agent_id, created_at)",
            "CREATE INDEX IF NOT EXISTS ix_notifications_user_read ON notifications (user_id, read_at)",
            "CREATE INDEX IF NOT EXISTS ix_task_runs_task_status ON task_runs (task_id, status)",
            "CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs (created_at)",
        ]:
            try:
                await conn.exec_driver_sql(idx_stmt)
            except Exception as e:
                logger.debug("Index creation failed (non-fatal): %s — %s", idx_stmt[:60], e)

        # MySQL 兼容补丁：ADD COLUMN IF NOT EXISTS 在 MySQL <8.0.29 中不支持
        for col_stmt in [
            ("agents", "kb_id", "kb_id INTEGER NULL"),
            ("kb_chunks", "embedding", "embedding TEXT NULL"),
        ]:
            try:
                table, column, definition = col_stmt
                cnt = (await conn.exec_driver_sql(
                    f"SELECT COUNT(*) FROM information_schema.COLUMNS "
                    f"WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='{table}' AND COLUMN_NAME='{column}'"
                )).scalar()
                if cnt == 0:
                    await conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {definition}")
            except Exception as e:
                logger.debug("Column check failed (non-fatal): %s.%s — %s", table, column, e)

    # Seed built-in templates
    try:
        async with SessionLocal() as db:
            from .api.admin.agent_templates import seed_templates
            await seed_templates(db)
    except Exception as e:
        logger.debug("Template seed failed (non-fatal): %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Security validation on startup
    for warn in settings.validate_security():
        logger.warning("⚠️  SECURITY: %s", warn)
    try:
        await _auto_migrate()
    except Exception as e:
        # Don't block startup on migration errors; surface them via /api/health failures instead
        logger.error("Database migration failed: %s", e)

    # 首次启动时自动加载演示数据
    try:
        from .db.session import async_session_factory
        from .db.models import User
        from sqlalchemy import select
        async with async_session_factory() as db:
            result = await db.execute(select(User).limit(1))
            if result.scalar_one_or_none() is None:
                from .db.seed_demo import seed
                try:
                    await seed()
                    logger.info("Demo data loaded successfully")
                except Exception as e:
                    logger.warning("Failed to load demo data: %s", e)
    except Exception as e:
        logger.debug("Auto-seed check failed (non-fatal): %s", e)

    cleanup = asyncio.create_task(cleanup_loop())
    alert_task = asyncio.create_task(_evaluate_alerts())
    learning_task = asyncio.create_task(_learning_loop())
    agent_comm_task = asyncio.create_task(_start_agent_message_polling())
    sch = get_scheduler()
    try:
        await sch.start()
    except Exception as e:
        logger.error("Task scheduler failed to start: %s — scheduled tasks will not run", e)
    try:
        yield
    finally:
        cleanup.cancel()
        alert_task.cancel()
        learning_task.cancel()
        agent_comm_task.cancel()
        try:
            await cleanup
        except (asyncio.CancelledError, Exception):
            pass
        try:
            await alert_task
        except (asyncio.CancelledError, Exception):
            pass
        try:
            await learning_task
        except (asyncio.CancelledError, Exception):
            pass
        try:
            await agent_comm_task
        except (asyncio.CancelledError, Exception):
            pass
        try:
            await sch.stop()
        except Exception:
            pass


async def _evaluate_alerts():
    """后台告警评估循环。"""
    while True:
        try:
            from .services.alert_service import AlertService
            async with SessionLocal() as db:
                svc = AlertService(db)
                await svc.evaluate_rules()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("Alert evaluation error: %s", e)
        await asyncio.sleep(60)


async def _learning_loop():
    """后台自学习循环，每小时运行一次。"""
    while True:
        try:
            from .services.learning_service import LearningService
            svc = LearningService()
            await svc.analyze_and_apply()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("Learning loop error: %s", e)
        await asyncio.sleep(3600)  # 每小时


async def _start_agent_message_polling():
    """启动 Agent 消息轮询服务。"""
    try:
        from .services.agent_communication import AgentCommunicationService
        svc = AgentCommunicationService.get_instance()
        svc.start_polling()
        logger.info("[AgentComm] 消息轮询已启动")
        # 保持任务运行
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        logger.info("[AgentComm] 消息轮询已停止")
    except Exception as e:
        logger.error("[AgentComm] 消息轮询启动失败: %s", e)


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
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# API 限流中间件
from .middleware.rate_limiter import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware)

# 审计中间件
from .middleware.audit import AuditMiddleware
app.add_middleware(AuditMiddleware)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(files.router)
app.include_router(downloads_api.router)
app.include_router(tasks_api.router)
app.include_router(tasks_api.detail_router)
app.include_router(notifications_api.router)
app.include_router(favorites_api.router)
app.include_router(feedback_api.router)

from .api import orchestrator as orchestrator_api
app.include_router(orchestrator_api.router)
app.include_router(webhook_im.router)
app.include_router(webhook_incoming.router)
app.include_router(admin_users.router)
app.include_router(admin_models.router)
app.include_router(admin_mcp.router)
app.include_router(admin_skills.router)
app.include_router(admin_agents.router)
app.include_router(admin_logs.router)
app.include_router(admin_departments.router)
app.include_router(admin_packs.router)
app.include_router(admin_approvals.router)
app.include_router(admin_quotas.router)
app.include_router(admin_stats.router)
app.include_router(admin_memories.router)
app.include_router(admin_task_templates.router)

from .api.admin import audit as admin_audit
app.include_router(admin_audit.router)

from .api.admin import alerts as admin_alerts
app.include_router(admin_alerts.router)

from .api.admin import auth as admin_auth
app.include_router(admin_auth.router)

from .api.admin import operation_approvals as admin_op_approvals
app.include_router(admin_op_approvals.router)

from .api.admin import data_masking as admin_data_masking
app.include_router(admin_data_masking.router)

from .api.admin import knowledge as admin_knowledge
app.include_router(admin_knowledge.router)

from .api.admin import agent_templates as admin_templates
app.include_router(admin_templates.router)

from .api.admin import workflows as admin_workflows
app.include_router(admin_workflows.router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "agent-mill"}
