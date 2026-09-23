from __future__ import annotations

import uuid
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fermenttrack.database import get_db
from fermenttrack.models import Batch, BatchIngredient, Culture, Ingredient, Measurement, Reminder
from fermenttrack.reminders import build_reminder_for_stage, now_utc
from fermenttrack.safety.service import get_safety_report
from fermenttrack.schemas import (
    BatchCompare,
    BatchCreate,
    BatchIngredientCreate,
    BatchIngredientOut,
    BatchOut,
    BatchPreview,
    BatchTimeline,
    CultureOut,
    MeasurementCreate,
    MeasurementOut,
    NoteCreate,
    RuleVerdictOut,
    SafetyReportOut,
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
    with_batch_ingredients: bool = False,
) -> Batch:
    stmt = select(Batch).where(Batch.id == batch_id)
    if with_measurements:
        stmt = stmt.options(selectinload(Batch.measurements))
    if with_culture:
        stmt = stmt.options(selectinload(Batch.culture))
    if with_batch_ingredients:
        stmt = stmt.options(selectinload(Batch.batch_ingredients))
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


def _build_timeline_events(batch: Batch) -> list[TimelineEvent]:
    return [
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


@router.get("/{batch_id}/timeline", response_model=BatchTimeline)
async def get_timeline(batch_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> BatchTimeline:
    batch = await _get_batch(batch_id, db, with_measurements=True)
    return BatchTimeline(batch=BatchOut.model_validate(batch), events=_build_timeline_events(batch))


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


@router.post("/{batch_id}/ingredients", response_model=BatchIngredientOut, status_code=201)
async def add_batch_ingredient(
    batch_id: uuid.UUID, payload: BatchIngredientCreate, db: AsyncSession = Depends(get_db)
) -> BatchIngredient:
    batch = await _get_batch(batch_id, db, with_culture=True)
    ingredient = await db.get(Ingredient, payload.ingredient_id)
    if ingredient is None:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    if not ingredient.is_active:
        raise HTTPException(
            status_code=400,
            detail=f"{ingredient.name!r} is retired; pick a specific ingredient instead",
        )
    if batch.culture.type not in ingredient.fermentation_systems:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{ingredient.name!r} isn't tagged for {batch.culture.type!r} "
                f"(tagged for {ingredient.fermentation_systems})"
            ),
        )

    batch_ingredient = BatchIngredient(
        batch_id=batch.id,
        ingredient_id=ingredient.id,
        quantity=payload.quantity,
        unit=payload.unit,
        role=payload.role or ingredient.default_role,
    )
    db.add(batch_ingredient)
    await db.commit()
    await db.refresh(batch_ingredient)
    return batch_ingredient


@router.get("/{batch_id}/ingredients", response_model=list[BatchIngredientOut])
async def list_batch_ingredients(
    batch_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[BatchIngredient]:
    await _get_batch(batch_id, db)  # raises 404 if the batch doesn't exist
    result = await db.execute(select(BatchIngredient).where(BatchIngredient.batch_id == batch_id))
    return list(result.scalars().all())


@router.get("/{batch_id}/preview", response_model=BatchPreview)
async def get_batch_preview(batch_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> BatchPreview:
    """Presentation-shaped aggregate for the batch-preview UI page — batch
    header, recipe, timeline, and safety advisory in one call. No compound/
    microbial data (see docs/superpowers/specs/2026-09-18-experiment-
    logging-design.md § 2 for why). Scope ceiling: this endpoint is owned by
    that one page's needs; any other consumer should use /timeline and
    /safety directly rather than this growing to serve them too.
    """
    batch = await _get_batch(
        batch_id, db, with_measurements=True, with_culture=True, with_batch_ingredients=True
    )

    now = now_utc()
    stage_entered_at = batch.stage_entered_at
    if stage_entered_at.tzinfo is None:
        # SQLite (used in tests/local dev, see tests/conftest.py) doesn't
        # preserve tz-awareness on TIMESTAMP(timezone=True) columns the way
        # Postgres does — all app timestamps are UTC by convention regardless.
        stage_entered_at = stage_entered_at.replace(tzinfo=timezone.utc)
    days_in_stage = (now - stage_entered_at).total_seconds() / 86400.0

    report = get_safety_report(batch)
    safety = SafetyReportOut(
        safe=report.safe,
        hard_stops=[RuleVerdictOut(**vars(v)) for v in report.hard_stops],
        warnings=[RuleVerdictOut(**vars(v)) for v in report.warnings],
        rules_evaluated=report.rules_evaluated,
        rules_triggered=report.rules_triggered,
        summary_en=report.summary_en,
        summary_fr=report.summary_fr,
    )

    return BatchPreview(
        batch=BatchOut.model_validate(batch),
        culture=CultureOut.model_validate(batch.culture),
        days_in_stage=max(days_in_stage, 0.0),
        recipe=[BatchIngredientOut.model_validate(bi) for bi in batch.batch_ingredients],
        timeline=_build_timeline_events(batch),
        safety=safety,
    )
