"""Per-account data export and delete (GDPR: right to access / right to erasure), plus the logbook.

No FermentTrack users table — Culture.owner_id (the Supabase JWT `sub`) is the
only row that carries the account boundary; everything else hangs off Culture
via cascading relationships (models.py).

Community recipes (design § 10.3) are the exception: published to the shared library, they
outlive the account. DELETE /me detaches them (owner_id and source_batch_id set null; the
pseudonym stays), and an admin's reviews lose their reviewer id (reviewed_by set null). GET
/export keeps its per-culture shape; your published recipes, every
status with the reviewer's reason, are exported by GET /me/community-recipes.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fermenttrack.auth import get_current_user_id, is_admin
from fermenttrack.database import get_db
from fermenttrack.models import (
    Batch,
    BatchEvidence,
    CommunityRecipe,
    Culture,
    Measurement,
    RecommendationJob,
)
from fermenttrack.routers.community import recipe_out
from fermenttrack.schemas import (
    CommunityRecipeOut,
    CultureExportOut,
    LogBatchOut,
    LogCultureOut,
    LogEntryOut,
    WhoAmIOut,
)

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


@router.get("/community-recipes", response_model=list[CommunityRecipeOut])
async def my_community_recipes(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user_id: str = Depends(get_current_user_id),
) -> list[CommunityRecipeOut]:
    """The recipes you published (design § 10.3), every status, newest first: the export of
    your community recipes (GET /export lists cultures)."""
    found = await db.execute(
        select(CommunityRecipe)
        .where(CommunityRecipe.owner_id == user_id)
        .order_by(CommunityRecipe.created_at.desc(), CommunityRecipe.id)
    )
    return [CommunityRecipeOut.model_validate(recipe_out(row)) for row in found.scalars()]


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
    return await log_entries(
        db, [Culture.owner_id == user_id], q, culture_id, type, since, limit, offset
    )


async def log_entries(
    db: AsyncSession,
    scope: list[Any],
    q: str | None,
    culture_id: uuid.UUID | None,
    type: str | None,
    since: datetime | None,
    limit: int,
    offset: int,
    *,
    with_owner: bool = False,
) -> list[LogEntryOut]:
    """The logbook over the cultures matching `scope`: one account's (/me/log), or every
    account's for an admin (/admin/log, with_owner labels each entry's account)."""
    pat = _like(q) if q else None
    where = list(scope)
    if culture_id:
        where.append(Culture.id == culture_id)

    # (timestamp, id, kind, culture, batch, detail): lightweight rows; pydantic objects only for the page.
    entries: list[tuple[datetime, str, str, Culture, Batch, dict]] = []

    # Stage history is kept as stage_change measurement rows (routers/batches.py
    # advance_stage): the "stage-change" filter reads those.
    mtype = "stage_change" if type == "stage-change" else type
    stmt = (
        select(Measurement, Batch, Culture)
        .join(Batch, Measurement.batch_id == Batch.id)
        .join(Culture, Batch.culture_id == Culture.id)
        .where(*where)
        .order_by(Measurement.measured_at.desc(), Measurement.id.desc())
        .limit(offset + limit)  # top offset+limit of each source suffice for the merged page
    )
    if mtype:  # case-insensitive: the UI stores "pH", the iSpindel webhook "ph"
        stmt = stmt.where(func.lower(Measurement.type) == mtype.lower())
    if since:
        stmt = stmt.where(Measurement.measured_at >= since)
    if pat:
        stmt = stmt.where(or_(
            Measurement.value_text.ilike(pat, escape="\\"),
            Measurement.notes.ilike(pat, escape="\\"),
        ))
    for m, b, c in (await db.execute(stmt)).all():
        if m.type == "stage_change":
            entries.append((m.measured_at, str(m.id), "stage-change", c, b, {"stage": m.value_text}))
            continue
        entries.append((m.measured_at, str(m.id), "note" if m.type == "note" else "measurement", c, b, {
            "type": m.type,
            "value_numeric": m.value_numeric,
            "value_text": m.value_text,
            "notes": m.notes,
        }))

    if not type or type == "stage-change":
        # Batches without logged stage history (created before it was kept, or still in their
        # first stage): one entry from the current stage's entry time.
        logged = (
            select(Measurement.id)
            .where(Measurement.batch_id == Batch.id, Measurement.type == "stage_change")
            .exists()
        )
        stmt = (
            select(Batch, Culture)
            .join(Culture, Batch.culture_id == Culture.id)
            .where(*where, ~logged)
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
            owner=c.owner_id if with_owner else None,
        )
        for ts, eid, kind, c, b, detail in entries[offset : offset + limit]
    ]


@router.get("", response_model=WhoAmIOut)
async def who_am_i(user_id: str = Depends(get_current_user_id)) -> WhoAmIOut:
    """The caller's account id (to share with the operator, e.g. to be made an admin) and
    whether it has admin read access."""
    return WhoAmIOut(user_id=user_id, admin=is_admin(user_id))


@router.delete("", status_code=204)
async def delete_my_data(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> None:
    result = await db.execute(select(Culture).where(Culture.owner_id == user_id))
    cultures = result.scalars().all()
    # learned-kinetics evidence carries the owner id: erase it explicitly (the FK cascade
    # covers it on Postgres; SQLite does not enforce foreign keys)
    await db.execute(
        sa_delete(BatchEvidence).where(
            (BatchEvidence.owner_id == user_id)
            | BatchEvidence.culture_id.in_([c.id for c in cultures])
        )
    )
    # born_from links between one's own cultures would block deleting a parent before
    # its child (FK checked per statement on Postgres): detach the lineage first
    await db.execute(
        update(Culture).where(Culture.owner_id == user_id).values(born_from=None)
    )
    # recommender jobs (deep searches) carry the owner id too; one running is dropped
    await db.execute(sa_delete(RecommendationJob).where(RecommendationJob.owner_id == user_id))
    # published community recipes stay in the library, detached (design § 10.3): no owner,
    # no source batch (the FK sets it null on Postgres; SQLite does not enforce it)
    await db.execute(
        update(CommunityRecipe)
        .where(CommunityRecipe.owner_id == user_id)
        .values(owner_id=None, source_batch_id=None)
    )
    # an admin's reviews stay (status, reason, date) without their user id
    await db.execute(
        update(CommunityRecipe)
        .where(CommunityRecipe.reviewed_by == user_id)
        .values(reviewed_by=None)
    )
    for culture in cultures:
        await db.delete(culture)  # cascades to batches and everything under them
    await db.commit()
