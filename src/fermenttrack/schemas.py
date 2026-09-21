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


# ── Ingredient ───────────────────────────────────────────────────────────

class IngredientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    canonical_id: str | None
    name: str
    default_role: str
    fermentation_systems: list[str]
    is_active: bool


# ── BatchIngredient ──────────────────────────────────────────────────────

class BatchIngredientCreate(BaseModel):
    ingredient_id: uuid.UUID
    quantity: float | None = None
    unit: str | None = None
    role: str | None = None  # if omitted, copied from Ingredient.default_role


class BatchIngredientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    batch_id: uuid.UUID
    ingredient_id: uuid.UUID
    quantity: float | None
    unit: str | None
    role: str


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


# ── Safety ───────────────────────────────────────────────────────────────
# Moved here from routers/safety.py so routers/batches.py's preview endpoint
# can reuse the same response shape without importing another router module.

class RuleVerdictOut(BaseModel):
    rule_id: str
    triggered: bool
    action: str
    reason_code: str
    reason_text_en: str
    reason_text_fr: str
    source_citation: str


class SafetyReportOut(BaseModel):
    safe: bool
    hard_stops: list[RuleVerdictOut]
    warnings: list[RuleVerdictOut]
    rules_evaluated: int
    rules_triggered: int
    summary_en: str
    summary_fr: str


# ── Preview ──────────────────────────────────────────────────────────────
# Presentation-shaped for the (future) batch-preview UI page. Scope ceiling:
# owned by that one page's needs — any other consumer uses /timeline and
# /safety directly rather than extending this. No compound/microbial data
# here by design (see docs/superpowers/specs/2026-09-18-experiment-logging-
# design.md § 2 — deferred until FermentGraph's ranker clears its promotion
# bar, to avoid presenting unvalidated heuristics as a current feature).

class BatchPreview(BaseModel):
    batch: BatchOut
    culture: CultureOut
    days_in_stage: float
    recipe: list[BatchIngredientOut]
    timeline: list[TimelineEvent]
    safety: SafetyReportOut


CultureWithBatches.model_rebuild()
