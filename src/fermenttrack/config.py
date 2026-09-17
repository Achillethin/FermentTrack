"""App settings, loaded from env / .env via pydantic-settings."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FERMENTTRACK_", env_file=".env", extra="ignore")

    # Postgres in production; tests override via FERMENTTRACK_DATABASE_URL to sqlite.
    database_url: str = "postgresql+psycopg://fermenttrack:fermenttrack@localhost:5432/fermenttrack"


settings = Settings()
