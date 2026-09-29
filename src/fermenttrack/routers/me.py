"""Per-account data export and delete (GDPR: right to access / right to erasure), plus the logbook.

No FermentTrack users table — Culture.owner_id (the Supabase JWT `sub`) is the
only row that carries the account boundary; everything else hangs off Culture
via cascading relationships (models.py).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fermenttrack.auth import get_current_user_id
from fermenttrack.database import get_db
from fermenttrack.models import Batch, Culture, Measurement
from fermenttrack.schemas import CultureExportOut, LogBatchOut, LogCultureOut, LogEntryOut

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/export", response_model=list[CultureExportOut])
async def export_my_data(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> list[Culture]:
    result = await db.execute(
        select(Culture)
        .where(Culture.owner_id == user_id)
        .options(selectinload(Culture.batches).selectinload(Batch.measurements))
    )
    return list(result.scalars().unique().all())


def _like(q: str) -> str:
    """Contains-pattern matching the user's %, _ and backslash literally (ESCAPE backslash)."""
    esc = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{esc}%"


@router.get("/log", response_model=list[LogEntryOut])
async def my_log(
    q: str | None = Query(None, max_length=200),
    culture_id: uuid.UUID | None = None,
    type: str | None = None,
    since: datetime | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=10_000),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> list[LogEntryOut]:
    """Reverse-chronological logbook across all of the caller's batches."""
    pat = _like(q) if q else None
    where = [Culture.owner_id == user_id]
    if culture_id:
        where.append(Culture.id == culture_id)

    # (timestamp, id, kind, culture, batch, detail): lightweight rows; pydantic objects only for the page.
    entries: list[tuple[datetime, str, str, Culture, Batch, dict]] = []

    if type != "stage-change":
        stmt = (
            select(Measurement, Batch, Culture)
            .join(Batch, Measurement.batch_id == Batch.id)
            .join(Culture, Batch.culture_id == Culture.id)
            .where(*where)
            .order_by(Measurement.measured_at.desc(), Measurement.id.desc())
            .limit(offset + limit)  # top offset+limit of each source suffice for the merged page
        )
        if type:  # case-insensitive: the UI stores "pH", the iSpindel webhook "ph"
            stmt = stmt.where(func.lower(Measurement.type) == type.lower())
        if since:
            stmt = stmt.where(Measurement.measured_at >= since)
        if pat:
            stmt = stmt.where(or_(
                Measurement.value_text.ilike(pat, escape="\\"),
                Measurement.notes.ilike(pat, escape="\\"),
            ))
        for m, b, c in (await db.execute(stmt)).all():
            entries.append((m.measured_at, str(m.id), "note" if m.type == "note" else "measurement", c, b, {
                "type": m.type,
                "value_numeric": m.value_numeric,
                "value_text": m.value_text,
                "notes": m.notes,
            }))

    if not type or type == "stage-change":
        # Stage history isn't stored: one entry per batch, from its current stage's entry time.
        stmt = (
            select(Batch, Culture)
            .join(Culture, Batch.culture_id == Culture.id)
            .where(*where)
        )
        if since:
            stmt = stmt.where(Batch.stage_entered_at >= since)
        if pat:
            stmt = stmt.where(Batch.current_stage.ilike(pat, escape="\\"))
        for b, c in (await db.execute(stmt)).all():
            entries.append((b.stage_entered_at, str(b.id), "stage-change", c, b, {"stage": b.current_stage}))

    entries.sort(key=lambda e: (e[0], e[1]), reverse=True)
    return [
        LogEntryOut(
            id=uuid.UUID(eid),
            culture=LogCultureOut(id=c.id, name=c.name, type=c.type),
            batch=LogBatchOut(id=b.id, current_stage=b.current_stage, started_at=b.started_at),
            kind=kind, timestamp=ts, detail=detail,
        )
        for ts, eid, kind, c, b, detail in entries[offset : offset + limit]
    ]


@router.delete("", status_code=204)
async def delete_my_data(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> None:
    result = await db.execute(select(Culture).where(Culture.owner_id == user_id))
    for culture in result.scalars().all():
        await db.delete(culture)  # cascades to batches and everything under them
    await db.commit()
