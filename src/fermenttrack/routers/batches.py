from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fermenttrack.database import get_db
from fermenttrack.models import Batch, Culture, Measurement, Reminder
from fermenttrack.reminders import build_reminder_for_stage, now_utc
from fermenttrack.schemas import (
    BatchCompare,
    BatchCreate,
    BatchOut,
    BatchTimeline,
    MeasurementCreate,
    MeasurementOut,
    NoteCreate,
    StageAdvance,
    TimelineEvent,
)
from fermenttrack.stages import InvalidStageError, first_stage, next_stage_name

router = APIRouter(prefix="/batches", tags=["batches"])


async def _get_batch(
    batch_id: uuid.UUID,
    db: AsyncSession,
    *,
    with_measurements: bool = False,
    with_culture: bool = False,
) -> Batch:
    stmt = select(Batch).where(Batch.id == batch_id)
    if with_measurements:
        stmt = stmt.options(selectinload(Batch.measurements))
    if with_culture:
        stmt = stmt.options(selectinload(Batch.culture))
    result = await db.execute(stmt)
    batch = result.scalar_one_or_none()
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    return batch


@router.post("", response_model=BatchOut, status_code=201)
async def create_batch(payload: BatchCreate, db: AsyncSession = Depends(get_db)) -> Batch:
    culture = await db.get(Culture, payload.culture_id)
    if culture is None:
        raise HTTPException(status_code=404, detail="Culture not found")

    started_at = now_utc()
    initial_stage = first_stage(culture.type)
    batch = Batch(
        culture_id=payload.culture_id,
        started_at=started_at,
        current_stage=initial_stage,
        stage_entered_at=started_at,
        target=payload.target,
    )
    db.add(batch)
    await db.flush()

    reminder = build_reminder_for_stage(batch, culture.type, initial_stage, started_at)
    if reminder is not None:
        db.add(reminder)

    await db.commit()
    await db.refresh(batch)
    return batch


@router.patch("/{batch_id}/stage", response_model=BatchOut)
async def advance_stage(
    batch_id: uuid.UUID, payload: StageAdvance, db: AsyncSession = Depends(get_db)
) -> Batch:
    batch = await _get_batch(batch_id, db, with_culture=True)
    substrate = batch.culture.type

    try:
        target_stage = payload.stage or next_stage_name(substrate, batch.current_stage)
        if target_stage is None:
            raise HTTPException(status_code=400, detail="Batch is already at its final stage")
        entered_at = now_utc()
        # validates stage name
        reminder = build_reminder_for_stage(batch, substrate, target_stage, entered_at)
    except InvalidStageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    batch.current_stage = target_stage
    batch.stage_entered_at = entered_at
    if target_stage in ("ready", "done"):
        batch.outcome = "success"
        batch.ended_at = entered_at

    # Superseded by the new stage's reminder — mark prior open reminders done
    # rather than leaving stale ones (e.g. a past stage's timer) in the list.
    await db.execute(
        update(Reminder)
        .where(Reminder.batch_id == batch.id, Reminder.completed_at.is_(None))
        .values(completed_at=entered_at)
    )

    if reminder is not None:
        db.add(reminder)

    await db.commit()
    await db.refresh(batch)
    return batch


@router.post("/{batch_id}/measure", response_model=MeasurementOut, status_code=201)
async def add_measurement(
    batch_id: uuid.UUID, payload: MeasurementCreate, db: AsyncSession = Depends(get_db)
) -> Measurement:
    batch = await _get_batch(batch_id, db)
    measurement = Measurement(batch_id=batch.id, **payload.model_dump())
    db.add(measurement)
    await db.commit()
    await db.refresh(measurement)
    return measurement


@router.post("/{batch_id}/note", response_model=MeasurementOut, status_code=201)
async def add_note(
    batch_id: uuid.UUID, payload: NoteCreate, db: AsyncSession = Depends(get_db)
) -> Measurement:
    """Notes are stored as measurements with type="note" (no separate table
    in docs/ARCHITECTURE.md's schema — value_text carries the note body)."""
    batch = await _get_batch(batch_id, db)
    note = Measurement(batch_id=batch.id, type="note", value_text=payload.text)
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


@router.get("/{batch_id}/timeline", response_model=BatchTimeline)
async def get_timeline(batch_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> BatchTimeline:
    batch = await _get_batch(batch_id, db, with_measurements=True)
    events = [
        TimelineEvent(
            kind="note" if m.type == "note" else "measurement",
            timestamp=m.measured_at,
            detail={
                "type": m.type,
                "value_numeric": m.value_numeric,
                "value_text": m.value_text,
                "notes": m.notes,
            },
        )
        for m in sorted(batch.measurements, key=lambda m: m.measured_at)
    ]
    return BatchTimeline(batch=BatchOut.model_validate(batch), events=events)


@router.get("/compare", response_model=BatchCompare)
async def compare_batches(
    batch_id: list[uuid.UUID] = Query(...), db: AsyncSession = Depends(get_db)
) -> BatchCompare:
    if len(batch_id) < 2:
        raise HTTPException(status_code=400, detail="Provide at least two batch_id query params")

    result = await db.execute(
        select(Batch).where(Batch.id.in_(batch_id)).options(selectinload(Batch.measurements))
    )
    batches = list(result.scalars().all())
    found_ids = {b.id for b in batches}
    missing = set(batch_id) - found_ids
    if missing:
        raise HTTPException(status_code=404, detail=f"Batch(es) not found: {missing}")

    measurements = {
        str(b.id): [
            MeasurementOut.model_validate(m)
            for m in sorted(b.measurements, key=lambda m: m.measured_at)
        ]
        for b in batches
    }
    return BatchCompare(batches=[BatchOut.model_validate(b) for b in batches], measurements=measurements)
