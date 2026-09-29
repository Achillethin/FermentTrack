"""Sourdough planner: the style/flour catalogue, a stateless bake-plan forecast and the
feeding chart. Design: docs/superpowers/specs/2026-09-28-sourdough-engine-design.md § 7.

Compute is CPU-bound numpy, so it runs in the threadpool; results are cached in
prediction.bake. A `culture_id` (the caller's own starter) brings in its learned kinetics.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from fermenttrack.auth import get_current_user_id
from fermenttrack.database import get_db
from fermenttrack.models import Culture
from fermenttrack.prediction import population
from fermenttrack.prediction.bake import BakeInputs, feeding_chart, forecast
from fermenttrack.prediction.priors import Prior
from fermenttrack.prediction.service import PredictionUnavailable
from fermenttrack.prediction.sourdough import (
    FLOURS,
    STYLES,
    blend,
    plan_from_dict,
    plan_to_dict,
    style_organisms,
)
from fermenttrack.schemas import FeedingChartIn, FeedingChartOut, PredictionOut, SourdoughPlanIn

router = APIRouter(prefix="/sourdough", tags=["sourdough"])


@router.get("/catalog")
async def catalog(user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    return {
        "styles": [
            {
                "key": s.key,
                "name": s.name,
                "native_name": s.native_name,
                "type": s.type,
                "seed": s.seed,
                "description": s.description,
                "organisms": style_organisms(s, False),
                "defaults": {
                    "hydration_pct": s.hydration_pct,
                    "seed_ratio": s.seed_ratio,
                    "temperature_c": s.temperature_c,
                    "flour": s.flour,
                    "hours": s.hours,
                },
                "notes": list(s.notes),
                "sources": list(s.sources),
            }
            for s in STYLES.values()
        ],
        "flours": [
            {
                "key": f.key,
                "name": f.name,
                "us_name": f.us_name,
                "grain": f.grain,
                "ash_pct": f.ash_pct,
                "protein_pct": f.protein_pct,
            }
            for f in FLOURS.values()
        ],
    }


async def starter_priors(
    db: AsyncSession, user_id: str, culture_id: uuid.UUID | None, style: str, organisms: list[str]
) -> dict[str, dict[str, Prior]]:
    """Learned priors for a plan: the caller's own starter if named (404 otherwise), else
    this baker and the style's class (a new starter's general default)."""
    starter = None
    if culture_id is not None:
        culture = (
            await db.execute(
                select(Culture).where(Culture.id == culture_id, Culture.owner_id == user_id)
            )
        ).scalar_one_or_none()
        if culture is None:
            raise HTTPException(status_code=404, detail="Culture not found")
        starter = culture.id
        style = culture.style or style
    return await population.learned_priors(
        db, organisms, ferment_type="sourdough", style=style, baker=user_id, starter=starter
    )


@router.post("/plan", response_model=PredictionOut)
async def plan_forecast(
    payload: SourdoughPlanIn,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user_id: str = Depends(get_current_user_id),
) -> PredictionOut:
    d = payload.model_dump(mode="json", exclude={"culture_id"})
    plan = plan_from_dict(d)
    style = STYLES[plan.style]
    organisms = style_organisms(style, bool(plan.dough and plan.dough.yeast_g > 0))
    priors = await starter_priors(db, user_id, payload.culture_id, plan.style, organisms)
    inputs = BakeInputs(plan=plan_to_dict(plan), population_priors=priors)
    try:
        body = await run_in_threadpool(forecast, plan, inputs)
    except PredictionUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    body["started_at"] = datetime.now(UTC)
    return PredictionOut.model_validate(body)


@router.post("/feeding-chart", response_model=FeedingChartOut)
async def feeding_chart_endpoint(
    payload: FeedingChartIn,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user_id: str = Depends(get_current_user_id),
) -> FeedingChartOut:
    style = STYLES.get(payload.style)
    if style is None or style.seed != "starter":
        raise HTTPException(status_code=422, detail="the feeding chart needs a starter style")
    try:
        flour = blend(payload.flour or style.flour)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    priors = await starter_priors(
        db, user_id, payload.culture_id, style.key, style_organisms(style, False)
    )
    body = await run_in_threadpool(
        feeding_chart, style.key, flour, payload.hydration_pct, payload.temperature_c,
        payload.starter, tuple(sorted(set(payload.ratios))), priors,
    )  # fmt: skip
    return FeedingChartOut.model_validate(body)
