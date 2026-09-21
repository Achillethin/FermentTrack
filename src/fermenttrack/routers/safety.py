from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fermenttrack.database import get_db
from fermenttrack.models import Batch
from fermenttrack.safety.service import get_safety_report
from fermenttrack.schemas import RuleVerdictOut, SafetyReportOut

router = APIRouter(prefix="/batches", tags=["safety"])


@router.get("/{batch_id}/safety", response_model=SafetyReportOut)
async def get_batch_safety(batch_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> SafetyReportOut:
    result = await db.execute(
        select(Batch)
        .where(Batch.id == batch_id)
        .options(selectinload(Batch.measurements), selectinload(Batch.culture))
    )
    batch = result.scalar_one_or_none()
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")

    report = get_safety_report(batch)
    return SafetyReportOut(
        safe=report.safe,
        hard_stops=[RuleVerdictOut(**vars(v)) for v in report.hard_stops],
        warnings=[RuleVerdictOut(**vars(v)) for v in report.warnings],
        rules_evaluated=report.rules_evaluated,
        rules_triggered=report.rules_triggered,
        summary_en=report.summary_en,
        summary_fr=report.summary_fr,
    )
