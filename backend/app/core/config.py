from __future__ import annotations
import os
from functools import lru_cache
from urllib.parse import quote_plus
from pydantic_settings import BaseSettings, SettingsConfigDict


# .env 路径基于文件位置，不依赖 CWD（确保 mill 脚本/Docker/IDE 均能加载）
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")


class Settings(BaseSettings):
    """All sensitive defaults are empty/placeholder. Real values MUST come from
    backend/.env (gitignored) or process env. See backend/.env.example for the
    full list of variables.
    """
    model_config = SettingsConfigDict(env_file=_env_path, env_file_encoding="utf-8", extra="ignore")

    # ============================================================
    # 数据库配置
    # ============================================================
    # 数据库类型: mysql | postgresql
    DB_TYPE: str = "mysql"
    
    # 数据库连接
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "agent_mill"
    DB_PASSWORD: str = "change-me-secure-password"
    DB_NAME: str = "agent_mill"
    
    # 自动生成 DATABASE_URL（手动配置的 DATABASE_URL 优先）
    DATABASE_URL: str = ""
    
    def get_database_url(self) -> str:
        """根据配置自动生成数据库连接 URL。"""
        # 手动配置的 DATABASE_URL 优先
        if self.DATABASE_URL:
            return self.DATABASE_URL
        
        # URL 编码密码，处理特殊字符（@, # 等）
        password = quote_plus(self.DB_PASSWORD) if self.DB_PASSWORD else ""
        
        # 根据 DB_TYPE 自动生成
        if self.DB_TYPE == "mysql":
            return f"mysql+aiomysql://{self.DB_USER}:{password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        elif self.DB_TYPE == "postgresql":
            return f"postgresql+asyncpg://{self.DB_USER}:{password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        else:
            raise ValueError(f"不支持的数据库类型: {self.DB_TYPE}，请使用 mysql 或 postgresql")

    def validate_security(self) -> list[str]:
        """检查不安全的默认值，返回警告列表。"""
        warnings = []
        insecure_secrets = {"change-me-in-production", "admin123", "change-me-secure-password", ""}
        if self.JWT_SECRET in insecure_secrets:
            warnings.append("JWT_SECRET 使用默认值，生产环境必须设置随机密钥")
        if not self.ENCRYPTION_KEY:
            warnings.append("ENCRYPTION_KEY 为空，将从 JWT_SECRET 派生（仅限开发环境）")
        if self.SEED_ADMIN_PASSWORD in ("admin123", "admin", "YOUR_USER_PASSWORD", "password"):
            warnings.append("SEED_ADMIN_PASSWORD 使用弱密码，生产环境必须修改")
        return warnings

    # MUST be replaced in production via env. 32+ bytes random.
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALG: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Fernet key (base64-encoded 32 bytes). If blank, crypto.py derives one
    # deterministically from JWT_SECRET — fine for dev, NOT for prod.
    ENCRYPTION_KEY: str = ""

    STORAGE_ROOT: str = "../storage"
    SKILLS_DIR: str = "../storage/skills"
    UPLOADS_DIR: str = "../storage/uploads"
    MAX_UPLOAD_MB: int = 50

    CORS_ORIGINS: str = "http://localhost:5173"

    # First-run admin bootstrap; change immediately after first login.
    SEED_ADMIN_USERNAME: str = "admin"
    SEED_ADMIN_PASSWORD: str = "changeme"

    # ---- File parsing (MinerU) ----
    MINERU_MODE: str = "cloud"  # "cloud" | "local" | "disabled"
    MINERU_BASE_URL: str = "https://mineru.net"
    MINERU_API_KEY: str = ""
    MINERU_TIMEOUT_SEC: int = 60
    # Hard cap on parsed markdown stored / sent to model
    PARSED_MARKDOWN_HARD_LIMIT: int = 20000

    # ---- SMTP (Task notifications) ----
    # Leave blank to disable email notifications. Configure via .env.
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""        # display-name <addr@host>; for QQ the address part must equal SMTP_USER
    SMTP_USE_TLS: bool = True  # STARTTLS; for SSL on 465 set to False and SMTP_USE_SSL=True
    SMTP_USE_SSL: bool = False
    APP_BASE_URL: str = "http://localhost:5173"  # link target in emails / notifications
    # Backend public base URL used when handing out signed file URLs to external
    # tools (MCP servers). Falls back to APP_BASE_URL when unset.
    BACKEND_BASE_URL: str = ""

    # ---- Logging ----
    LOG_LEVEL: str = "INFO"  # DEBUG | INFO | WARNING | ERROR


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
