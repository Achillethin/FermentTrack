"""Async SQLAlchemy engine/session setup."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from fermenttrack.config import settings


class Base(DeclarativeBase):
    pass


def _to_async_url(url: str) -> str:
    # psycopg v3 supports asyncio natively under the same "psycopg" dialect name.
    if url.startswith("sqlite://") and "+aiosqlite" not in url:
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return url


engine = create_async_engine(_to_async_url(settings.database_url), future=True)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
