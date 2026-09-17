"""Reminder computation on stage transitions."""

from __future__ import annotations

from datetime import datetime, timezone

from fermenttrack.models import Batch, Reminder
from fermenttrack.stages import get_stage


def build_reminder_for_stage(batch: Batch, stage_name: str, entered_at: datetime) -> Reminder | None:
    """Compute the next Reminder for a batch entering `stage_name`.

    due_at = stage entry + expected_duration. Returns None for stages with
    no timer (e.g. terminal "ready" stage).
    """
    stage = get_stage(stage_name)
    if stage.expected_duration is None or stage.reminder_action is None:
        return None
    return Reminder(
        batch_id=batch.id,
        action=stage.reminder_action,
        due_at=entered_at + stage.expected_duration,
        urgency=stage.urgency,
    )


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
