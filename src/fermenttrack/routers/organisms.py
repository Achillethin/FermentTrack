from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.database import get_db
from fermenttrack.models import Organism
from fermenttrack.schemas import OrganismOut

router = APIRouter(prefix="/organisms", tags=["organisms"])


@router.get("", response_model=list[OrganismOut])
async def search_organisms(
    q: str = Query(..., min_length=2),
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[Organism]:
    stmt = (
        select(Organism)
        .where(func.lower(Organism.name).contains(q.lower(), autoescape=True))
        .order_by(func.length(Organism.name), Organism.name)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
