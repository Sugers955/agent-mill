from __future__ import annotations
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All sensitive defaults are empty/placeholder. Real values MUST come from
    backend/.env (gitignored) or process env. See backend/.env.example for the
    full list of variables.
    """
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://h3c:h3c@localhost:5432/h3c_agent"

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
    SEED_ADMIN_PASSWORD: str = "admin123"

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

    # ---- Logging ----
    LOG_LEVEL: str = "INFO"  # DEBUG | INFO | WARNING | ERROR


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
