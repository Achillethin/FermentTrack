from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fermenttrack.auth import get_current_user_id
from fermenttrack.database import get_db
from fermenttrack.models import Culture
from fermenttrack.schemas import CultureCreate, CultureOut, CultureWithBatches

router = APIRouter(prefix="/cultures", tags=["cultures"])


@router.post("", response_model=CultureOut, status_code=201)
async def create_culture(
    payload: CultureCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> Culture:
    if payload.born_from is not None:
        # lineage only within your own starters: never a link into another account
        parent = await db.get(Culture, payload.born_from)
        if parent is None or parent.owner_id != user_id:
            raise HTTPException(status_code=404, detail="Parent culture not found")
    culture = Culture(**payload.model_dump(), owner_id=user_id)
    db.add(culture)
    await db.commit()
    await db.refresh(culture)
    return culture


@router.get("", response_model=list[CultureOut])
async def list_cultures(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> list[Culture]:
    result = await db.execute(select(Culture).where(Culture.owner_id == user_id))
    return list(result.scalars().all())


@router.get("/{culture_id}", response_model=CultureWithBatches)
async def get_culture(
    culture_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> Culture:
    result = await db.execute(
        select(Culture)
        .where(Culture.id == culture_id, Culture.owner_id == user_id)
        .options(selectinload(Culture.batches))
    )
    culture = result.scalar_one_or_none()
    if culture is None:
        raise HTTPException(status_code=404, detail="Culture not found")
    return culture
