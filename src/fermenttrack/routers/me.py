"""Per-account data export and delete (GDPR: right to access / right to erasure).

No FermentTrack users table — Culture.owner_id (the Supabase JWT `sub`) is the
only row that carries the account boundary; everything else hangs off Culture
via cascading relationships (models.py).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fermenttrack.auth import get_current_user_id
from fermenttrack.database import get_db
from fermenttrack.models import Batch, Culture
from fermenttrack.schemas import CultureExportOut

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/export", response_model=list[CultureExportOut])
async def export_my_data(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> list[Culture]:
    result = await db.execute(
        select(Culture)
        .where(Culture.owner_id == user_id)
        .options(selectinload(Culture.batches).selectinload(Batch.measurements))
    )
    return list(result.scalars().unique().all())


@router.delete("", status_code=204)
async def delete_my_data(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> None:
    result = await db.execute(select(Culture).where(Culture.owner_id == user_id))
    for culture in result.scalars().all():
        await db.delete(culture)  # cascades to batches and everything under them
    await db.commit()
