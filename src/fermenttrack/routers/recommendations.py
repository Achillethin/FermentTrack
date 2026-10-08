"""The recommender's API (design §§ 5, 10.1, 11.2).

- POST /recommendations: Proven cards from the precomputed grid (Experimental arrives with
  B7; `experimental` and `both` return the Proven section with a note).
- POST /recommendations/forecast: one card at a slider temperature, from a live 64-member
  forecast (stateless; sourdough answers with its planner link).
- POST /batches/from-recommendation: Start batch, in one transaction (culture, batch,
  ingredients, reminders, recommendation_links). Sourdough starts in the planner: 409.

All three need a signed-in user (anonymous sessions included); the library itself is public
(GET /recipes). Model runs and the first grid load are CPU-bound: they run in the threadpool.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from fermenttrack.auth import get_current_user_id
from fermenttrack.database import get_db
from fermenttrack.models import (
    SAFETY_REMINDER,
    Batch,
    BatchIngredient,
    Culture,
    Ingredient,
    RecommendationLink,
    Reminder,
)
from fermenttrack.prediction.service import PredictionUnavailable
from fermenttrack.recommender import gate, run, service
from fermenttrack.reminders import build_reminder_for_stage, now_utc
from fermenttrack.schemas import (
    BatchOut,
    CultureOut,
    FromRecommendationIn,
    FromRecommendationOut,
    RecommendationForecastIn,
    RecommendationForecastOut,
    RecommendationLinkOut,
    RecommendationRequest,
    RecommendationsOut,
    ReminderOut,
)
from fermenttrack.stages import first_stage

router = APIRouter(tags=["recommendations"])
logger = logging.getLogger(__name__)

PH_REMINDER_AFTER = timedelta(hours=48)
PH_REMINDER = f"{gate.PH_LOG_LINE} {gate.PH_DEADLINE_LINE}"  # the card's own lines, verbatim


def _cannot_run(exc: run.RecipeError) -> HTTPException:
    """A library recipe the engine cannot run (an invalid schedule, a levain build that is not
    one starter, flour and water row) is a library bug, never the request's: the user's
    temperature is bounded and clamped (service.resolve_temperature) before it reaches a
    schedule."""
    logger.error("library recipe cannot be run: %s", exc)
    return HTTPException(status_code=500, detail=f"This library recipe cannot be run: {exc}")


@router.post("/recommendations", response_model=RecommendationsOut)
async def recommend(
    payload: RecommendationRequest,
    user_id: str = Depends(get_current_user_id),
) -> RecommendationsOut:
    try:
        body = await run_in_threadpool(
            service.recommend, payload.ingredients, payload.aromas, payload.tastes,
            payload.mode, payload.temperature_c, payload.batch_g,
        )  # fmt: skip
    except run.RecipeError as exc:
        raise _cannot_run(exc) from None
    return RecommendationsOut.model_validate(body)


@router.post("/recommendations/forecast", response_model=RecommendationForecastOut)
async def forecast(
    payload: RecommendationForecastIn,
    user_id: str = Depends(get_current_user_id),
) -> RecommendationForecastOut:
    try:
        body = await run_in_threadpool(
            service.forecast, payload.recipe_key, payload.aromas, payload.tastes,
            payload.temperature_c, payload.batch_g,
        )  # fmt: skip
    except service.UnknownRecipe as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except service.GateRefused as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except PredictionUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    except run.RecipeError as exc:
        raise _cannot_run(exc) from None
    return RecommendationForecastOut.model_validate(body)


async def _culture(
    db: AsyncSession, payload: FromRecommendationIn, user_id: str, ferment_type: str, name: str
) -> Culture:
    if payload.culture_id is None:
        culture = Culture(name=payload.culture_name or name, type=ferment_type, owner_id=user_id)
        db.add(culture)
        await db.flush()
        return culture
    found = await db.get(Culture, payload.culture_id)
    if found is None or found.owner_id != user_id:
        raise HTTPException(status_code=404, detail="Culture not found")
    if found.type != ferment_type:
        raise HTTPException(
            status_code=422, detail=f"this recipe needs a {ferment_type} culture, not {found.type}"
        )
    return found


@router.post(
    "/batches/from-recommendation", response_model=FromRecommendationOut, status_code=201
)
async def start_batch(
    payload: FromRecommendationIn,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user_id: str = Depends(get_current_user_id),
) -> FromRecommendationOut:
    try:
        recipe = service.active_recipe(payload.recipe_key)
    except service.UnknownRecipe as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    try:
        if recipe.handoff == "planner":  # Q31: the planner creates sourdough batches
            served = service.resolve_temperature(recipe, payload.temperature_c).served_c
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Sourdough starts in the levain planner.",
                    "handoff": "planner",
                    "planner_link": service.planner_link(recipe, served, payload.batch_g),
                },
            )
        plan = await run_in_threadpool(
            service.batch_plan, recipe.key, payload.aromas, payload.tastes,
            payload.temperature_c, payload.batch_g, payload.mode,
        )  # fmt: skip
    except service.GateRefused as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except run.RecipeError as exc:
        raise _cannot_run(exc) from None

    names = sorted({name for name, _, _ in plan.rows})
    found = await db.execute(
        select(Ingredient)
        .where(Ingredient.name.in_(names), Ingredient.is_active.is_(True))
        .order_by(Ingredient.id)
    )
    by_name: dict[str, Ingredient] = {}
    for ingredient in found.scalars():
        by_name.setdefault(ingredient.name, ingredient)
    missing = [n for n in names if n not in by_name]
    if missing:  # a catalogue name the database lacks: migrations not applied
        raise HTTPException(
            status_code=503,
            detail=f"The ingredient catalogue is missing {', '.join(missing)}: run migrations.",
        )

    culture = await _culture(db, payload, user_id, recipe.fermentation_type, recipe.name)
    started = now_utc()
    stage = first_stage(culture.type)
    batch = Batch(
        culture_id=culture.id, started_at=started, current_stage=stage, stage_entered_at=started,
        expected_temperature_c=plan.expected_temperature_c,
    )  # fmt: skip
    db.add(batch)
    await db.flush()
    db.add_all(
        BatchIngredient(
            batch_id=batch.id, ingredient_id=by_name[name].id, quantity=grams, unit="g",
            role=role,
        )
        for name, grams, role in plan.rows
    )  # fmt: skip
    reminders = [r for r in (build_reminder_for_stage(batch, culture.type, stage, started),) if r]
    if plan.ph_reminder:  # a safety reminder: a stage change does not close it
        reminders.append(
            Reminder(
                batch_id=batch.id, action=PH_REMINDER, due_at=started + PH_REMINDER_AFTER,
                urgency="critical", kind=SAFETY_REMINDER,
            )
        )  # fmt: skip
    db.add_all(reminders)
    link = RecommendationLink(batch_id=batch.id, **plan.link)
    db.add(link)
    await db.commit()
    for row in (batch, culture, link, *reminders):
        await db.refresh(row)
    return FromRecommendationOut(
        batch=BatchOut.model_validate(batch),
        culture=CultureOut.model_validate(culture),
        link=RecommendationLinkOut.model_validate(link),
        reminders=[ReminderOut.model_validate(r) for r in reminders],
        skipped_ingredients=list(plan.skipped),
    )
