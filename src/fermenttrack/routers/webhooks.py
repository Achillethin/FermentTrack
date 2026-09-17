"""iSpindel webhook (docs/README.md MVP scope bullet: 'iSpindel/GravityMon webhook').

Standard iSpindel HTTP POST payload — see https://www.ispindel.de. Kept
minimal: no auth beyond what's already in the app, no retry/queueing infra.
The target batch is identified by a `batch_id` query param since iSpindel
devices have no native concept of a FermentTrack batch (device registry /
per-device pairing is future-scope, not part of this MVP).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.database import get_db
from fermenttrack.models import Batch, Measurement
from fermenttrack.schemas import MeasurementOut

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class ISpindelPayload(BaseModel):
    """Standard iSpindel JSON payload fields relevant to FermentTrack."""

    name: str | None = None
    ID: int | None = None
    angle: float | None = None
    temperature: float | None = None
    temp_units: str | None = None
    gravity: float | None = None
    battery: float | None = None
    RSSI: float | None = None


@router.post("/ispindel", response_model=list[MeasurementOut], status_code=201)
async def ispindel_webhook(
    payload: ISpindelPayload,
    batch_id: uuid.UUID = Query(..., description="FermentTrack batch to attach readings to"),
    db: AsyncSession = Depends(get_db),
) -> list[Measurement]:
    batch = await db.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")

    created: list[Measurement] = []
    if payload.gravity is not None:
        created.append(Measurement(batch_id=batch.id, type="gravity", value_numeric=payload.gravity))
    if payload.temperature is not None:
        created.append(
            Measurement(batch_id=batch.id, type="temperature", value_numeric=payload.temperature)
        )
    if payload.battery is not None:
        created.append(
            Measurement(
                batch_id=batch.id,
                type="battery",
                value_numeric=payload.battery,
                notes="iSpindel battery voltage",
            )
        )

    if not created:
        raise HTTPException(status_code=422, detail="No recognized measurement fields in payload")

    db.add_all(created)
    await db.commit()
    for m in created:
        await db.refresh(m)
    return created
