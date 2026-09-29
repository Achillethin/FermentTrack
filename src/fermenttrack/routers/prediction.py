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
from fermenttrack.prediction.bake import BakeInputs, evidence_for
from fermenttrack.prediction.bake import forecast as bake_forecast
from fermenttrack.prediction.sourdough import STYLES, compile_plan, plan_from_dict, plan_to_dict
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


async def _learn(
    db: AsyncSession, batch: Batch, ferment_type: str, style: str | None, evidence: list | None
) -> None:
    claim = await db.execute(
        update(Batch)
        .where(Batch.id == batch.id, Batch.population_pooled_at.is_(None))
        .values(population_pooled_at=now_utc())
    )
    if claim.rowcount != 1:
        return
    if evidence is None:
        # served from a cache without running inference: undo the claim, retry next call
        await db.rollback()
        return
    await population.record_evidence(
        db, batch_id=batch.id, culture_id=batch.culture_id, owner_id=batch.culture.owner_id,
        ferment_type=ferment_type, style=style, outcome=batch.outcome, evidence=evidence,
    )  # fmt: skip
    await db.commit()


# stage changes that start a plan phase: the mix starts the bulk; shaping starts the proof
_PHASE_STAGES = (("bulk_ferment",), ("shape", "cold_retard"))


def _known_bounds(batch: Batch, started: datetime) -> tuple[float, ...]:
    """Logged starts of the bulk and proof phases (h from the levain feed)."""
    changes = sorted(
        (m for m in batch.measurements if m.type == "stage_change"), key=lambda m: m.measured_at
    )
    when: dict[str, datetime] = {}
    for m in changes:
        when.setdefault(m.value_text or "", _utc(m.measured_at))
    # batches started before stage history was logged: the current stage's entry time
    when.setdefault(batch.current_stage, _utc(batch.stage_entered_at))
    out: list[float] = []
    for stages in _PHASE_STAGES:
        t = next((when[s] for s in stages if s in when), None)
        if t is None:
            break
        out.append(max((t - started).total_seconds() / 3600.0, 0.0))
    return tuple(out)


async def _sourdough_prediction(
    db: AsyncSession,
    batch: Batch,
    organisms: list,
    enzymes: dict[uuid.UUID, list[str]],
    started: datetime,
    now_h: float,
    finished: bool,
) -> PredictionOut:
    plan = plan_from_dict(batch.sourdough_plan or {})
    culture = batch.culture
    style = culture.style or plan.style
    style_names = set(STYLES[plan.style].organisms)
    extra = tuple(o.name for o, src, _ in organisms if src != "default" and o.name not in style_names)
    compiled_names = compile_plan(plan, extra).organisms
    priors = await population.learned_priors(
        db, compiled_names, ferment_type="sourdough", style=style, baker=culture.owner_id,
        starter=culture.id, exclude_batch=batch.id if finished else None,
    )
    inputs = BakeInputs(
        plan=plan_to_dict(plan),
        now_h=now_h,
        measurements=tuple(
            (m.type, (_utc(m.measured_at) - started).total_seconds() / 3600.0, m.value_numeric)
            for m in sorted(batch.measurements, key=lambda m: m.measured_at)
            if m.value_numeric is not None
        ),
        known_bounds=_known_bounds(batch, started),
        organisms=tuple(
            OrganismIn(o.name, o.kingdom, tuple(sorted(enzymes.get(o.id, []))))
            for o, *_ in organisms
        ),
        extra_organisms=extra,
        population_priors=priors,
        finished=finished,
    )
    try:
        body = await run_in_threadpool(bake_forecast, plan, inputs)
    except PredictionUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    if finished and batch.population_pooled_at is None and body.get("status") == "calibrated":
        await _learn(db, batch, "sourdough", style, evidence_for(inputs.fingerprint()))
    body["started_at"] = started
    body["now_h"] = round(now_h, 3)
    return PredictionOut.model_validate(body)


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

    culture = batch.culture
    if culture.type == "sourdough" and batch.sourdough_plan:
        return await _sourdough_prediction(
            db, batch, organisms, enzymes, started, now_h, finished
        )

    # Learned priors (prediction/population.py): this starter's, its style's and its
    # baker's evidence from finished batches, resolved here (service.py stays DB-free).
    style = culture.style or culture.type
    population_priors = await population.learned_priors(
        db, [o.name for o, *_ in organisms], ferment_type=culture.type, style=style,
        baker=culture.owner_id, starter=culture.id, exclude_batch=batch.id if finished else None,
    )

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

    # Learn only from a batch that actually calibrated: "prior_only" (no usable readings)
    # has no posterior to learn from. The claim (compare-and-swap on population_pooled_at)
    # makes two concurrent requests for the same finished batch record it once.
    if finished and batch.population_pooled_at is None and body.get("status") == "calibrated":
        await _learn(db, batch, culture.type, style, population_samples(inputs))

    # cached outputs are keyed per hour: report the exact start and "now"
    body["started_at"] = started
    body["now_h"] = round(now_h, 3)
    return PredictionOut.model_validate(body)
