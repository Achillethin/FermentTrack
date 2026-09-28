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
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.concurrency import run_in_threadpool

from fermenttrack.auth import get_current_user_id
from fermenttrack.database import get_db
from fermenttrack.models import Batch, BatchIngredient, Ingredient, OrganismEnzyme
from fermenttrack.prediction import population
from fermenttrack.prediction.organisms import ORGANISM_KINETICS
from fermenttrack.prediction.priors import Prior
from fermenttrack.prediction.service import (
    MAX_HORIZON_H,
    MeasurementIn,
    OrganismIn,
    PredictionInputs,
    PredictionUnavailable,
    RecipeIn,
    population_samples,
    predict,
)
from fermenttrack.reminders import now_utc
from fermenttrack.routers.batches import _get_batch, _resolve_batch_organisms
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
    user_id: str = Depends(get_current_user_id),
) -> PredictionOut:
    batch = await _get_batch(
        batch_id, db, user_id=user_id, with_measurements=True, with_culture=True
    )

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
            .where(OrganismEnzyme.organism_id.in_([t[0].id for t in organisms]))
            .options(selectinload(OrganismEnzyme.enzyme))
        )
        for oe in links.scalars():
            enzymes.setdefault(oe.organism_id, []).append(oe.enzyme.ec_number)

    started = _utc(batch.started_at)
    finished = batch.outcome != "in_progress"
    # a finished batch's "now" is when it ended, not today
    now = _utc(batch.ended_at) if finished and batch.ended_at is not None else now_utc()
    now_h = max((now - started).total_seconds() / 3600.0, 0.0)

    # Pooled population priors (empirical-Bayes plug-in, prediction/population.py) for
    # each organism this batch models — resolved here, not in service.py, which is pure/
    # no-DB by design; below MIN_POOLED_OBS batches this just returns the literature Prior.
    population_priors: dict[str, dict[str, Prior]] = {}
    for o, *_rest in organisms:
        kin = ORGANISM_KINETICS.get(o.name)
        if kin is None:
            continue
        population_priors[o.name] = {
            name: await population.population_prior_for(db, o.id, name, getattr(kin, name))
            for name in population.POOLED_PARAMS
        }

    inputs = PredictionInputs(
        fermentation_type=batch.culture.type,
        now_h=now_h,
        expected_temperature_c=batch.expected_temperature_c,
        organisms=tuple(
            OrganismIn(o.name, o.kingdom, tuple(sorted(enzymes.get(o.id, []))))
            for o, *_ in sorted(organisms, key=lambda os: os[0].name)
        ),
        organism_source="custom" if any(t[1] != "default" for t in organisms) else "default",
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
        finished=finished,
        population_priors=population_priors,
    )
    try:
        body = await run_in_threadpool(predict, inputs, temperature_c, horizon_h)
    except PredictionUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None

    # Pool only a batch that actually calibrated: "prior_only" (no usable pH/gravity/
    # Brix readings) has no reweighted posterior — its "mean" would just be prior-
    # sampling noise, not information, and must not count as a pooled observation.
    if finished and batch.population_pooled_at is None and body.get("status") == "calibrated":
        # Atomic claim (compare-and-swap on population_pooled_at IS NULL): two
        # concurrent requests for the same finished batch (double-click, two tabs) must
        # not both pool it — only the request whose UPDATE actually matches a row wins.
        claim = await db.execute(
            update(Batch)
            .where(Batch.id == batch.id, Batch.population_pooled_at.is_(None))
            .values(population_pooled_at=now_utc())
        )
        if claim.rowcount == 1:
            samples = population_samples(inputs)
            if samples is None:
                # predict() didn't run inference this call (served from an in-process
                # cache), so there's nothing to pool yet — undo the claim and let a
                # later call retry rather than marking this batch pooled for nothing.
                await db.rollback()
            else:
                for o, *_rest in organisms:
                    kin = ORGANISM_KINETICS.get(o.name)
                    per_param = samples.get(o.name)
                    if kin is None or per_param is None:
                        continue
                    for name in population.POOLED_PARAMS:
                        values, weights = per_param[name]
                        await population.update_population_prior(
                            db, o.id, name, values, weights, getattr(kin, name).scale
                        )
                await db.commit()

    # cached outputs are keyed per hour: report the exact start and "now"
    body["started_at"] = started
    body["now_h"] = round(now_h, 3)
    return PredictionOut.model_validate(body)
