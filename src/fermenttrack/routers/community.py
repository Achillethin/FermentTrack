"""Community recipes' API (design § 10.3; recommender.community holds the rules).

- POST /community-recipes {batch_id, title, pseudonym}: publish one of your finished batches
  (404 for someone else's). Every automatic check of § 10.3 runs (422 with every reason); a
  batch already published and not rejected is a 409 (a partial unique index settles two
  simultaneous publishes). The recipe is then pending. The response
  carries the privacy notice: the recipe stays in the library if you delete your account,
  detached from you (DELETE /me). Anonymous accounts may publish. Your own published recipes,
  every status, are listed by GET /me/community-recipes (routers/me.py), the export path.
- GET /admin/community-recipes?status=pending, POST /admin/community-recipes/{id}/approve and
  /reject {reason}: the review queue, admins only (auth.require_admin,
  FERMENTTRACK_ADMIN_USER_IDS). Reviewing is moderation of the shared library, the one thing
  an admin changes: it never touches an account's own data. Approval enqueues the recipe's
  forecast job (recommender.community; approving again re-queues one that failed); a
  rejection needs its reason. Each item shows the recipe's newest forecast job (`forecast_job`:
  status, error, progress).

The helpers below read approved recipes for routers/recommendations.py: its community section,
a community recipe as an Experimental parent, its slider and Start batch.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import distinct, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.concurrency import run_in_threadpool

from fermenttrack.auth import get_current_user_id, require_admin
from fermenttrack.database import get_db
from fermenttrack.models import (
    COMMUNITY_APPROVED,
    COMMUNITY_PENDING,
    COMMUNITY_REJECTED,
    Batch,
    BatchIngredient,
    CommunityRecipe,
    CommunityRecipeForecast,
    Culture,
    Ingredient,
    RecommendationJob,
    RecommendationLink,
)
from fermenttrack.recommender import community, grid, service
from fermenttrack.reminders import now_utc
from fermenttrack.routers.batches import _get_batch
from fermenttrack.schemas import (
    AdminCommunityRecipeOut,
    CommunityPublishIn,
    CommunityPublishOut,
    CommunityReviewIn,
    CommunityStatus,
)

router = APIRouter(tags=["community"])
ALREADY_PUBLISHED = "This batch is already published."


def recipe_out(row: CommunityRecipe) -> dict[str, Any]:
    """schemas.CommunityRecipeOut's fields."""
    return {
        "id": row.id, "title": row.title, "pseudonym": row.pseudonym,
        "fermentation_type": row.fermentation_type,
        "ingredients": [
            {
                "name": r["name"], "role": r["role"], "g_per_kg": r["g_per_kg"],
                "fdc_id": r.get("fdc_id"),
                "label": community.USDA_LABEL if r.get("fdc_id") is not None else None,
            }
            for r in row.recipe
        ],
        "temperature_c": row.temperature_c, "duration_h": row.duration_h, "status": row.status,
        "reason": row.reason, "created_at": row.created_at, "reviewed_at": row.reviewed_at,
    }  # fmt: skip


def _admin_out(row: CommunityRecipe, job: RecommendationJob | None) -> AdminCommunityRecipeOut:
    """The admin's view: the owner, the source batch, the reviewer and the newest forecast
    job (its status and error)."""
    forecast_job = None if job is None else {
        "id": job.id, "status": job.status, "error": job.error, "done": job.done,
        "total": job.total, "finished_at": job.finished_at,
    }  # fmt: skip
    return AdminCommunityRecipeOut.model_validate(
        recipe_out(row) | {
            "owner_id": row.owner_id, "source_batch_id": row.source_batch_id,
            "reviewed_by": row.reviewed_by, "forecast_job": forecast_job,
        }
    )  # fmt: skip


async def _admin_list(
    db: AsyncSession, rows: list[CommunityRecipe]
) -> list[AdminCommunityRecipeOut]:
    latest = await community.latest_jobs(db, [r.id for r in rows])
    return [_admin_out(r, latest.get(r.id)) for r in rows]


@router.post("/community-recipes", response_model=CommunityPublishOut, status_code=201)
async def publish(
    payload: CommunityPublishIn,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user_id: str = Depends(get_current_user_id),
) -> CommunityPublishOut:
    batch = await _get_batch(
        payload.batch_id, db, user_id=user_id, with_measurements=True, with_culture=True
    )
    found = await db.execute(
        select(BatchIngredient)
        .where(BatchIngredient.batch_id == batch.id)
        .options(selectinload(BatchIngredient.ingredient).selectinload(Ingredient.nutrients))
    )
    rows = sorted(
        (
            community.LoggedRow(
                bi.ingredient.name, bi.quantity, bi.unit, bi.role, bi.ingredient.is_active,
                bi.ingredient.fdc_id,
                tuple(sorted((n.nutrient, n.amount_per_100g) for n in bi.ingredient.nutrients)),
            )
            for bi in found.scalars()
        ),
        key=lambda r: (r.name, r.role, r.quantity or 0.0, r.unit or ""),
    )  # fmt: skip
    readings = [
        (m.type.lower(), m.measured_at, m.value_numeric)
        for m in batch.measurements if m.value_numeric is not None
    ]  # fmt: skip
    source = community.SourceBatch(
        fermentation_type=batch.culture.type, rows=tuple(rows),
        temperatures=tuple((at, v) for t, at, v in readings if t == "temperature"),
        expected_temperature_c=batch.expected_temperature_c,
        ph=tuple((at, v) for t, at, v in readings if t == "ph"),
        started_at=batch.started_at, ended_at=batch.ended_at, outcome=batch.outcome,
    )  # fmt: skip
    if await _published(db, batch.id):
        raise HTTPException(status_code=409, detail=ALREADY_PUBLISHED)
    try:
        draft = community.draft(source)
    except community.PublishRefused as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": "This batch cannot be published yet.", "reasons": list(exc.reasons)},
        ) from None
    row = CommunityRecipe(
        owner_id=user_id, source_batch_id=batch.id, pseudonym=payload.pseudonym,
        title=payload.title, fermentation_type=draft.fermentation_type, recipe=list(draft.rows),
        temperature_c=draft.temperature_c, duration_h=draft.duration_h,
        status=COMMUNITY_PENDING, created_at=now_utc(),
    )  # fmt: skip
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:  # a simultaneous publish of the same batch won the unique index
        await db.rollback()
        raise HTTPException(status_code=409, detail=ALREADY_PUBLISHED) from None
    await db.refresh(row)
    notice = {"notice": community.PRIVACY_NOTICE}
    return CommunityPublishOut.model_validate(recipe_out(row) | notice)


async def _published(db: AsyncSession, batch_id: uuid.UUID) -> bool:
    """The batch is published and not rejected (uq_community_recipes_source_batch holds it on
    a race)."""
    found = await db.execute(
        select(CommunityRecipe.id)
        .where(
            CommunityRecipe.source_batch_id == batch_id,
            CommunityRecipe.status != COMMUNITY_REJECTED,
        )
        .limit(1)
    )
    return found.scalar_one_or_none() is not None


# ── the review queue (admins) ───────────────────────────────────────────


@router.get("/admin/community-recipes", response_model=list[AdminCommunityRecipeOut])
async def review_queue(
    status: CommunityStatus = "pending",  # a query parameter
    db: AsyncSession = Depends(get_db),  # noqa: B008
    admin_id: str = Depends(require_admin),
) -> list[AdminCommunityRecipeOut]:
    found = await db.execute(
        select(CommunityRecipe)
        .where(CommunityRecipe.status == status)
        .order_by(CommunityRecipe.created_at, CommunityRecipe.id)
    )
    return await _admin_list(db, list(found.scalars()))


async def _reviewed(db: AsyncSession, recipe_id: uuid.UUID) -> CommunityRecipe:
    row = await db.get(CommunityRecipe, recipe_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Community recipe not found")
    return row


@router.post("/admin/community-recipes/{recipe_id}/approve", response_model=AdminCommunityRecipeOut)
async def approve(
    recipe_id: uuid.UUID,
    payload: CommunityReviewIn | None = None,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    admin_id: str = Depends(require_admin),
) -> AdminCommunityRecipeOut:
    """Approve, and queue the recipe's forecasts (one job; none while one is queued or
    running). A recipe no model temperature passes the gate for is a 409 (no forecast)."""
    row = await _reviewed(db, recipe_id)
    recipe = community.candidate(community.stored(row)).recipe
    if not await run_in_threadpool(community.forecast_temperatures, recipe):
        raise HTTPException(
            status_code=409, detail="No model temperature passes the safety checks for it."
        )
    row.status, row.reviewed_at, row.reviewed_by = COMMUNITY_APPROVED, now_utc(), admin_id
    row.reason = payload.reason if payload else None
    await community.enqueue(db, row, await run_in_threadpool(grid.version))  # commits
    await db.refresh(row)
    return (await _admin_list(db, [row]))[0]


@router.post("/admin/community-recipes/{recipe_id}/reject", response_model=AdminCommunityRecipeOut)
async def reject(
    recipe_id: uuid.UUID,
    payload: CommunityReviewIn,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    admin_id: str = Depends(require_admin),
) -> AdminCommunityRecipeOut:
    """Reject, with the reason its author reads (GET /me/community-recipes); an approved
    recipe leaves the community section."""
    if not payload.reason:
        raise HTTPException(status_code=422, detail="A rejection needs its reason.")
    row = await _reviewed(db, recipe_id)
    row.status, row.reviewed_at, row.reviewed_by = COMMUNITY_REJECTED, now_utc(), admin_id
    row.reason = payload.reason
    await db.commit()
    await db.refresh(row)
    return (await _admin_list(db, [row]))[0]


# ── approved recipes, for routers/recommendations.py ────────────────────


async def _forecasts_and_made(
    db: AsyncSession, ids: Sequence[uuid.UUID]
) -> tuple[dict[uuid.UUID, list[CommunityRecipeForecast]], dict[uuid.UUID, int]]:
    """Per recipe: its forecasts of the current grid version, and "made n×": the distinct
    people (culture owners) who started a batch from it or a variant of it, its author
    excluded."""
    current = await run_in_threadpool(grid.version)
    found = await db.execute(
        select(CommunityRecipeForecast)
        .where(
            CommunityRecipeForecast.recipe_id.in_(ids),
            CommunityRecipeForecast.grid_version == current,
        )
        .order_by(CommunityRecipeForecast.recipe_id, CommunityRecipeForecast.temp_c)
    )
    forecasts: dict[uuid.UUID, list[CommunityRecipeForecast]] = {}
    for f in found.scalars():
        forecasts.setdefault(f.recipe_id, []).append(f)
    counted = await db.execute(
        select(RecommendationLink.community_recipe_id, func.count(distinct(Culture.owner_id)))
        .join(Batch, Batch.id == RecommendationLink.batch_id)
        .join(Culture, Culture.id == Batch.culture_id)
        .join(CommunityRecipe, CommunityRecipe.id == RecommendationLink.community_recipe_id)
        .where(
            RecommendationLink.community_recipe_id.in_(ids),
            or_(CommunityRecipe.owner_id.is_(None), Culture.owner_id != CommunityRecipe.owner_id),
        )
        .group_by(RecommendationLink.community_recipe_id)
    )
    made = {rid: int(n) for rid, n in counted.tuples() if rid is not None}
    return forecasts, made


def _holds(row: CommunityRecipe, must: set[str]) -> bool:
    try:
        return must <= {str(i["name"]) for i in row.recipe}
    except Exception:  # unreadable: community.candidates logs it and leaves it out
        return True


async def approved_candidates(
    db: AsyncSession, listed: Sequence[str]
) -> list[community.Candidate]:
    """The approved recipes holding every must-include ingredient, with their current
    forecasts and "made n×" (the community section). One that cannot be read is logged and
    left out."""
    must = set(service.must_include(listed))
    found = await db.execute(
        select(CommunityRecipe)
        .where(CommunityRecipe.status == COMMUNITY_APPROVED)
        .order_by(CommunityRecipe.created_at, CommunityRecipe.id)
    )
    rows = [r for r in found.scalars() if _holds(r, must)]
    if not rows:
        return []
    forecasts, made = await _forecasts_and_made(db, [r.id for r in rows])
    stored = [community.stored(r, forecasts.get(r.id, ()), made.get(r.id, 0)) for r in rows]
    return await run_in_threadpool(community.candidates, stored)


async def approved_candidate(db: AsyncSession, recipe_id: uuid.UUID) -> community.Candidate:
    """One approved recipe (404 otherwise: pending, rejected or unknown)."""
    row = await db.get(CommunityRecipe, recipe_id)
    if row is None or row.status != COMMUNITY_APPROVED:
        raise HTTPException(status_code=404, detail="Community recipe not found")
    forecasts, made = await _forecasts_and_made(db, [row.id])
    s = community.stored(row, forecasts.get(row.id, ()), made.get(row.id, 0))
    return await run_in_threadpool(community.candidate, s)
