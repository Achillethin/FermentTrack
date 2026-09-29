"""Admin read access across accounts (FERMENTTRACK_ADMIN_USER_IDS): every account's
logbook and cultures. Read-only: a bake is opened through the normal batch routes, whose
read-only endpoints let an admin through (routers/batches.py `_get_batch(admin_read=)`);
nothing here or there lets an admin change another account's data.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.auth import require_admin
from fermenttrack.database import get_db
from fermenttrack.models import Culture
from fermenttrack.routers.me import log_entries
from fermenttrack.schemas import AdminCultureOut, LogEntryOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/log", response_model=list[LogEntryOut])
async def all_logs(
    q: str | None = Query(None, max_length=200),
    culture_id: uuid.UUID | None = None,
    type: str | None = None,
    since: datetime | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=10_000),
    db: AsyncSession = Depends(get_db),  # noqa: B008
    admin_id: str = Depends(require_admin),
) -> list[LogEntryOut]:
    """Every account's logbook, newest first; each entry says whose account it is."""
    return await log_entries(
        db, [], q, culture_id, type, since, limit, offset, with_owner=True
    )


@router.get("/cultures", response_model=list[AdminCultureOut])
async def all_cultures(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    admin_id: str = Depends(require_admin),
) -> list[Culture]:
    result = await db.execute(select(Culture).order_by(Culture.created_at.desc()))
    return list(result.scalars().all())
