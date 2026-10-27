from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.auth import get_current_user_id
from fermenttrack.database import get_db
from fermenttrack.models import STAGE_REMINDER, Batch, Culture, Reminder
from fermenttrack.reminders import now_utc
from fermenttrack.routers.batches import move_to_stage
from fermenttrack.stages import SETUP_STAGES, next_stage_name
from fermenttrack.schemas import ReminderOut, ReminderSnooze

router = APIRouter(prefix="/reminders", tags=["reminders"])


@router.get("", response_model=list[ReminderOut])
async def list_reminders(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> list[Reminder]:
    """Upcoming reminders (next 48h), per docs/ARCHITECTURE.md."""
    horizon = now_utc() + timedelta(hours=48)
    result = await db.execute(
        select(Reminder)
        .join(Batch, Reminder.batch_id == Batch.id)
        .join(Culture, Batch.culture_id == Culture.id)
        .where(Reminder.completed_at.is_(None))
        .where(Reminder.due_at <= horizon)
        .where(Culture.owner_id == user_id)
        .order_by(Reminder.due_at)
    )
    return list(result.scalars().all())


async def _get_reminder(reminder_id: uuid.UUID, db: AsyncSession, user_id: str) -> Reminder:
    result = await db.execute(
        select(Reminder)
        .join(Batch, Reminder.batch_id == Batch.id)
        .join(Culture, Batch.culture_id == Culture.id)
        .where(Reminder.id == reminder_id, Culture.owner_id == user_id)
    )
    reminder = result.scalar_one_or_none()
    if reminder is None:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return reminder


@router.patch("/{reminder_id}/done", response_model=ReminderOut)
async def mark_done(
    reminder_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> Reminder:
    reminder = await _get_reminder(reminder_id, db, user_id)
    reminder.completed_at = now_utc()
    if reminder.kind == STAGE_REMINDER:
        batch = await db.get(Batch, reminder.batch_id, options=[selectinload(Batch.culture)])
        assert batch is not None
        stage = (batch.culture.type, batch.current_stage)
        if stage in SETUP_STAGES and batch.outcome == "in_progress":
            nxt = next_stage_name(*stage)
            if nxt is not None:
                await move_to_stage(db, batch, nxt)  # supersedes this reminder too
    await db.commit()
    await db.refresh(reminder)
    return reminder


@router.patch("/{reminder_id}/snooze", response_model=ReminderOut)
async def snooze(
    reminder_id: uuid.UUID,
    payload: ReminderSnooze,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> Reminder:
    reminder = await _get_reminder(reminder_id, db, user_id)
    reminder.due_at = payload.until
    await db.commit()
    await db.refresh(reminder)
    return reminder
