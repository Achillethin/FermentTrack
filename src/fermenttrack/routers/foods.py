"""Search the frozen USDA FDC catalog."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.database import get_db
from fermenttrack.models import FdcFood
from fermenttrack.schemas import FdcFoodOut

router = APIRouter(prefix="/foods", tags=["foods"])


@router.get("", response_model=list[FdcFoodOut])
async def search_foods(
    q: str = Query(min_length=2, description="Every whitespace-separated word must appear"),
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> list[FdcFood]:
    tokens = q.lower().split()
    if not tokens:
        return []
    stmt = select(FdcFood)
    for token in tokens:
        stmt = stmt.where(func.lower(FdcFood.description).contains(token, autoescape=True))
    stmt = stmt.order_by(func.length(FdcFood.description), FdcFood.description).limit(limit)
    return list((await db.execute(stmt)).scalars().all())
