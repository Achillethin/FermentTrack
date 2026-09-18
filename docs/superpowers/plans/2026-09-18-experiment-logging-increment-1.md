# Experiment Logging — Increment 1 (Domain Model) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generalize FermentTrack's stage state machine beyond kombucha (add sourdough, koji, cheese) and add `Ingredient`/`BatchIngredient` recipe logging, seeded with reference data across all documented substrates.

**Architecture:** Extends the existing FastAPI + SQLAlchemy 2.0 (async) + Alembic stack. `stages.py` becomes a substrate-keyed registry instead of a single kombucha dict; two new tables (`ingredients`, `batch_ingredients`) are added via an Alembic migration that also seeds 20 reference ingredients; two new endpoints expose ingredient reference data and per-batch recipe logging.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async ORM, Pydantic v2, Alembic, pytest + pytest-asyncio + httpx (existing test stack, SQLite in-memory for tests via `tests/conftest.py`).

**Spec:** `docs/superpowers/specs/2026-09-18-experiment-logging-design.md` (revision 2) — sections "1. Domain Model Additions" (Ingredient/BatchIngredient + seed data + stage machine generalization). This plan covers Increment 1 only — the `GET /batches/{id}/preview` endpoint (Increment 2) and the frontend (Increment 3) are separate plans, written after this one ships.

## Global Constraints

- No new external dependencies — everything here uses packages already in `pyproject.toml`.
- `role` on `BatchIngredient` is copied from `Ingredient.default_role` **at insert time only**, never re-derived — a later edit to `Ingredient.default_role` must not change historical batches' displayed role.
- `Ingredient.canonical_id` stays `None` for all seed rows — it's only populated later if/when the deferred FermentGraph export lands (out of scope here, see spec's "Deferred" section).
- Kefir, miso, and vinegar get `Ingredient`/`BatchIngredient` support but **no stage machine** — batches for those substrates use a single `"in_progress"` pseudo-stage with no reminder automation. Do not build stage progression for them in this plan.
- Follow existing patterns exactly: `from __future__ import annotations` at the top of every module, async SQLAlchemy 2.0 style (`Mapped`/`mapped_column`), Pydantic v2 (`ConfigDict(from_attributes=True)` on every `*Out` schema), one router per resource under `src/fermenttrack/routers/`.

---

## Task 1: Generalize stage machines beyond kombucha

**Files:**
- Modify: `src/fermenttrack/stages.py` (full rewrite — currently 88 lines, kombucha-only)
- Test: `tests/test_stages.py` (new file)

**Interfaces:**
- Produces: `StageDef` (unchanged shape), `STAGE_MACHINES: dict[str, dict[str, StageDef]]`, `STAGE_ORDER: dict[str, list[str]]`, `get_stage(substrate: str, name: str) -> StageDef`, `next_stage_name(substrate: str, current: str) -> str | None`, `first_stage(substrate: str) -> str`, `InvalidStageError`. Task 2 consumes all of these with the new two-argument signatures.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_stages.py`:

```python
"""Multi-substrate stage machine tests (docs/ARCHITECTURE.md § Stage State Machines)."""

from __future__ import annotations

import pytest

from fermenttrack.stages import (
    InvalidStageError,
    first_stage,
    get_stage,
    next_stage_name,
)


def test_kombucha_progression_unchanged() -> None:
    assert first_stage("kombucha") == "brew_sweet_tea"
    assert next_stage_name("kombucha", "brew_sweet_tea") == "1F"
    assert next_stage_name("kombucha", "bottling") == "conditioning"
    assert next_stage_name("kombucha", "ready") is None


def test_sourdough_progression() -> None:
    assert first_stage("sourdough") == "feed_starter"
    assert next_stage_name("sourdough", "feed_starter") == "bulk_ferment"
    assert next_stage_name("sourdough", "bulk_ferment") == "shape"
    assert next_stage_name("sourdough", "shape") == "cold_retard"
    assert next_stage_name("sourdough", "cold_retard") == "bake"
    assert next_stage_name("sourdough", "bake") == "done"
    assert next_stage_name("sourdough", "done") is None


def test_koji_progression() -> None:
    assert first_stage("koji") == "soak"
    order = ["soak", "steam", "inoculate", "incubate", "harvest", "done"]
    for current, expected_next in zip(order, order[1:] + [None]):
        assert next_stage_name("koji", current) == expected_next


def test_cheese_progression() -> None:
    assert first_stage("cheese") == "heat_milk"
    order = ["heat_milk", "culture", "rennet", "cut_curd", "cook", "press", "salt", "age", "ready"]
    for current, expected_next in zip(order, order[1:] + [None]):
        assert next_stage_name("cheese", current) == expected_next


def test_substrate_without_stage_machine_uses_in_progress_pseudo_stage() -> None:
    assert first_stage("kefir") == "in_progress"
    assert next_stage_name("kefir", "in_progress") is None
    stage = get_stage("kefir", "in_progress")
    assert stage.reminder_action is None
    assert stage.expected_duration is None


def test_invalid_stage_name_within_known_machine_raises() -> None:
    with pytest.raises(InvalidStageError):
        get_stage("kombucha", "bogus_stage")


def test_invalid_stage_name_for_no_machine_substrate_raises() -> None:
    with pytest.raises(InvalidStageError):
        get_stage("kefir", "bogus_stage")


def test_bottling_is_critical_urgency() -> None:
    assert get_stage("kombucha", "bottling").urgency == "critical"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_stages.py -v`
Expected: FAIL with `ModuleNotFoundError` or `ImportError` — `first_stage` doesn't exist yet, and `get_stage`/`next_stage_name` still take one argument, not two.

- [ ] **Step 3: Rewrite `src/fermenttrack/stages.py`**

```python
"""Multi-substrate stage state machines (docs/ARCHITECTURE.md § Stage State Machines).

Kombucha: brew_sweet_tea -> 1F (7-14 days) -> 2F_flavoring (2-4 days) -> bottling
          -> conditioning (2-5 days) -> ready
Sourdough: feed_starter -> bulk_ferment (4-12h) -> shape -> cold_retard (8-24h)
           -> bake -> done
Koji: soak -> steam -> inoculate -> incubate (36-48h) -> harvest -> done
Cheese: heat_milk -> culture -> rennet -> cut_curd -> cook -> press -> salt
        -> age -> ready

Kefir, miso, and vinegar have Ingredient/BatchIngredient recipe-logging
support (see models.py) but no stage machine here yet. Batches for those
substrates get a single "in_progress" pseudo-stage with no reminder
automation until a real state machine is documented for them.
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


# Bottling carries the over-carbonation / glass-explosion risk called out in
# ARCHITECTURE.md -> critical urgency.
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

SOURDOUGH_STAGES: dict[str, StageDef] = {
    "feed_starter": StageDef(
        name="feed_starter",
        next_stage="bulk_ferment",
        expected_duration=timedelta(hours=1),
        reminder_action="starter fed — watch for peak activity before mixing dough",
        urgency="low",
    ),
    "bulk_ferment": StageDef(
        name="bulk_ferment",
        next_stage="shape",
        expected_duration=timedelta(hours=8),  # midpoint of 4-12h range
        reminder_action="check dough rise — shape when doubled",
        urgency="medium",
    ),
    "shape": StageDef(
        name="shape",
        next_stage="cold_retard",
        expected_duration=timedelta(hours=1),
        reminder_action="dough shaped — move to fridge for cold retard",
        urgency="low",
    ),
    "cold_retard": StageDef(
        name="cold_retard",
        next_stage="bake",
        expected_duration=timedelta(hours=16),  # midpoint of 8-24h range
        reminder_action="cold retard complete — preheat oven and bake",
        urgency="medium",
    ),
    "bake": StageDef(
        name="bake",
        next_stage="done",
        expected_duration=timedelta(minutes=45),
        reminder_action="check internal temp / crust color — pull when done",
        urgency="high",
    ),
    "done": StageDef(
        name="done",
        next_stage=None,
        expected_duration=None,
        reminder_action=None,
        urgency="low",
    ),
}

KOJI_STAGES: dict[str, StageDef] = {
    "soak": StageDef(
        name="soak",
        next_stage="steam",
        expected_duration=timedelta(hours=8),
        reminder_action="soak complete — drain and steam",
        urgency="low",
    ),
    "steam": StageDef(
        name="steam",
        next_stage="inoculate",
        expected_duration=timedelta(hours=1),
        reminder_action="steaming complete — cool to inoculation temp and add spores",
        urgency="medium",
    ),
    "inoculate": StageDef(
        name="inoculate",
        next_stage="incubate",
        expected_duration=timedelta(hours=1),
        reminder_action="spores mixed in — move to incubation",
        urgency="low",
    ),
    "incubate": StageDef(
        name="incubate",
        next_stage="harvest",
        expected_duration=timedelta(hours=42),  # midpoint of 36-48h range
        reminder_action="check for even white mycelium coverage — harvest when ready",
        urgency="high",
    ),
    "harvest": StageDef(
        name="harvest",
        next_stage="done",
        expected_duration=timedelta(hours=1),
        reminder_action="koji harvested — cool and use or store",
        urgency="medium",
    ),
    "done": StageDef(
        name="done",
        next_stage=None,
        expected_duration=None,
        reminder_action=None,
        urgency="low",
    ),
}

CHEESE_STAGES: dict[str, StageDef] = {
    "heat_milk": StageDef(
        name="heat_milk",
        next_stage="culture",
        expected_duration=timedelta(minutes=30),
        reminder_action="milk at temp — add starter culture",
        urgency="low",
    ),
    "culture": StageDef(
        name="culture",
        next_stage="rennet",
        expected_duration=timedelta(hours=1),
        reminder_action="culture ripening complete — add rennet",
        urgency="medium",
    ),
    "rennet": StageDef(
        name="rennet",
        next_stage="cut_curd",
        expected_duration=timedelta(hours=1),
        reminder_action="check for clean break — cut the curd",
        urgency="medium",
    ),
    "cut_curd": StageDef(
        name="cut_curd",
        next_stage="cook",
        expected_duration=timedelta(minutes=15),
        reminder_action="curd cut — begin cooking",
        urgency="low",
    ),
    "cook": StageDef(
        name="cook",
        next_stage="press",
        expected_duration=timedelta(hours=1),
        reminder_action="cooking complete — drain whey and press",
        urgency="medium",
    ),
    "press": StageDef(
        name="press",
        next_stage="salt",
        expected_duration=timedelta(hours=6),
        reminder_action="pressing complete — salt or brine the cheese",
        urgency="medium",
    ),
    "salt": StageDef(
        name="salt",
        next_stage="age",
        expected_duration=timedelta(hours=12),
        reminder_action="salting complete — move to aging",
        urgency="low",
    ),
    "age": StageDef(
        name="age",
        next_stage="ready",
        expected_duration=timedelta(days=14),
        reminder_action="check rind development and turn the wheel",
        urgency="medium",
    ),
    "ready": StageDef(
        name="ready",
        next_stage=None,
        expected_duration=None,
        reminder_action=None,
        urgency="low",
    ),
}

STAGE_MACHINES: dict[str, dict[str, StageDef]] = {
    "kombucha": KOMBUCHA_STAGES,
    "sourdough": SOURDOUGH_STAGES,
    "koji": KOJI_STAGES,
    "cheese": CHEESE_STAGES,
}

STAGE_ORDER: dict[str, list[str]] = {
    "kombucha": ["brew_sweet_tea", "1F", "2F_flavoring", "bottling", "conditioning", "ready"],
    "sourdough": ["feed_starter", "bulk_ferment", "shape", "cold_retard", "bake", "done"],
    "koji": ["soak", "steam", "inoculate", "incubate", "harvest", "done"],
    "cheese": ["heat_milk", "culture", "rennet", "cut_curd", "cook", "press", "salt", "age", "ready"],
}

# Pseudo-stage for substrates with no registered stage machine (kefir, miso,
# vinegar today, and any future substrate not yet documented in
# ARCHITECTURE.md). No reminder, no progression — recipe logging still
# works via Ingredient/BatchIngredient regardless.
_NO_MACHINE_STAGE = StageDef(
    name="in_progress",
    next_stage=None,
    expected_duration=None,
    reminder_action=None,
    urgency="low",
)


class InvalidStageError(ValueError):
    pass


def get_stage(substrate: str, name: str) -> StageDef:
    machine = STAGE_MACHINES.get(substrate)
    if machine is None:
        if name == _NO_MACHINE_STAGE.name:
            return _NO_MACHINE_STAGE
        raise InvalidStageError(
            f"Substrate {substrate!r} has no stage machine; only "
            f"{_NO_MACHINE_STAGE.name!r} is valid, got {name!r}"
        )
    try:
        return machine[name]
    except KeyError:
        raise InvalidStageError(f"Unknown {substrate} stage: {name!r}") from None


def next_stage_name(substrate: str, current: str) -> str | None:
    return get_stage(substrate, current).next_stage


def first_stage(substrate: str) -> str:
    order = STAGE_ORDER.get(substrate)
    return order[0] if order else _NO_MACHINE_STAGE.name
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_stages.py -v`
Expected: PASS, 8 tests.

- [ ] **Step 5: Commit**

```bash
git add src/fermenttrack/stages.py tests/test_stages.py
git commit -m "feat: generalize stage machines to sourdough, koji, cheese, no-machine fallback"
```

---

## Task 2: Wire substrate-awareness through reminders and the batches router

**Files:**
- Modify: `src/fermenttrack/reminders.py:11-25` (`build_reminder_for_stage` signature)
- Modify: `src/fermenttrack/routers/batches.py:1-113` (`_get_batch`, `create_batch`, `advance_stage`)
- Modify: `tests/test_cultures_batches.py` (add new tests, no changes to existing ones needed)

**Interfaces:**
- Consumes: `get_stage(substrate, name)`, `next_stage_name(substrate, current)`, `first_stage(substrate)`, `InvalidStageError` from Task 1.
- Produces: `build_reminder_for_stage(batch: Batch, substrate: str, stage_name: str, entered_at: datetime) -> Reminder | None` — Task 6 does not consume this, no downstream dependents beyond this task.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cultures_batches.py`:

```python
@pytest.mark.asyncio
async def test_sourdough_batch_uses_sourdough_stages(client: AsyncClient) -> None:
    culture = await _create_culture(client, name="My Levain")
    resp = await client.post("/cultures", json={"name": "My Levain", "type": "sourdough"})
    culture = resp.json()
    batch = await _create_batch(client, culture["id"])
    assert batch["current_stage"] == "feed_starter"

    resp = await client.patch(f"/batches/{batch['id']}/stage", json={})
    assert resp.status_code == 200
    assert resp.json()["current_stage"] == "bulk_ferment"


@pytest.mark.asyncio
async def test_kefir_batch_has_no_stage_machine(client: AsyncClient) -> None:
    resp = await client.post("/cultures", json={"name": "Water Kefir #1", "type": "kefir"})
    culture = resp.json()
    batch = await _create_batch(client, culture["id"])
    assert batch["current_stage"] == "in_progress"

    # No reminder should have been created — no expected_duration on the
    # no-machine pseudo-stage.
    resp = await client.get("/reminders")
    assert all(r["batch_id"] != batch["id"] for r in resp.json())

    # Advancing a substrate with no stage machine has nowhere to go.
    resp = await client.patch(f"/batches/{batch['id']}/stage", json={})
    assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cultures_batches.py -v -k "sourdough or kefir"`
Expected: FAIL — `create_batch` still calls the old single-argument `STAGE_ORDER[0]`/`build_reminder_for_stage`, so every batch starts at `"brew_sweet_tea"` regardless of substrate.

- [ ] **Step 3: Update `src/fermenttrack/reminders.py`**

Replace the whole file:

```python
"""Reminder computation on stage transitions."""

from __future__ import annotations

from datetime import datetime, timezone

from fermenttrack.models import Batch, Reminder
from fermenttrack.stages import get_stage


def build_reminder_for_stage(
    batch: Batch, substrate: str, stage_name: str, entered_at: datetime
) -> Reminder | None:
    """Compute the next Reminder for a batch entering `stage_name`.

    due_at = stage entry + expected_duration. Returns None for stages with
    no timer (e.g. terminal stages, or the no-machine "in_progress" stage).
    """
    stage = get_stage(substrate, stage_name)
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
```

- [ ] **Step 4: Update `src/fermenttrack/routers/batches.py`**

Replace the imports and the `_get_batch`/`create_batch`/`advance_stage` functions (lines 1-101 of the current file; the measurement/note/timeline/compare functions below are untouched):

```python
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fermenttrack.database import get_db
from fermenttrack.models import Batch, Culture, Measurement, Reminder
from fermenttrack.reminders import build_reminder_for_stage, now_utc
from fermenttrack.schemas import (
    BatchCompare,
    BatchCreate,
    BatchOut,
    BatchTimeline,
    MeasurementCreate,
    MeasurementOut,
    NoteCreate,
    StageAdvance,
    TimelineEvent,
)
from fermenttrack.stages import InvalidStageError, first_stage, next_stage_name

router = APIRouter(prefix="/batches", tags=["batches"])


async def _get_batch(
    batch_id: uuid.UUID,
    db: AsyncSession,
    *,
    with_measurements: bool = False,
    with_culture: bool = False,
) -> Batch:
    stmt = select(Batch).where(Batch.id == batch_id)
    if with_measurements:
        stmt = stmt.options(selectinload(Batch.measurements))
    if with_culture:
        stmt = stmt.options(selectinload(Batch.culture))
    result = await db.execute(stmt)
    batch = result.scalar_one_or_none()
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    return batch


@router.post("", response_model=BatchOut, status_code=201)
async def create_batch(payload: BatchCreate, db: AsyncSession = Depends(get_db)) -> Batch:
    culture = await db.get(Culture, payload.culture_id)
    if culture is None:
        raise HTTPException(status_code=404, detail="Culture not found")

    started_at = now_utc()
    initial_stage = first_stage(culture.type)
    batch = Batch(
        culture_id=payload.culture_id,
        started_at=started_at,
        current_stage=initial_stage,
        stage_entered_at=started_at,
        target=payload.target,
    )
    db.add(batch)
    await db.flush()

    reminder = build_reminder_for_stage(batch, culture.type, initial_stage, started_at)
    if reminder is not None:
        db.add(reminder)

    await db.commit()
    await db.refresh(batch)
    return batch


@router.patch("/{batch_id}/stage", response_model=BatchOut)
async def advance_stage(
    batch_id: uuid.UUID, payload: StageAdvance, db: AsyncSession = Depends(get_db)
) -> Batch:
    batch = await _get_batch(batch_id, db, with_culture=True)
    substrate = batch.culture.type

    try:
        target_stage = payload.stage or next_stage_name(substrate, batch.current_stage)
        if target_stage is None:
            raise HTTPException(status_code=400, detail="Batch is already at its final stage")
        entered_at = now_utc()
        # validates stage name
        reminder = build_reminder_for_stage(batch, substrate, target_stage, entered_at)
    except InvalidStageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    batch.current_stage = target_stage
    batch.stage_entered_at = entered_at
    if target_stage in ("ready", "done"):
        batch.outcome = "success"
        batch.ended_at = entered_at

    # Superseded by the new stage's reminder — mark prior open reminders done
    # rather than leaving stale ones (e.g. a past stage's timer) in the list.
    await db.execute(
        update(Reminder)
        .where(Reminder.batch_id == batch.id, Reminder.completed_at.is_(None))
        .values(completed_at=entered_at)
    )

    if reminder is not None:
        db.add(reminder)

    await db.commit()
    await db.refresh(batch)
    return batch
```

Note the terminal-outcome check changed from `target_stage == "ready"` to `target_stage in ("ready", "done")` — sourdough and koji terminate at `"done"`, not `"ready"`; kombucha and cheese still terminate at `"ready"`. This is the only behavioral change in the untouched-looking terminal-state logic.

Also add `culture: Mapped["Culture"] = relationship()` is NOT needed here — `Batch.culture` already exists via the existing `back_populates="batches"` relationship on `Culture` (see `src/fermenttrack/models.py:59`, `culture: Mapped["Culture"] = relationship(back_populates="batches")`) — `selectinload(Batch.culture)` in `_get_batch` works against that existing relationship with no model changes needed.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_cultures_batches.py -v`
Expected: PASS, all tests including the 2 new ones (existing kombucha tests must still pass unchanged — they don't set an explicit `type`, but `CultureCreate.type` defaults to `"kombucha"` per `schemas.py:15`, and `_create_culture`'s helper always passes `"type": "kombucha"` explicitly).

- [ ] **Step 6: Commit**

```bash
git add src/fermenttrack/reminders.py src/fermenttrack/routers/batches.py tests/test_cultures_batches.py
git commit -m "feat: route batch stage progression through substrate-aware stage machines"
```

---

## Task 3: `Ingredient` and `BatchIngredient` models + schemas

**Files:**
- Modify: `src/fermenttrack/models.py` (add two classes, extend `Batch`)
- Modify: `src/fermenttrack/schemas.py` (add four schema classes)
- Test: `tests/test_ingredients_model.py` (new file — model-level round-trip, no API yet)

**Interfaces:**
- Produces: `Ingredient` (SQLAlchemy model: `id, canonical_id, name, default_role, fermentation_systems, is_active`), `BatchIngredient` (SQLAlchemy model: `id, batch_id, ingredient_id, quantity, unit, role`), `IngredientOut`, `BatchIngredientCreate`, `BatchIngredientOut` (Pydantic). Tasks 5 and 6 consume these directly.

- [ ] **Step 1: Write the failing test**

Create `tests/test_ingredients_model.py`:

```python
"""Ingredient/BatchIngredient model round-trip (no API — see test_ingredients.py
and test_batch_ingredients.py in later tasks for the HTTP-level behavior)."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.models import Batch, BatchIngredient, Culture, Ingredient


@pytest.mark.asyncio
async def test_ingredient_round_trip(db_session: AsyncSession) -> None:
    ingredient = Ingredient(
        name="Black/green tea",
        default_role="base",
        fermentation_systems=["kombucha"],
    )
    db_session.add(ingredient)
    await db_session.commit()

    result = await db_session.execute(select(Ingredient).where(Ingredient.name == "Black/green tea"))
    fetched = result.scalar_one()
    assert fetched.default_role == "base"
    assert fetched.fermentation_systems == ["kombucha"]
    assert fetched.is_active is True
    assert fetched.canonical_id is None


@pytest.mark.asyncio
async def test_batch_ingredient_round_trip(db_session: AsyncSession) -> None:
    culture = Culture(name="Jun SCOBY", type="kombucha")
    db_session.add(culture)
    await db_session.flush()

    batch = Batch(culture_id=culture.id, current_stage="brew_sweet_tea")
    ingredient = Ingredient(name="Cane sugar", default_role="base", fermentation_systems=["kombucha"])
    db_session.add_all([batch, ingredient])
    await db_session.flush()

    batch_ingredient = BatchIngredient(
        batch_id=batch.id,
        ingredient_id=ingredient.id,
        quantity=100.0,
        unit="g",
        role="base",
    )
    db_session.add(batch_ingredient)
    await db_session.commit()

    result = await db_session.execute(
        select(BatchIngredient).where(BatchIngredient.batch_id == batch.id)
    )
    fetched = result.scalar_one()
    assert fetched.quantity == 100.0
    assert fetched.unit == "g"
    assert fetched.role == "base"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ingredients_model.py -v`
Expected: FAIL with `ImportError: cannot import name 'Ingredient' from 'fermenttrack.models'`.

- [ ] **Step 3: Add the models**

In `src/fermenttrack/models.py`, add `Boolean` and `JSON` to the existing `from sqlalchemy import ...` line (currently `from sqlalchemy import Float, ForeignKey, Interval, Text`, becomes `from sqlalchemy import Boolean, Float, ForeignKey, Interval, JSON, Text`), then append these two classes and extend `Batch`:

```python
class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    canonical_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    default_role: Mapped[str] = mapped_column(Text, nullable=False)  # base | starter | flavoring | additive
    fermentation_systems: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class BatchIngredient(Base):
    __tablename__ = "batch_ingredients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("batches.id"), nullable=False
    )
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingredients.id"), nullable=False
    )
    quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    # Copied from Ingredient.default_role AT INSERT TIME by the router (Task 6),
    # never re-derived — see Global Constraints.

    batch: Mapped["Batch"] = relationship(back_populates="batch_ingredients")
    ingredient: Mapped["Ingredient"] = relationship()
```

In the existing `Batch` class, add one relationship alongside `measurements`/`reminders`:

```python
    batch_ingredients: Mapped[list["BatchIngredient"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )
```

- [ ] **Step 4: Add the schemas**

In `src/fermenttrack/schemas.py`, append after the `Reminder` section (before `# ── Timeline / compare ──`):

```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_ingredients_model.py -v`
Expected: PASS, 2 tests.

- [ ] **Step 6: Run the full test suite to check for regressions**

Run: `pytest -q`
Expected: PASS, all prior tests still green (new `Base.metadata` tables don't affect existing model behavior).

- [ ] **Step 7: Commit**

```bash
git add src/fermenttrack/models.py src/fermenttrack/schemas.py tests/test_ingredients_model.py
git commit -m "feat: add Ingredient and BatchIngredient models and schemas"
```

---

## Task 4: Seed data module + Alembic migration

**Files:**
- Create: `src/fermenttrack/seed_data.py`
- Create: `alembic/versions/0002_ingredients.py`
- Test: `tests/test_seed_data.py` (new file — pure Python, no DB)

**Interfaces:**
- Consumes: nothing from prior tasks (pure data).
- Produces: `INGREDIENT_SEED_DATA: list[tuple[str, str, list[str]]]` (name, default_role, fermentation_systems) — consumed by the migration in this task; not consumed by later application code (it's a one-time seed, not a runtime lookup table).

- [ ] **Step 1: Write the failing test**

Create `tests/test_seed_data.py`:

```python
"""Seed data integrity — no DB needed, pure data checks."""

from __future__ import annotations

from fermenttrack.seed_data import INGREDIENT_SEED_DATA

VALID_ROLES = {"base", "starter", "flavoring", "additive"}


def test_seed_data_has_twenty_ingredients() -> None:
    assert len(INGREDIENT_SEED_DATA) == 20


def test_seed_data_names_are_unique() -> None:
    names = [name for name, _role, _systems in INGREDIENT_SEED_DATA]
    assert len(names) == len(set(names))


def test_seed_data_roles_are_valid() -> None:
    for name, role, _systems in INGREDIENT_SEED_DATA:
        assert role in VALID_ROLES, f"{name!r} has invalid role {role!r}"


def test_seed_data_every_ingredient_has_at_least_one_system() -> None:
    for name, _role, systems in INGREDIENT_SEED_DATA:
        assert len(systems) >= 1, f"{name!r} has no fermentation_systems"


def test_seed_data_covers_all_four_stage_machine_substrates() -> None:
    all_systems = {s for _name, _role, systems in INGREDIENT_SEED_DATA for s in systems}
    assert {"kombucha", "sourdough", "koji", "cheese"} <= all_systems
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_seed_data.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'fermenttrack.seed_data'`.

- [ ] **Step 3: Create `src/fermenttrack/seed_data.py`**

```python
"""Reference ingredient seed data (docs/superpowers/specs/2026-09-18-experiment-logging-design.md
§ 1, "Seed data — all documented substrates"). Single-sourced here so both the
Alembic migration (alembic/versions/0002_ingredients.py) and any future
re-seed tooling use the same list.
"""

from __future__ import annotations

# (name, default_role, fermentation_systems)
INGREDIENT_SEED_DATA: list[tuple[str, str, list[str]]] = [
    ("Black/green tea", "base", ["kombucha"]),
    ("Water", "base", ["kombucha", "sourdough"]),
    ("Cane sugar", "base", ["kombucha", "kefir"]),
    ("SCOBY / starter liquid", "starter", ["kombucha"]),
    ("Fresh ginger", "flavoring", ["kombucha", "kefir"]),
    ("Fruit", "flavoring", ["kombucha", "kefir"]),
    ("Herbs", "flavoring", ["kombucha", "kefir"]),
    ("Spices", "flavoring", ["kombucha", "kefir"]),
    ("Flour", "base", ["sourdough"]),
    ("Starter/levain", "starter", ["sourdough"]),
    ("Rice/grain/soybean", "base", ["koji", "miso"]),
    ("Koji spores (A. oryzae)", "starter", ["koji", "miso"]),
    ("Milk", "base", ["cheese", "kefir"]),
    ("Rennet", "starter", ["cheese"]),
    ("Starter/cheese culture", "starter", ["cheese"]),
    ("Kefir grains", "starter", ["kefir"]),
    ("Wine/cider/base alcohol", "base", ["vinegar"]),
    ("Mother of vinegar (Acetobacter)", "starter", ["vinegar"]),
    ("Salt", "additive", ["cheese", "koji", "miso", "sourdough"]),
    ("Calcium chloride", "additive", ["cheese"]),
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_seed_data.py -v`
Expected: PASS, 5 tests.

- [ ] **Step 5: Create the Alembic migration**

Create `alembic/versions/0002_ingredients.py`:

```python
"""ingredients and batch_ingredients — recipe logging

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-18

"""
from __future__ import annotations

import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from fermenttrack.seed_data import INGREDIENT_SEED_DATA

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    ingredients_table = op.create_table(
        "ingredients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("canonical_id", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("default_role", sa.Text(), nullable=False),
        sa.Column("fermentation_systems", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "batch_ingredients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("batches.id"), nullable=False
        ),
        sa.Column(
            "ingredient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ingredients.id"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Float(), nullable=True),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column("role", sa.Text(), nullable=False),
    )
    op.create_index("ix_batch_ingredients_batch_id", "batch_ingredients", ["batch_id"])

    op.bulk_insert(
        ingredients_table,
        [
            {
                "id": uuid.uuid4(),
                "canonical_id": None,
                "name": name,
                "default_role": role,
                "fermentation_systems": systems,
                "is_active": True,
            }
            for name, role, systems in INGREDIENT_SEED_DATA
        ],
    )


def downgrade() -> None:
    op.drop_table("batch_ingredients")
    op.drop_table("ingredients")
```

- [ ] **Step 6: Verify the migration runs cleanly against a scratch database**

This project's pytest suite builds tables via `Base.metadata.create_all` (see `tests/conftest.py`), not via Alembic — matching how migration `0001` was handled, this migration isn't exercised by the automated test suite. Verify it manually against a throwaway SQLite file:

Run:
```bash
DATABASE_URL="sqlite:///./_migration_check.db" python -m alembic upgrade head
```
Expected: completes with no errors, prints `Running upgrade  -> 0001, ...` then `Running upgrade 0001 -> 0002, ...`.

Then confirm the seed rows landed:
```bash
python -c "
import sqlite3
conn = sqlite3.connect('_migration_check.db')
print(conn.execute('SELECT COUNT(*) FROM ingredients').fetchone())
conn.close()
"
```
Expected: `(20,)`

Clean up the scratch file:
```bash
rm _migration_check.db
```

- [ ] **Step 7: Commit**

```bash
git add src/fermenttrack/seed_data.py alembic/versions/0002_ingredients.py tests/test_seed_data.py
git commit -m "feat: seed 20 reference ingredients across kombucha/sourdough/koji/cheese/kefir/miso/vinegar"
```

---

## Task 5: `GET /ingredients` endpoint

**Files:**
- Create: `src/fermenttrack/routers/ingredients.py`
- Modify: `src/fermenttrack/main.py`
- Test: `tests/test_ingredients.py` (new file)

**Interfaces:**
- Consumes: `Ingredient` model, `IngredientOut` schema (Task 3).
- Produces: `GET /ingredients` — not consumed by any other task in this plan; Increment 2's preview endpoint (separate plan) may use it later.

- [ ] **Step 1: Write the failing test**

Create `tests/test_ingredients.py`:

```python
"""GET /ingredients — reference data listing."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.models import Ingredient


@pytest.mark.asyncio
async def test_list_ingredients_returns_only_active(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add_all(
        [
            Ingredient(name="Black/green tea", default_role="base", fermentation_systems=["kombucha"]),
            Ingredient(
                name="Retired ingredient",
                default_role="base",
                fermentation_systems=["kombucha"],
                is_active=False,
            ),
        ]
    )
    await db_session.commit()

    resp = await client.get("/ingredients")
    assert resp.status_code == 200
    names = {i["name"] for i in resp.json()}
    assert names == {"Black/green tea"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ingredients.py -v`
Expected: FAIL with 404 — no `/ingredients` route registered yet.

- [ ] **Step 3: Create the router**

Create `src/fermenttrack/routers/ingredients.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.database import get_db
from fermenttrack.models import Ingredient
from fermenttrack.schemas import IngredientOut

router = APIRouter(prefix="/ingredients", tags=["ingredients"])


@router.get("", response_model=list[IngredientOut])
async def list_ingredients(db: AsyncSession = Depends(get_db)) -> list[Ingredient]:
    result = await db.execute(select(Ingredient).where(Ingredient.is_active.is_(True)))
    return list(result.scalars().all())
```

- [ ] **Step 4: Register the router in `src/fermenttrack/main.py`**

Change:
```python
from fermenttrack.routers import batches, cultures, reminders, safety, webhooks
```
to:
```python
from fermenttrack.routers import batches, cultures, ingredients, reminders, safety, webhooks
```

And add, alongside the other `app.include_router(...)` calls:
```python
app.include_router(ingredients.router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_ingredients.py -v`
Expected: PASS, 1 test.

- [ ] **Step 6: Commit**

```bash
git add src/fermenttrack/routers/ingredients.py src/fermenttrack/main.py tests/test_ingredients.py
git commit -m "feat: add GET /ingredients reference-data endpoint"
```

---

## Task 6: Batch recipe endpoints (`BatchIngredient` CRUD)

**Files:**
- Modify: `src/fermenttrack/routers/batches.py` (add two endpoints, extend imports)
- Test: `tests/test_batch_ingredients.py` (new file)

**Interfaces:**
- Consumes: `BatchIngredient`, `Ingredient` models; `BatchIngredientCreate`, `BatchIngredientOut` schemas (Task 3); `_get_batch` helper (Task 2).
- Produces: `POST /batches/{batch_id}/ingredients`, `GET /batches/{batch_id}/ingredients` — Increment 2's preview endpoint (separate plan) will call the same query pattern, not this HTTP endpoint directly.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_batch_ingredients.py`:

```python
"""POST/GET /batches/{id}/ingredients — recipe logging with role pre-fill."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.models import Ingredient


async def _create_culture_and_batch(client: AsyncClient) -> tuple[str, str]:
    resp = await client.post("/cultures", json={"name": "Jun SCOBY", "type": "kombucha"})
    culture_id = resp.json()["id"]
    resp = await client.post("/batches", json={"culture_id": culture_id})
    return culture_id, resp.json()["id"]


@pytest.mark.asyncio
async def test_add_batch_ingredient_prefills_role_from_ingredient_default(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    ingredient = Ingredient(name="Cane sugar", default_role="base", fermentation_systems=["kombucha"])
    db_session.add(ingredient)
    await db_session.commit()
    await db_session.refresh(ingredient)

    _culture_id, batch_id = await _create_culture_and_batch(client)

    resp = await client.post(
        f"/batches/{batch_id}/ingredients",
        json={"ingredient_id": str(ingredient.id), "quantity": 200.0, "unit": "g"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "base"
    assert body["quantity"] == 200.0
    assert body["unit"] == "g"


@pytest.mark.asyncio
async def test_add_batch_ingredient_role_override_persists(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    ingredient = Ingredient(name="Cane sugar", default_role="base", fermentation_systems=["kombucha"])
    db_session.add(ingredient)
    await db_session.commit()
    await db_session.refresh(ingredient)

    _culture_id, batch_id = await _create_culture_and_batch(client)

    resp = await client.post(
        f"/batches/{batch_id}/ingredients",
        json={"ingredient_id": str(ingredient.id), "role": "flavoring"},
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "flavoring"

    # Later edits to Ingredient.default_role must not retroactively change
    # this batch's already-recorded role.
    ingredient.default_role = "starter"
    await db_session.commit()

    resp = await client.get(f"/batches/{batch_id}/ingredients")
    assert resp.json()[0]["role"] == "flavoring"


@pytest.mark.asyncio
async def test_add_batch_ingredient_unknown_ingredient_404s(client: AsyncClient) -> None:
    _culture_id, batch_id = await _create_culture_and_batch(client)
    resp = await client.post(
        f"/batches/{batch_id}/ingredients",
        json={"ingredient_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_batch_ingredients_unknown_batch_404s(client: AsyncClient) -> None:
    resp = await client.get("/batches/00000000-0000-0000-0000-000000000000/ingredients")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_batch_ingredients_empty_recipe(client: AsyncClient) -> None:
    _culture_id, batch_id = await _create_culture_and_batch(client)
    resp = await client.get(f"/batches/{batch_id}/ingredients")
    assert resp.status_code == 200
    assert resp.json() == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_batch_ingredients.py -v`
Expected: FAIL with 404 on every request — the routes don't exist yet.

- [ ] **Step 3: Add the endpoints to `src/fermenttrack/routers/batches.py`**

Extend the imports at the top of the file (add to the existing `fermenttrack.models` and `fermenttrack.schemas` import lines):

```python
from fermenttrack.models import Batch, BatchIngredient, Culture, Ingredient, Measurement, Reminder
```

```python
from fermenttrack.schemas import (
    BatchCompare,
    BatchCreate,
    BatchIngredientCreate,
    BatchIngredientOut,
    BatchOut,
    BatchTimeline,
    MeasurementCreate,
    MeasurementOut,
    NoteCreate,
    StageAdvance,
    TimelineEvent,
)
```

Append these two endpoints at the end of the file (after `compare_batches`):

```python
@router.post("/{batch_id}/ingredients", response_model=BatchIngredientOut, status_code=201)
async def add_batch_ingredient(
    batch_id: uuid.UUID, payload: BatchIngredientCreate, db: AsyncSession = Depends(get_db)
) -> BatchIngredient:
    batch = await _get_batch(batch_id, db)
    ingredient = await db.get(Ingredient, payload.ingredient_id)
    if ingredient is None:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    batch_ingredient = BatchIngredient(
        batch_id=batch.id,
        ingredient_id=ingredient.id,
        quantity=payload.quantity,
        unit=payload.unit,
        role=payload.role or ingredient.default_role,
    )
    db.add(batch_ingredient)
    await db.commit()
    await db.refresh(batch_ingredient)
    return batch_ingredient


@router.get("/{batch_id}/ingredients", response_model=list[BatchIngredientOut])
async def list_batch_ingredients(
    batch_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[BatchIngredient]:
    await _get_batch(batch_id, db)  # raises 404 if the batch doesn't exist
    result = await db.execute(select(BatchIngredient).where(BatchIngredient.batch_id == batch_id))
    return list(result.scalars().all())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_batch_ingredients.py -v`
Expected: PASS, 5 tests.

- [ ] **Step 5: Run the full test suite**

Run: `pytest -q`
Expected: PASS, all tests across the whole project green — this is the last task in the plan.

- [ ] **Step 6: Commit**

```bash
git add src/fermenttrack/routers/batches.py tests/test_batch_ingredients.py
git commit -m "feat: add batch recipe endpoints (POST/GET /batches/{id}/ingredients)"
```

---

## Self-Review Notes

- **Spec coverage:** `Ingredient` model ✓ (Task 3), `BatchIngredient` model ✓ (Task 3), seed data across all documented substrates ✓ (Task 4), stage machine generalization for kombucha/sourdough/koji/cheese + no-machine fallback for kefir/miso/vinegar ✓ (Tasks 1-2), `role` copy-at-insert-not-re-derived ✓ (Task 6, tested explicitly). `Measurement` — spec says "no schema break," correctly no task touches it. `GET /batches/{id}/preview` and the frontend are explicitly out of scope for this plan (separate plans per the spec's increment split) — not included here, by design.
- **Type consistency:** `get_stage`/`next_stage_name`/`first_stage` all take `substrate: str` as the first argument consistently across Tasks 1, 2. `BatchIngredientCreate.role: str | None` in the schema matches the `payload.role or ingredient.default_role` fallback logic in Task 6 exactly.
- **No placeholders:** every step has literal, complete code — verified by re-reading each task's Step 3/implementation block.
