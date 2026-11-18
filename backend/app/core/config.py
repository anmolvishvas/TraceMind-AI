from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Production application settings managed via environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application Metadata
    PROJECT_NAME: str = "TraceMind AI"
    VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # PostgreSQL Database
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "tracemind"
    POSTGRES_PASSWORD: str = "tracemind_secret"
    POSTGRES_DB: str = "tracemind_db"
    POSTGRES_POOL_SIZE: int = 20
    POSTGRES_MAX_OVERFLOW: int = 10

    @property
    def async_database_url(self) -> str:
        """Construct the asyncpg connection string."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Redis Cache and Queue Broker
    REDIS_URL: str = "redis://localhost:6379/0"

    # AI & OpenAI Configuration
    OPENAI_API_KEY: str = Field(default="sk-placeholder-key")
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_CHAT_MODEL: str = "gpt-4o"
    MAX_RAG_CONTEXT_CHUNKS: int = 5
    MAX_RCA_SUPPORTING_LOGS: int = 30

    # Ingestion & Anomaly Limits
    MAX_UPLOAD_SIZE_BYTES: int = 100 * 1024 * 1024  # 100 MB
    ANOMALY_Z_SCORE_THRESHOLD: float = 3.0
    ANOMALY_IQR_MULTIPLIER: float = 1.5
    MINIMUM_ANOMALY_ABSOLUTE_COUNT: int = 10

    # Security & CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
