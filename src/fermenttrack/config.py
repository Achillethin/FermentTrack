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

    # Supabase project URL (https://<ref>.supabase.co). Projects on JWT signing
    # keys (the default for new ones) sign access tokens with ES256/RS256; the
    # public keys come from <url>/auth/v1/.well-known/jwks.json.
    supabase_url: str | None = None

    # Legacy Supabase JWT secret (Project Settings -> API -> JWT Secret), only
    # needed if the project still signs access tokens with HS256. With neither
    # this nor supabase_url set, authed routes return 503 (tests bypass auth
    # via dependency_overrides).
    supabase_jwt_secret: str | None = None

    # Comma-separated Supabase user ids (JWT `sub`) with read-only access to every
    # user's logbook and bakes (routers/admin.py). Server-side on purpose: nothing a
    # client can put in its token (user_metadata is user-editable) grants it.
    admin_user_ids: str = ""

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
