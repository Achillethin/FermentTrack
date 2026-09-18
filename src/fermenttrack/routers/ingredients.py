from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.database import get_db
from fermenttrack.models import Ingredient
from fermenttrack.schemas import IngredientOut

router = APIRouter(prefix="/ingredients", tags=["ingredients"])


@router.get("", response_model=list[IngredientOut])
async def list_ingredients(db: AsyncSession = Depends(get_db)) -> list[Ingredient]:
    result = await db.execute(select(Ingredient).where(Ingredient.is_active.is_(True)))
    return list(result.scalars().all())
