"""Application configuration via pydantic-settings — typed, env-driven, with safe defaults."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, sourced from environment variables / .env.

    All secrets and runtime configuration flow through this class — no raw
    os.getenv calls in the rest of the codebase.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://postsearch:postsearch@db:5432/postsearch"

    # HMAC secret for cursor pagination tokens
    secret_key: str = "change-me-in-production"

    # Server
    app_port: int = 8000


settings = Settings()
