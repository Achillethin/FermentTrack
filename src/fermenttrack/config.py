"""App settings, loaded from env / .env via pydantic-settings."""

from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FERMENTTRACK_", env_file=".env", extra="ignore")

    # Postgres in production; tests override via FERMENTTRACK_DATABASE_URL to sqlite.
    database_url: str = "postgresql+psycopg://fermenttrack:fermenttrack@localhost:5432/fermenttrack"

    # Comma-separated list of allowed CORS origins (the deployed frontend's
    # origin, e.g. https://<user>.github.io). Defaults cover local Vite dev.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @field_validator("database_url")
    @classmethod
    def _use_psycopg3_dialect(cls, v: str) -> str:
        # Hosted Postgres providers (Supabase, Render, ...) hand out plain
        # "postgresql://" URLs, which makes SQLAlchemy default to the psycopg2
        # dialect — not installed here, this project uses psycopg v3. Normalize
        # once so nobody has to remember to hand-edit the copied URL.
        if v.startswith("postgresql://"):
            return "postgresql+psycopg://" + v.removeprefix("postgresql://")
        return v


settings = Settings()
