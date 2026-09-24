"""GET /batches/{id}/prediction — the kinetic fermentation forecast.

Spec: docs/superpowers/specs/2026-09-24-fermentation-prediction-design.md. The model run
is CPU-bound numpy (up to a few seconds on a small instance), so it runs in the
threadpool, off the event loop; results are cached per input fingerprint in
fermenttrack.prediction.service.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.concurrency import run_in_threadpool

from fermenttrack.database import get_db
from fermenttrack.models import Batch, BatchIngredient, Ingredient, OrganismEnzyme
from fermenttrack.prediction.service import (
    MAX_HORIZON_H,
    MeasurementIn,
    OrganismIn,
    PredictionInputs,
    RecipeIn,
    predict,
)
from fermenttrack.reminders import now_utc
from fermenttrack.routers.batches import _resolve_batch_organisms
from fermenttrack.schemas import PredictionOut

router = APIRouter(prefix="/batches", tags=["prediction"])


def _utc(dt: datetime) -> datetime:
    # SQLite drops tz-awareness (see routers/batches.py get_batch_preview); all app
    # timestamps are UTC by convention.
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


@router.get("/{batch_id}/prediction", response_model=PredictionOut)
async def get_batch_prediction(
    batch_id: uuid.UUID,
    temperature_c: float | None = Query(
        default=None, ge=-5.0, le=60.0, description="What-if temperature from now on (°C)"
    ),
    horizon_h: float | None = Query(
        default=None, gt=0.0, le=MAX_HORIZON_H, description="Forecast window from batch start"
    ),
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PredictionOut:
    result = await db.execute(
        select(Batch)
        .where(Batch.id == batch_id)
        .options(selectinload(Batch.measurements), selectinload(Batch.culture))
    )
    batch = result.scalar_one_or_none()
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")

    rows = await db.execute(
        select(BatchIngredient)
        .where(BatchIngredient.batch_id == batch_id)
        .options(selectinload(BatchIngredient.ingredient).selectinload(Ingredient.nutrients))
    )
    recipe = tuple(
        RecipeIn(
            bi.ingredient.name,
            bi.quantity,
            bi.unit,
            {n.nutrient: n.amount_per_100g for n in bi.ingredient.nutrients},
            bi.role,
        )
        for bi in rows.scalars()
    )

    organisms = await _resolve_batch_organisms(batch, db)
    enzymes: dict[uuid.UUID, list[str]] = {}
    if organisms:
        links = await db.execute(
            select(OrganismEnzyme)
            .where(OrganismEnzyme.organism_id.in_([o.id for o, _ in organisms]))
            .options(selectinload(OrganismEnzyme.enzyme))
        )
        for oe in links.scalars():
            enzymes.setdefault(oe.organism_id, []).append(oe.enzyme.ec_number)

    started = _utc(batch.started_at)
    inputs = PredictionInputs(
        fermentation_type=batch.culture.type,
        now_h=max((now_utc() - started).total_seconds() / 3600.0, 0.0),
        expected_temperature_c=batch.expected_temperature_c,
        organisms=tuple(
            OrganismIn(o.name, o.kingdom, tuple(sorted(enzymes.get(o.id, []))))
            for o, _ in sorted(organisms, key=lambda os: os[0].name)
        ),
        organism_source="custom" if any(src != "default" for _, src in organisms) else "default",
        recipe=recipe,
        measurements=tuple(
            MeasurementIn(
                m.type,
                (_utc(m.measured_at) - started).total_seconds() / 3600.0,
                m.value_numeric,
            )
            for m in sorted(batch.measurements, key=lambda m: m.measured_at)
            if m.type != "note"
        ),
        finished=batch.outcome != "in_progress",
    )
    body = await run_in_threadpool(predict, inputs, temperature_c, horizon_h)
    return PredictionOut.model_validate(body)
