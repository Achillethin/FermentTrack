"""App settings, loaded from env / .env via pydantic-settings."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FERMENTTRACK_", env_file=".env", extra="ignore")

    # Postgres in production; tests override via FERMENTTRACK_DATABASE_URL to sqlite.
    database_url: str = "postgresql+psycopg://fermenttrack:fermenttrack@localhost:5432/fermenttrack"

    # Comma-separated list of allowed CORS origins (the deployed frontend's
    # origin, e.g. https://<user>.github.io). Defaults cover local Vite dev.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"


settings = Settings()
