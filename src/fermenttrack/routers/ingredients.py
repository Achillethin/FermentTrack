from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.database import get_db
from fermenttrack.models import Ingredient
from fermenttrack.schemas import IngredientOut

router = APIRouter(prefix="/ingredients", tags=["ingredients"])


@router.get("", response_model=list[IngredientOut])
async def list_ingredients(
    substrate: str | None = Query(
        default=None, description="Filter to a fermentation_systems entry, e.g. 'kombucha'"
    ),
    include_retired: bool = Query(
        default=False, description="Also return retired rows (to label historical recipes)"
    ),
    db: AsyncSession = Depends(get_db),
) -> list[Ingredient]:
    stmt = select(Ingredient)
    if not include_retired:
        stmt = stmt.where(Ingredient.is_active.is_(True))
    result = await db.execute(stmt)
    ingredients = list(result.scalars().all())
    if substrate is not None:
        # fermentation_systems is a JSON list column — filtered in Python
        # rather than a DB-side JSON contains() to stay portable across the
        # Postgres/SQLite split this project already runs on (see database.py).
        ingredients = [i for i in ingredients if substrate in i.fermentation_systems]
    return ingredients
