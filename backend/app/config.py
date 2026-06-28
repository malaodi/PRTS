from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "allow",
    }

    APP_NAME: str = "PRTS Platform"
    DEBUG: bool = True
    SECRET_KEY: str = "dev-secret-key-change-in-production-please"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    DATABASE_URL: str = "postgresql+asyncpg://prts:prts@localhost:5432/prts"
    DATABASE_SYNC_URL: str = "postgresql+psycopg2://prts:prts@localhost:5432/prts"

    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "prts-platform"
    LANGCHAIN_TRACING_V2: bool = True

    DEFAULT_MODEL: str = "gpt-4"
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    ADMIN_EMAIL: str = "admin@prts.local"
    ADMIN_PASSWORD: str = "admin123"

    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
