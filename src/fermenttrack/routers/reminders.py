from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.database import get_db
from fermenttrack.models import Reminder
from fermenttrack.reminders import now_utc
from fermenttrack.schemas import ReminderOut, ReminderSnooze

router = APIRouter(prefix="/reminders", tags=["reminders"])


@router.get("", response_model=list[ReminderOut])
async def list_reminders(db: AsyncSession = Depends(get_db)) -> list[Reminder]:
    """Upcoming reminders (next 48h), per docs/ARCHITECTURE.md."""
    horizon = now_utc() + timedelta(hours=48)
    result = await db.execute(
        select(Reminder)
        .where(Reminder.completed_at.is_(None))
        .where(Reminder.due_at <= horizon)
        .order_by(Reminder.due_at)
    )
    return list(result.scalars().all())


async def _get_reminder(reminder_id: uuid.UUID, db: AsyncSession) -> Reminder:
    reminder = await db.get(Reminder, reminder_id)
    if reminder is None:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return reminder


@router.patch("/{reminder_id}/done", response_model=ReminderOut)
async def mark_done(reminder_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Reminder:
    reminder = await _get_reminder(reminder_id, db)
    reminder.completed_at = now_utc()
    await db.commit()
    await db.refresh(reminder)
    return reminder


@router.patch("/{reminder_id}/snooze", response_model=ReminderOut)
async def snooze(
    reminder_id: uuid.UUID, payload: ReminderSnooze, db: AsyncSession = Depends(get_db)
) -> Reminder:
    reminder = await _get_reminder(reminder_id, db)
    reminder.due_at = payload.until
    await db.commit()
    await db.refresh(reminder)
    return reminder
