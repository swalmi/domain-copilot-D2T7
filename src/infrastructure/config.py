from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables using Pydantic Settings."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_title: str = "Domain Copilot"
    allow_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:8000"]
    )

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/domain_copilot"
    )
    redis_url: str = "redis://localhost:6379/0"


    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "llama3.2:3b"
    ollama_embedding_model: str = "nomic-embed-text"

    openrouter_api_key: str = ""
    openrouter_model_name: str = "nvidia"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    min_confidence_score: float = 0.01

    @field_validator("allow_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Parse comma-separated string or list into a clean list of allowed CORS origins."""
        if isinstance(v, str):
            origins = [origin.strip() for origin in v.split(",") if origin.strip()]
            if "*" in origins:
                raise ValueError(
                    "Wildcard '*' is strictly prohibited in CORS origins for security compliance."
                )
            return origins
        if isinstance(v, list):
            if "*" in v:
                raise ValueError(
                    "Wildcard '*' is strictly prohibited in CORS origins for security compliance."
                )
            return v
        return ["http://localhost:3000", "http://localhost:8000"]

    @field_validator("database_url", mode="before")
    @classmethod
    def fix_async_db_url(cls, v: str) -> str:
        """Ensure PostgreSQL database URL uses the asyncpg driver prefix."""
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton instance of application settings."""
    return Settings()
