"""Pydantic v2 request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict


# ── Culture ──────────────────────────────────────────────────────────────

class CultureCreate(BaseModel):
    name: str
    type: str = "kombucha"
    born_from: uuid.UUID | None = None
    status: str = "active"


class CultureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    type: str
    born_from: uuid.UUID | None
    status: str
    created_at: datetime


class CultureWithBatches(CultureOut):
    batches: list["BatchOut"] = []


# ── Batch ────────────────────────────────────────────────────────────────

class BatchCreate(BaseModel):
    culture_id: uuid.UUID
    target: str | None = None


class BatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    culture_id: uuid.UUID
    started_at: datetime
    current_stage: str
    stage_entered_at: datetime
    target: str | None
    outcome: str
    ended_at: datetime | None


class StageAdvance(BaseModel):
    """Optional explicit target stage; if omitted, advances to the next stage."""

    stage: str | None = None


# ── Measurement ──────────────────────────────────────────────────────────

class MeasurementCreate(BaseModel):
    type: str
    value_numeric: float | None = None
    value_text: str | None = None
    notes: str | None = None


class MeasurementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    batch_id: uuid.UUID
    measured_at: datetime
    type: str
    value_numeric: float | None
    value_text: str | None
    notes: str | None


# ── Note ─────────────────────────────────────────────────────────────────

class NoteCreate(BaseModel):
    text: str


# ── Reminder ─────────────────────────────────────────────────────────────

class ReminderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    batch_id: uuid.UUID
    action: str
    due_at: datetime
    repeat_interval: timedelta | None
    urgency: str
    completed_at: datetime | None


class ReminderSnooze(BaseModel):
    until: datetime


# ── Timeline / compare ──────────────────────────────────────────────────

class TimelineEvent(BaseModel):
    kind: str  # "measurement" | "note" | "stage_change"
    timestamp: datetime
    detail: dict


class BatchTimeline(BaseModel):
    batch: BatchOut
    events: list[TimelineEvent]


class BatchCompare(BaseModel):
    batches: list[BatchOut]
    measurements: dict[str, list[MeasurementOut]]


CultureWithBatches.model_rebuild()
