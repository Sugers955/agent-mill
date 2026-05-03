from __future__ import annotations
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://h3c:h3c@localhost:5432/h3c_agent"

    JWT_SECRET: str = "dev-secret"
    JWT_ALG: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    ENCRYPTION_KEY: str = ""

    STORAGE_ROOT: str = "../storage"
    SKILLS_DIR: str = "../storage/skills"
    UPLOADS_DIR: str = "../storage/uploads"
    MAX_UPLOAD_MB: int = 50

    CORS_ORIGINS: str = "http://localhost:5173"

    SEED_ADMIN_USERNAME: str = "admin"
    SEED_ADMIN_PASSWORD: str = "admin123"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
