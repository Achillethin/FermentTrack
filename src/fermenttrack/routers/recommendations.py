"""The recommender's API (design §§ 5, 10.1, 11.2).

- POST /recommendations: Proven cards from the precomputed grid, and Experimental variants
  (mode experimental or both): from the grid, screened, or live for a variant of one of your
  batches (parent_batch_id, Q16) or of an approved community recipe (community_recipe_id);
  and the "Community — not proven" section (mode proven or both, design § 10.3): approved
  community recipes from their stored forecasts (recommender.community).
- POST /recommendations/forecast: one card at a slider temperature, from a live 64-member
  forecast (stateless; sourdough answers with its planner link). With operators: the
  variant's live forecast, the confirmation of a screened card ("interaction detected"). A
  community card (community_recipe_id) runs its own live forecast.
- POST /batches/from-recommendation: Start batch, in one transaction (culture, batch,
  ingredients, reminders, recommendation_links). Sourdough starts in the planner: 409. A
  variant is recomputed here from its operators; its USDA foods are booked like a USDA pick. A
  community card (community_recipe_id, no operators) is booked from its stored forecasts
  (live when they are not of the current grid); its link carries community_recipe_id, and a
  variant of your batch's carries parent_batch_id.
- POST /recommendations/deep-search ("search deeper", design § 10.2): queues a background job
  of up to 20 live forecasts (recommender.jobs) and answers 202 {job_id}; 200 with your
  finished job of the same request (its results are kept); 409 with the job id while you have
  one queued or running. A parent_batch_id is refused (422): your batch's variants already run
  live. GET /recommendations/jobs/{job_id} polls it (yours only, 404 otherwise); GET
  /recommendations/jobs lists yours (your data, as DELETE /me erases it): your 10 newest, the
  older ones being deleted as you start new ones.

All of them need a signed-in user (anonymous sessions included); the library itself is public
(GET /recipes). A parent batch must be the user's own (404 otherwise); a community recipe must
be approved (404 otherwise). Model runs and the first grid load are CPU-bound: they run in the
threadpool.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.concurrency import run_in_threadpool

from fermenttrack.auth import get_current_user_id
from fermenttrack.composition import to_grams
from fermenttrack.database import get_db
from fermenttrack.models import (
    SAFETY_REMINDER,
    Batch,
    BatchIngredient,
    Culture,
    Ingredient,
    RecommendationJob,
    RecommendationLink,
    Reminder,
)
from fermenttrack.prediction.service import PredictionUnavailable
from fermenttrack.recommender import community, gate, jobs, run, service
from fermenttrack.reminders import build_reminder_for_stage, now_utc
from fermenttrack.routers.batches import _get_batch, _ingredient_for_fdc_food
from fermenttrack.routers.community import approved_candidate, approved_candidates
from fermenttrack.schemas import (
    BatchOut,
    CultureOut,
    DeepSearchOut,
    FromRecommendationIn,
    FromRecommendationOut,
    OperatorIn,
    RecommendationForecastIn,
    RecommendationForecastOut,
    RecommendationJobOut,
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


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)  # SQLite drops the zone


async def _own_parent(db: AsyncSession, batch_id: uuid.UUID, user_id: str) -> service.Parent:
    """One of the user's batches as an Experimental parent (Q16): 404 unless it is theirs; 422
    for a type the Experimental mode does not take. A row of a retired ingredient is kept
    without a mass, exactly like a row without a quantity or with an unknown unit: it never
    disappears from the batch's total, so the salt gate fails closed (salt % unknown) instead
    of reading a higher salt % from the remaining rows, and it is neither run nor booked."""
    batch = await _get_batch(
        batch_id, db, user_id=user_id, with_measurements=True, with_culture=True
    )
    found = await db.execute(
        select(BatchIngredient)
        .where(BatchIngredient.batch_id == batch.id)
        .options(selectinload(BatchIngredient.ingredient).selectinload(Ingredient.nutrients))
    )
    rows = sorted(
        (
            service.OwnBatchRow(
                bi.ingredient.name,
                to_grams(bi.quantity, bi.unit) if bi.ingredient.is_active else None,
                bi.role,
                tuple(sorted((n.nutrient, n.amount_per_100g) for n in bi.ingredient.nutrients)),
            )
            for bi in found.scalars()
        ),
        key=lambda r: (r.name, r.grams or 0.0, r.role),
    )  # fmt: skip
    siblings = await db.execute(
        select(Batch.id, Batch.started_at).where(Batch.culture_id == batch.culture_id)
    )
    order = sorted(siblings.all(), key=lambda b: (_utc(b.started_at), str(b.id)))
    readings = [
        m.value_numeric for m in batch.measurements
        if m.type == "temperature" and m.value_numeric is not None
    ]  # fmt: skip
    finished = batch.outcome != "in_progress" and batch.ended_at is not None
    own = service.OwnBatch(
        batch_id=str(batch.id),
        number=1 + [b.id for b in order].index(batch.id),
        culture_name=batch.culture.name,
        fermentation_type=batch.culture.type,
        rows=tuple(rows),
        temperature_c=sum(readings) / len(readings) if readings else batch.expected_temperature_c,
        duration_h=(
            (_utc(batch.ended_at) - _utc(batch.started_at)).total_seconds() / 3600.0
            if finished and batch.ended_at is not None else None
        ),
    )  # fmt: skip
    try:
        return service.own_parent(own)
    except service.RecommendationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


def _requests(ops: list[OperatorIn]) -> tuple[service.OperatorRequest, ...]:
    return tuple(
        service.OperatorRequest(o.op, o.ingredient, o.replaces, o.to_c, o.fdc_id) for o in ops
    )


@router.post("/recommendations", response_model=RecommendationsOut)
async def recommend(
    payload: RecommendationRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user_id: str = Depends(get_current_user_id),
) -> RecommendationsOut:
    own = None
    if payload.parent_batch_id is not None:
        own = await _own_parent(db, payload.parent_batch_id, user_id)
    elif payload.community_recipe_id is not None:
        own = community.parent(await approved_candidate(db, payload.community_recipe_id))
    try:
        body = await run_in_threadpool(
            service.recommend, payload.ingredients, payload.aromas, payload.tastes,
            payload.mode, payload.temperature_c, payload.batch_g, payload.usda_fdc_ids, own,
        )  # fmt: skip
        if payload.mode in ("proven", "both"):
            candidates = await approved_candidates(db, payload.ingredients)
            body["community"] = await run_in_threadpool(
                community.section, candidates, payload.ingredients, payload.aromas,
                payload.tastes, payload.temperature_c, payload.batch_g,
            )  # fmt: skip
    except PredictionUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    except run.RecipeError as exc:
        raise _cannot_run(exc) from None
    return RecommendationsOut.model_validate(body)


@router.post("/recommendations/forecast", response_model=RecommendationForecastOut)
async def forecast(
    payload: RecommendationForecastIn,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user_id: str = Depends(get_current_user_id),
) -> RecommendationForecastOut:
    own = None
    shared = None  # a community card (no operators): its own live forecast
    if payload.parent_batch_id is not None:
        own = await _own_parent(db, payload.parent_batch_id, user_id)
    elif payload.community_recipe_id is not None:
        found = await approved_candidate(db, payload.community_recipe_id)
        own, shared = (community.parent(found), None) if payload.operators else (None, found)
    try:
        body = await run_in_threadpool(
            lambda: community.forecast(
                shared, payload.aromas, payload.tastes, payload.temperature_c
            ) if shared is not None else service.forecast(
                payload.recipe_key, payload.aromas, payload.tastes, payload.temperature_c,
                payload.batch_g, ops=_requests(payload.operators), own=own,
            )
        )  # fmt: skip
    except service.UnknownRecipe as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except service.RecommendationError as exc:  # GateRefused, OperatorRefused
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
    ops = _requests(payload.operators)
    own = None
    shared = None  # a community card (no operators): booked from its own forecasts
    if payload.parent_batch_id is not None:
        own = await _own_parent(db, payload.parent_batch_id, user_id)
    elif payload.community_recipe_id is not None:
        picked = await approved_candidate(db, payload.community_recipe_id)
        own, shared = (community.parent(picked), None) if ops else (None, picked)
    else:
        try:
            service.active_recipe(payload.recipe_key or "")
        except service.UnknownRecipe as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
    try:
        handoff = None if own or shared else service.planner_handoff(
            payload.recipe_key, payload.temperature_c, payload.batch_g, ops
        )  # fmt: skip
        if handoff is not None:  # Q31: the planner creates sourdough batches
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Sourdough starts in the levain planner.",
                    "handoff": "planner",
                    "planner_link": handoff,
                },
            )
        plan = await run_in_threadpool(
            lambda: community.batch_plan(
                shared, payload.aromas, payload.tastes, payload.temperature_c, payload.batch_g,
                payload.mode,
            ) if shared is not None else service.batch_plan(
                payload.recipe_key, payload.aromas, payload.tastes, payload.temperature_c,
                payload.batch_g, payload.mode, ops=ops, own=own,
            )
        )  # fmt: skip
    except service.RecommendationError as exc:  # GateRefused, OperatorRefused
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except PredictionUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
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

    ferment_type = plan.card.recipe.fermentation_type
    culture = await _culture(db, payload, user_id, ferment_type, plan.name)
    usda = [
        (await _ingredient_for_fdc_food(db, fdc_id, ferment_type, role), grams, role)
        for fdc_id, grams, role in plan.fdc_rows
    ]  # operator (v): found or created like a USDA pick (404 if the food is unknown)
    started = now_utc()
    stage = first_stage(culture.type)
    batch = Batch(
        culture_id=culture.id, started_at=started, current_stage=stage, stage_entered_at=started,
        expected_temperature_c=plan.expected_temperature_c,
    )  # fmt: skip
    db.add(batch)
    await db.flush()
    booked = [(by_name[name], grams, role) for name, grams, role in plan.rows] + usda
    db.add_all(
        BatchIngredient(
            batch_id=batch.id, ingredient_id=ingredient.id, quantity=grams, unit="g", role=role
        )
        for ingredient, grams, role in booked
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


# ── search deeper: background jobs (design § 10.2) ──────────────────────


def _busy(job: RecommendationJob) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "message": "You already have a search running: its results come in as it goes.",
            "job_id": str(job.id),
        },
    )


@router.post(
    "/recommendations/deep-search",
    response_model=DeepSearchOut,
    status_code=202,
    responses={
        200: {"model": DeepSearchOut, "description": "Your finished job of the same request"},
        409: {"description": "You already have a queued or running job (detail.job_id)"},
    },
)
async def deep_search(
    payload: RecommendationRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user_id: str = Depends(get_current_user_id),
) -> DeepSearchOut:
    if payload.parent_batch_id is not None or payload.community_recipe_id is not None:
        raise HTTPException(
            status_code=422,
            detail="Search deeper explores the library's recipes; your batch's or a community "
            "recipe's variants already run live in POST /recommendations.",
        )
    request = payload.model_dump(mode="json", exclude={"community_recipe_id"})
    fingerprint = await run_in_threadpool(jobs.deep_search_fingerprint, request)
    done = await jobs.find_done(db, user_id, jobs.DEEP_SEARCH, fingerprint)
    if done is not None:
        response.status_code = 200
        return DeepSearchOut(job_id=done.id, status="done")
    active = await jobs.find_active(db, user_id)
    if active is not None:
        raise _busy(active)
    try:
        job = await jobs.submit(
            db, jobs.DEEP_SEARCH, request, fingerprint=fingerprint, owner_id=user_id
        )
    except IntegrityError:  # a concurrent request of yours queued one first
        active = await jobs.find_active(db, user_id)
        if active is None:
            raise
        raise _busy(active) from None
    return DeepSearchOut(job_id=job.id, status="queued")


async def _job_out(db: AsyncSession, job: RecommendationJob) -> RecommendationJobOut:
    return RecommendationJobOut.model_validate({
        "job_id": job.id, "status": job.status, "done": job.done, "total": job.total,
        "eta_s": await jobs.eta_s(db, job), "results": [r["card"] for r in job.results],
        "error": job.error, "request": job.request, "created_at": job.created_at,
        "started_at": job.started_at, "finished_at": job.finished_at,
    })  # fmt: skip


@router.get("/recommendations/jobs", response_model=list[RecommendationJobOut])
async def my_jobs(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user_id: str = Depends(get_current_user_id),
) -> list[RecommendationJobOut]:
    """Your deep searches, newest first: what you asked and what came back (the newest
    JOBS_KEPT, every one kept)."""
    found = await db.execute(
        select(RecommendationJob)
        .where(RecommendationJob.owner_id == user_id, RecommendationJob.kind == jobs.DEEP_SEARCH)
        .order_by(RecommendationJob.created_at.desc(), RecommendationJob.id)
        .limit(jobs.JOBS_KEPT)
    )
    return [await _job_out(db, job) for job in found.scalars()]


@router.get("/recommendations/jobs/{job_id}", response_model=RecommendationJobOut)
async def get_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user_id: str = Depends(get_current_user_id),
) -> RecommendationJobOut:
    job = await db.get(RecommendationJob, job_id)
    if job is None or job.owner_id != user_id or job.kind != jobs.DEEP_SEARCH:
        raise HTTPException(status_code=404, detail="Job not found")
    return await _job_out(db, job)
