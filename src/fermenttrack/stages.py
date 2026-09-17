"""Kombucha stage state machine (docs/ARCHITECTURE.md § Stage State Machines).

brew_sweet_tea -> 1F (7-14 days) -> 2F_flavoring (2-4 days) -> bottling
              -> conditioning (2-5 days) -> ready

Only kombucha is in MVP scope; other ferment types (sourdough, koji, cheese)
are documented in ARCHITECTURE.md but not implemented here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True)
class StageDef:
    name: str
    next_stage: str | None
    expected_duration: timedelta | None  # None = no timer-based reminder (e.g. terminal stage)
    reminder_action: str | None
    urgency: str  # low | medium | high | critical


# Ordered kombucha stage progression. Bottling carries the over-carbonation /
# glass-explosion risk called out in ARCHITECTURE.md -> critical urgency.
KOMBUCHA_STAGES: dict[str, StageDef] = {
    "brew_sweet_tea": StageDef(
        name="brew_sweet_tea",
        next_stage="1F",
        expected_duration=timedelta(hours=1),
        reminder_action="cool tea to room temp, add SCOBY, start 1F",
        urgency="low",
    ),
    "1F": StageDef(
        name="1F",
        next_stage="2F_flavoring",
        expected_duration=timedelta(days=10),  # midpoint of 7-14 day range
        reminder_action="taste test — check for readiness to move to 2F",
        urgency="medium",
    ),
    "2F_flavoring": StageDef(
        name="2F_flavoring",
        next_stage="bottling",
        expected_duration=timedelta(days=3),  # midpoint of 2-4 day range
        reminder_action="check carbonation before bottling",
        urgency="medium",
    ),
    "bottling": StageDef(
        name="bottling",
        next_stage="conditioning",
        expected_duration=timedelta(days=1),
        reminder_action="burp bottles — over-carbonation risk (glass explosion) after day 5",
        urgency="critical",
    ),
    "conditioning": StageDef(
        name="conditioning",
        next_stage="ready",
        expected_duration=timedelta(days=3),  # midpoint of 2-5 day range
        reminder_action="check conditioning progress, move to fridge when ready",
        urgency="high",
    ),
    "ready": StageDef(
        name="ready",
        next_stage=None,
        expected_duration=None,
        reminder_action=None,
        urgency="low",
    ),
}

STAGE_ORDER = ["brew_sweet_tea", "1F", "2F_flavoring", "bottling", "conditioning", "ready"]


class InvalidStageError(ValueError):
    pass


def get_stage(name: str) -> StageDef:
    try:
        return KOMBUCHA_STAGES[name]
    except KeyError:
        raise InvalidStageError(f"Unknown kombucha stage: {name!r}") from None


def next_stage_name(current: str) -> str | None:
    return get_stage(current).next_stage
