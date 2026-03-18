"""Configuration management."""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    database_url: str = "sqlite:///./agent_studio.db"
    redis_url: str = "redis://localhost:6379/0"
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    log_level: str = "info"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
