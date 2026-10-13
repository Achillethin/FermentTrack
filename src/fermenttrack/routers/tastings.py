"""A batch's tastings (design § 11.2): POST and GET /batches/{id}/tastings, DELETE
/batches/{id}/tastings/{tasting_id}. The batch's owner only (404 otherwise, admins included: a
tasting's notes are the user's own). Any batch can be tasted, recommended or not: the
calibration gate's baseline needs both (§ 13.2).

- **Time:** the request gives tasted_at (default now; without a zone, UTC) and the server
  stores t_h, the hours since the batch started: the calibration gate reads the batch's
  recommendation link's P series at that t_h (models.RecommendationLink.p_series). A time
  before the batch started is a 422; so is one in the future beyond FUTURE_SKEW (a client
  clock a little ahead is taken as now). A batch may be tasted after it ended.
- **Reminders:** a tasting closes the batch's open tasting reminders (the stop-by prompt that
  Start batch creates, routers/recommendations.py); a stage change never does.
- **Privacy:** notes are free text owned by the user: never logged, never shown to another
  user (the community cards count tasted batches and average their liking, nothing more);
  exported by GET /me/export, deleted with the batch (DELETE /me). Control characters other
  than tab and line breaks are refused (422): Postgres refuses a NUL, and its error would carry
  the text; the engine hides bound values from errors and logs anyway (database.py).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.auth import get_current_user_id
from fermenttrack.database import get_db
from fermenttrack.models import TASTING_REMINDER, Reminder, Tasting
from fermenttrack.reminders import now_utc
from fermenttrack.routers.batches import _get_batch
from fermenttrack.schemas import TastingIn, TastingOut

router = APIRouter(prefix="/batches", tags=["tastings"])
FUTURE_SKEW = timedelta(minutes=10)


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)  # SQLite drops the zone


def hours_since_start(started_at: datetime, tasted_at: datetime | None, now: datetime) -> float:
    """t_h: the hours from the batch's start to tasted_at (None: now). Raises HTTPException 422
    for a time before the start, or after now by more than FUTURE_SKEW."""
    at = now if tasted_at is None else _utc(tasted_at)
    if at > now + FUTURE_SKEW:
        raise HTTPException(status_code=422, detail="tasted_at is in the future")
    at = min(at, now)
    started = _utc(started_at)
    if at < started:
        raise HTTPException(status_code=422, detail="tasted_at is before the batch started")
    return round((at - started).total_seconds() / 3600.0, 3)


@router.post("/{batch_id}/tastings", response_model=TastingOut, status_code=201)
async def add_tasting(
    batch_id: uuid.UUID,
    payload: TastingIn,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user_id: str = Depends(get_current_user_id),
) -> Tasting:
    batch = await _get_batch(batch_id, db, user_id=user_id)
    now = now_utc()
    tasting = Tasting(
        batch_id=batch.id, t_h=hours_since_start(batch.started_at, payload.tasted_at, now),
        ratings=payload.ratings, liking=payload.liking, make_again=payload.make_again,
        notes=payload.notes, created_at=now,
    )  # fmt: skip
    db.add(tasting)
    await db.execute(
        update(Reminder)
        .where(
            Reminder.batch_id == batch.id,
            Reminder.kind == TASTING_REMINDER,
            Reminder.completed_at.is_(None),
        )
        .values(completed_at=now)
    )
    await db.commit()
    await db.refresh(tasting)
    return tasting


@router.get("/{batch_id}/tastings", response_model=list[TastingOut])
async def list_tastings(
    batch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user_id: str = Depends(get_current_user_id),
) -> list[Tasting]:
    """The batch's tastings, earliest first."""
    await _get_batch(batch_id, db, user_id=user_id)  # 404 unless yours
    found = await db.execute(
        select(Tasting)
        .where(Tasting.batch_id == batch_id)
        .order_by(Tasting.t_h, Tasting.created_at, Tasting.id)
    )
    return list(found.scalars())


@router.delete("/{batch_id}/tastings/{tasting_id}", status_code=204)
async def delete_tasting(
    batch_id: uuid.UUID,
    tasting_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user_id: str = Depends(get_current_user_id),
) -> None:
    await _get_batch(batch_id, db, user_id=user_id)  # 404 unless yours
    found = await db.execute(
        select(Tasting).where(Tasting.id == tasting_id, Tasting.batch_id == batch_id)
    )
    tasting = found.scalar_one_or_none()
    if tasting is None:
        raise HTTPException(status_code=404, detail="Tasting not found")
    await db.delete(tasting)
    await db.commit()
