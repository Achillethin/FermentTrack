from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fermenttrack.database import get_db
from fermenttrack.models import Culture
from fermenttrack.schemas import CultureCreate, CultureOut, CultureWithBatches

router = APIRouter(prefix="/cultures", tags=["cultures"])


@router.post("", response_model=CultureOut, status_code=201)
async def create_culture(payload: CultureCreate, db: AsyncSession = Depends(get_db)) -> Culture:
    culture = Culture(**payload.model_dump())
    db.add(culture)
    await db.commit()
    await db.refresh(culture)
    return culture


@router.get("", response_model=list[CultureOut])
async def list_cultures(db: AsyncSession = Depends(get_db)) -> list[Culture]:
    result = await db.execute(select(Culture))
    return list(result.scalars().all())


@router.get("/{culture_id}", response_model=CultureWithBatches)
async def get_culture(culture_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Culture:
    result = await db.execute(
        select(Culture).where(Culture.id == culture_id).options(selectinload(Culture.batches))
    )
    culture = result.scalar_one_or_none()
    if culture is None:
        raise HTTPException(status_code=404, detail="Culture not found")
    return culture
