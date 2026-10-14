"""The recipe library, public and read-only (design Q17): GET /recipes and GET /recipes/{key}."""

from __future__ import annotations

from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from fermenttrack.recommender import library
from fermenttrack.recommender.library import Recipe
from fermenttrack.schemas import RecipeOut

router = APIRouter(prefix="/recipes", tags=["recipes"])

_ENVELOPE = ("temp_c", "duration_h", "salt_pct", "sugar_g_per_kg", "temp_schedule")


def recipe_out(recipe: Recipe) -> RecipeOut:
    body = asdict(recipe)
    envelope = {k: body.pop(k) for k in _ENVELOPE} | {"basis": body.pop("envelope_basis")}
    return RecipeOut.model_validate(
        body | {"envelope": envelope, "labels": library.trust_labels(recipe)}
    )


@router.get("", response_model=list[RecipeOut])
async def list_recipes(
    type_: str | None = Query(
        default=None, alias="type", description="A fermentation type, e.g. 'kombucha'"
    ),
    status: Literal["active", "draft"] = Query(
        default="active", description="Draft recipes are library data, never recommended"
    ),
) -> list[RecipeOut]:
    return [
        recipe_out(r)
        for r in library.load_library().values()
        if r.status == status and (type_ is None or r.fermentation_type == type_)
    ]


@router.get("/{key}", response_model=RecipeOut)
async def get_recipe(key: str) -> RecipeOut:
    recipe = library.get(key)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe_out(recipe)
