from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.auth import get_current_user_id
from fermenttrack.database import get_db
from fermenttrack.routers.batches import _get_batch
from fermenttrack.safety.service import get_safety_report
from fermenttrack.schemas import RuleVerdictOut, SafetyReportOut

router = APIRouter(prefix="/batches", tags=["safety"])


@router.get("/{batch_id}/safety", response_model=SafetyReportOut)
async def get_batch_safety(
    batch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> SafetyReportOut:
    batch = await _get_batch(
        batch_id, db, user_id=user_id, with_measurements=True, with_culture=True
    )

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
