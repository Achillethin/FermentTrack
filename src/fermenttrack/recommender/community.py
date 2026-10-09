"""Community recipes (design § 10.3, Q23, Q29, Q30): a finished batch published as a recipe, the
forecast jobs of the approved ones, their "Community — not proven" cards, and a community recipe
as an Experimental parent or a Start batch. The database is the routers' (routers/community.py
reads and writes it); everything here is computed from plain values.

**Publish** (`draft`: design § 10.3's automatic checks, on one's own finished batch):
- the type has a forecast profile (not a free-string "generic" type) and is not sourdough (its
  recipes are shared through the levain planner);
- finished: the batch has an end time, after its start (the actual duration is the recipe's);
- the rows are the batch's BatchIngredient rows: each a live catalogue name or a USDA pick
  (stored with its fdc_id and nutrients, labelled "USDA food: aroma effect unknown"), with a
  quantity in a known unit. A retired ingredient, an unknown unit or a missing, non-finite or
  non-positive quantity refuses the publication, naming the rows;
- **normalisation**: each logged quantity to grams (composition.to_grams: g, kg, mg; ml and l
  at 1 g/ml, the composition module's assumption), then g/kg of the batch's weighed total,
  1000 × g / total, rounded to 0.01 g/kg. **Mass balance**: the stored rows sum to 1000 g/kg
  ± 5 % (MASS_TOLERANCE): scaled back, the stored recipe is the logged batch within 5 %. Every
  other row being refused, only a conversion fault can fail it: it guards what is stored;
- the temperature is the mean of the batch's plausible temperature readings (inside the
  engine's TEMP_RANGE_C, logged between its start and end), else its expected temperature;
- the gate (design § 7, with the salt-barrier minimums) passes at that temperature, and at
  least one model temperature (`forecast_temperatures`) passes it too;
- acid-safety types (gate.needs_ph_reminder) have a pH reading of 2.0-4.6 logged between the
  batch's start and end (`ph_evidence`: lower readings are meter faults or typos);
- feedback (`publish_checks_feedback`): until the tasting form (B10), the batch's outcome is
  "success"; B10 switches that one function to "a tasting is filled in".
Then the recipe is pending until an admin approves or rejects it.

**Forecasts** (job kind "community_forecast", the B8 queue): approval enqueues one system job
per recipe, with one step per model temperature: `forecast_temperatures`, the grid builder's
three (design § 8.1: the profile's temp_range[0], temp_c and temp_range[1], the recipe's own
temperature clipped into the range replacing the nearest) that pass the gate. Each step is a
live forecast with the live paths' 64 members (service.FORECAST_MEMBERS, not the grid's 160)
on the recipe's own time axis (run.time_axis of its duration span), summarised like a grid
entry (service.live_variant_statistics: E / U / P per series, milestone crossing times, card
labels). `store_forecasts` (the job's on_done) replaces the recipe's rows in
community_recipe_forecasts, each with the grid version it goes with, unless the recipe was
rejected meanwhile. At startup (`recompute_at_startup`), every approved recipe whose forecasts
are missing or of another grid version is enqueued again; a recipe whose job is queued or
running is never enqueued twice (the job's fingerprint is "community_forecast:<id>"), and one
whose newest job failed on the current grid version is not retried (`stale`) until an admin
approves it again or the grid changes.

**As a recipe** (`as_recipe`; Q25, Q26): the documented temperature span is the batch's
temperature ± 3 °C (TEMP_WIDEN_C) and the duration span its actual duration ± 30 %
(DURATION_WIDEN), labelled "single-value source, widened". The card serves the temperature like
a library recipe's (service.resolve_temperature): the user's, else the batch's, clamped to that
span within the safety limits; source-only outside the profile's range.

**Section** "Community — not proven" (`section`, mode proven or both): approved recipes with
forecasts of the current grid version that hold every must-include ingredient and pass the gate
at every temperature the card can show; statistics interpolated in temperature between the
stored forecasts (clamped to them, like grid.interp_temp), the window in mode community (§ 6:
up to d_hi, never before d_lo); ranked by E(peak), then "made n×" (the distinct other people
who started a batch from it, its variants included, its author excluded), then the mean liking
(None until B10's tastings); 3 cards at most. A recipe whose card cannot be built is logged and
left out. The card names the pseudonym and "made n×" and carries the trust
label "Community — not proven" and the gate's safety lines.

**Parent** (`parent`): a community recipe is an Experimental parent like your own batch: live
forecasts, at most 3 variants (service.own_batch_cards), labelled "community recipe".
"""

from __future__ import annotations

import asyncio
import logging
import math
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fermenttrack.composition import to_grams
from fermenttrack.models import (
    ACTIVE_JOB_STATUSES,
    COMMUNITY_APPROVED,
    JOB_DONE,
    JOB_FAILED,
    CommunityRecipe,
    CommunityRecipeForecast,
    RecommendationJob,
)
from fermenttrack.prediction import service as engine
from fermenttrack.prediction.priors import FloatArray
from fermenttrack.prediction.profiles import PROFILES
from fermenttrack.recommender import gate, grid, jobs, library, operators, run, service
from fermenttrack.recommender.library import Recipe, RecipeIngredient, Span

logger = logging.getLogger(__name__)

COMMUNITY_FORECAST = "community_forecast"  # the job kind
FORECAST_VERSION = 1  # the job's plan and steps (Handler.version)
SECTION_LABEL = "Community — not proven"
NO_MATCH = "No approved community recipe matches this request yet."
PROVENANCE = "community"
PRIVACY_NOTICE = (
    "Your recipe stays in the library if you delete your account; it is detached from you."
)
TEMP_WIDEN_C = 3.0  # Q25: the batch's single temperature, widened
DURATION_WIDEN = 0.3  # Q25: its actual duration ± 30 %
MASS_TOLERANCE = 0.05  # the stored rows sum to 1000 g/kg ± 5 %
PH_SAFE = 4.6
PH_EVIDENCE_MIN = 2.0  # a lower "pH" is no food ferment's: not evidence (ph_evidence)
OUTCOME_SHARED = "success"  # the batch outcome publishing needs (publish_checks_feedback)
USDA_LABEL = f"USDA food: {operators.AROMA_UNKNOWN}"


class PublishRefused(ValueError):
    """The batch fails one or more of the publishing checks (every reason found)."""

    def __init__(self, reasons: Sequence[str]) -> None:
        super().__init__("; ".join(reasons))
        self.reasons = tuple(reasons)


# ── publishing (design § 10.3) ──────────────────────────────────────────


@dataclass(frozen=True)
class LoggedRow:
    """A BatchIngredient row as logged."""

    name: str
    quantity: float | None
    unit: str | None
    role: str
    active: bool  # Ingredient.is_active: False for a retired ingredient
    fdc_id: int | None = None  # a USDA pick
    nutrients: tuple[tuple[str, float], ...] = ()  # g/100 g (a USDA pick's)


@dataclass(frozen=True)
class SourceBatch:
    """The batch to publish, as the router reads it (owned: checked there)."""

    fermentation_type: str
    rows: tuple[LoggedRow, ...]
    temperatures: tuple[tuple[datetime, float], ...]  # logged readings: (measured_at, °C)
    expected_temperature_c: float | None
    ph: tuple[tuple[datetime, float], ...]  # logged readings: (measured_at, pH)
    started_at: datetime
    ended_at: datetime | None
    outcome: str | None


@dataclass(frozen=True)
class Draft:
    """What publishing stores."""

    fermentation_type: str
    rows: tuple[dict[str, Any], ...]  # {name, role, g_per_kg, fdc_id, nutrients}
    temperature_c: float
    duration_h: float


def publish_checks_feedback(batch: SourceBatch) -> list[str]:
    """Design § 10.3's feedback check: until the tasting form (B10), the batch's outcome is
    recorded as a success (only a batch that turned out well is shared). B10 switches this
    function to "a tasting is filled in"."""
    if batch.outcome != OUTCOME_SHARED:
        return ["only a batch that turned out well is shared: record its outcome as a success"]
    return []


def _type_reasons(ferment_type: str) -> list[str]:
    if ferment_type == "sourdough":
        return ["sourdough recipes are shared through the levain planner, not here"]
    if ferment_type not in PROFILES:
        return [f"a {ferment_type!r} batch has no forecast profile (a generic type)"]
    return []


def _names(rows: Iterable[LoggedRow]) -> str:
    return ", ".join(sorted({r.name for r in rows}))


def normalise(rows: Sequence[LoggedRow]) -> tuple[list[dict[str, Any]], list[str]]:
    """(the rows as g/kg of the weighed total, the refusals naming the rows that cannot be)."""
    retired = [r for r in rows if not r.active]
    unknown = [
        r for r in rows if r.active and r.fdc_id is None and r.name not in library.CATALOGUE_NAMES
    ]
    grams: dict[int, float] = {}
    unweighed = []
    for i, r in enumerate(rows):
        g = to_grams(r.quantity, r.unit)
        if g is None or not math.isfinite(g) or g <= 0:
            unweighed.append(r)
        else:
            grams[i] = g
    reasons = []
    if not rows:
        reasons.append("the batch has no ingredients logged")
    if retired:
        reasons.append(f"retired ingredients, replace them with current ones: {_names(retired)}")
    if unknown:
        reasons.append(f"not in the ingredient catalogue: {_names(unknown)}")
    if unweighed:
        reasons.append(
            "no usable quantity (missing, not positive, or in an unknown unit): "
            f"{_names(unweighed)}"
        )
    if reasons:
        return [], reasons
    total = math.fsum(grams.values())
    out = [
        {
            "name": r.name, "role": r.role, "g_per_kg": round(1000.0 * grams[i] / total, 2),
            "fdc_id": r.fdc_id,
            "nutrients": [[n, v] for n, v in r.nutrients] if r.fdc_id is not None else None,
        }
        for i, r in enumerate(rows)
    ]  # fmt: skip
    return out, []


def mass_balanced(rows: Iterable[Mapping[str, Any]]) -> bool:
    """The stored rows sum to 1000 g/kg ± MASS_TOLERANCE."""
    total = math.fsum(float(r["g_per_kg"]) for r in rows)
    return math.isfinite(total) and abs(total - 1000.0) <= 1000.0 * MASS_TOLERANCE


def _during(batch: SourceBatch, at: datetime) -> bool:
    """Logged between the batch's start and its end (inclusive)."""
    end = batch.ended_at
    return _utc(batch.started_at) <= _utc(at) and (end is None or _utc(at) <= _utc(end))


def _plausible_c(t: float | None) -> bool:
    lo, hi = engine.TEMP_RANGE_C  # the engine's accepted readings
    return t is not None and lo <= t <= hi  # False for NaN too


def mean_temperature(batch: SourceBatch) -> float | None:
    """The mean of the plausible temperature readings logged during the batch (inside the
    engine's TEMP_RANGE_C), else the expected temperature (if plausible)."""
    readings = [t for at, t in batch.temperatures if _plausible_c(t) and _during(batch, at)]
    if readings:
        return math.fsum(readings) / len(readings)
    t = batch.expected_temperature_c
    return t if _plausible_c(t) else None


def ph_evidence(batch: SourceBatch) -> bool:
    """A pH reading of PH_SAFE or below, logged during the batch and plausible: at least
    PH_EVIDENCE_MIN (a reading outside 0-14 is not a pH, and one below 2 is no food ferment's:
    a meter fault or a typo)."""
    return any(PH_EVIDENCE_MIN <= p <= PH_SAFE and _during(batch, at) for at, p in batch.ph)


def draft(batch: SourceBatch) -> Draft:
    """The recipe a batch publishes, after every check of design § 10.3 (module docstring).
    Raises PublishRefused with every reason found."""
    ft = batch.fermentation_type
    reasons = _type_reasons(ft)
    if reasons:
        raise PublishRefused(reasons)
    if batch.ended_at is None:
        raise PublishRefused(["only a finished batch can be published: finish it first"])
    duration = (_utc(batch.ended_at) - _utc(batch.started_at)).total_seconds() / 3600.0
    if not duration > 0:
        reasons.append("the batch has no duration: its end is not after its start")
    rows, row_reasons = normalise(batch.rows)
    reasons += row_reasons
    temp = mean_temperature(batch)
    if temp is None:
        reasons.append("no temperature: log temperature readings or set the expected one")
    if rows and not mass_balanced(rows):
        reasons.append("the ingredient masses do not balance to 1000 g/kg (± 5 %)")
    if rows and temp is not None and duration > 0:
        recipe = as_recipe("draft", "draft", ft, rows, temp, duration)
        result = gate.check(gate.from_recipe(recipe), [])
        if not result.ok:
            reasons.append(f"the safety checks refuse it: {'; '.join(result.reasons)}")
        elif not forecast_temperatures(recipe):
            reasons.append("no temperature the model covers passes the safety checks for it")
    if gate.needs_ph_reminder(ft) and not ph_evidence(batch):
        reasons.append(
            f"log a pH reading of {PH_SAFE:g} or below, taken during the batch, first (an "
            "acid-safety ferment)"
        )
    reasons += publish_checks_feedback(batch)
    if reasons:
        raise PublishRefused(reasons)
    assert temp is not None
    return Draft(ft, tuple(rows), round(temp, 2), round(duration, 2))


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)  # SQLite drops the zone


# ── a stored community recipe as a recipe ───────────────────────────────


def _ingredient(row: Mapping[str, Any]) -> RecipeIngredient:
    g = float(row["g_per_kg"])
    fdc_id = None if row.get("fdc_id") is None else int(row["fdc_id"])
    usda = fdc_id is not None
    nutrients = (
        tuple((str(n), float(v)) for n, v in row.get("nutrients") or ()) if usda else None
    )
    return RecipeIngredient(
        str(row["name"]), "user" if usda else "existing", str(row["role"]), Span(g, g, g),
        "core", "community recipe", "", USDA_LABEL if usda else None, nutrients=nutrients,
        fdc_id=fdc_id,
    )  # fmt: skip


def as_recipe(
    recipe_id: str,
    title: str,
    fermentation_type: str,
    rows: Sequence[Mapping[str, Any]],
    temperature_c: float,
    duration_h: float,
) -> Recipe:
    """The community recipe as a library recipe (key "community:<id>"): its temperature
    ± TEMP_WIDEN_C and its duration ± DURATION_WIDEN as the documented spans (Q25)."""
    profile = PROFILES[fermentation_type]
    t, d = float(temperature_c), float(duration_h)
    temp = Span(t, t - TEMP_WIDEN_C, t + TEMP_WIDEN_C)
    duration = Span(d, (1.0 - DURATION_WIDEN) * d, (1.0 + DURATION_WIDEN) * d)
    p_lo, p_hi = profile.temp_range
    scope = []
    if not (p_lo <= temp.lo and temp.hi <= p_hi):
        scope.append("temp_outside_profile")
    if duration.hi > profile.horizon_h:
        scope.append("beyond_horizon")
    return Recipe(
        key=f"community:{recipe_id}", name=title, fermentation_type=fermentation_type,
        style_region="", provenance=PROVENANCE, temp_c=temp, duration_h=duration,
        salt_pct=None, sugar_g_per_kg=None, aerobic=profile.aerobic, method="", stages="",
        safety_targets="", reported_aromas=(), sources=(), status="active", notes="",
        temp_schedule=(), envelope_basis="widened_single_value",
        model_scope=tuple(scope) or ("in_range",), handoff=None, planner_style=None,
        ingredients=tuple(_ingredient(r) for r in rows),
    )  # fmt: skip


def forecast_temperatures(recipe: Recipe) -> tuple[float, ...]:
    """The model temperatures its forecasts run at: design § 8.1's three, as the grid builder
    picks them (scripts/build_recommender_grid.py candidate_temperatures and
    grid_temperatures, for a recipe without stages): the profile's temp_range[0], temp_c and
    temp_range[1], the recipe's own temperature clipped into the range replacing the nearest
    (the lower one on a tie); those that pass the gate."""
    profile = PROFILES[recipe.fermentation_type]
    lo, hi = profile.temp_range
    assert recipe.temp_c is not None  # as_recipe always sets it
    cands = [lo, profile.temp_c, hi]
    own = min(max(recipe.temp_c.median, lo), hi)
    cands[min(range(3), key=lambda i: abs(cands[i] - own))] = own
    like = gate.from_recipe(recipe)
    return tuple(t for t in sorted(set(cands)) if gate.check(like, [t]).ok)


def axis(recipe: Recipe) -> tuple[FloatArray, float]:
    """The recipe's time axis (run.time_axis): 24 log-spaced times to 1.5 × d_hi within the
    horizon, plus d_lo, d_med and d_hi."""
    d = recipe.duration_h
    assert d is not None  # as_recipe always sets it
    horizon = float(PROFILES[recipe.fermentation_type].horizon_h)
    return run.time_axis((d.lo, d.median, d.hi), horizon)


# ── statistics as JSON (the grid's schema) ──────────────────────────────


def _num(x: float) -> float | None:
    """4 decimals (the grid keeps float16); None for inf (a milestone not reached): JSON has
    no infinity."""
    return round(float(x), 4) if math.isfinite(x) else None


def entry_json(entry: grid.Entry) -> dict[str, Any]:
    """A forecast with the grid's statistics (grid.Entry) as JSON."""

    def series(m: Mapping[str, FloatArray]) -> dict[str, list[float | None]]:
        return {s: [_num(x) for x in v] for s, v in sorted(m.items())}

    return {
        "temp_c": float(entry.temp_c),
        "t_h": [_num(x) for x in entry.t_h],
        "e": series(entry.e), "u": series(entry.u), "p": series(entry.p),
        "milestones": {
            k: [_num(m.p10), _num(m.p50), _num(m.p90), _num(m.reached)]
            for k, m in sorted(entry.milestones.items())
        },
        "members": entry.members,
        "schedule": [[float(h), float(c)] for h, c in entry.schedule],
        "top_compound": {s: [c, tier] for s, (c, tier) in sorted(entry.top_compound.items())},
        "not_modelled": list(entry.not_modelled),
        "skipped": list(entry.skipped),
    }  # fmt: skip


def entry_from_json(recipe_key: str, doc: Mapping[str, Any]) -> grid.Entry:
    def series(m: Mapping[str, Sequence[float]]) -> Mapping[str, FloatArray]:
        return MappingProxyType({s: np.asarray(v, dtype=np.float64) for s, v in m.items()})

    def time(x: float | None) -> float:
        return math.inf if x is None else float(x)

    return grid.Entry(
        recipe_key=recipe_key, temp_c=float(doc["temp_c"]),
        t_h=np.asarray(doc["t_h"], dtype=np.float64), e=series(doc["e"]), u=series(doc["u"]),
        p=series(doc["p"]),
        milestones=MappingProxyType({
            k: grid.MilestoneTimes(*(time(x) for x in v)) for k, v in doc["milestones"].items()
        }),
        members=int(doc["members"]),
        schedule=tuple((float(h), float(c)) for h, c in doc["schedule"]),
        top_compound=MappingProxyType({s: (c, t) for s, (c, t) in doc["top_compound"].items()}),
        not_modelled=tuple(doc["not_modelled"]), skipped=tuple(doc["skipped"]),
    )  # fmt: skip


def interp(entries: Sequence[grid.Entry], temp_c: float) -> grid.Entry:
    """The stored forecasts linear in temperature between the two around temp_c, clamped to
    the end ones (grid.interp_temp's rule; they share the recipe's time axis)."""
    ordered = sorted(entries, key=lambda e: e.temp_c)
    t = min(max(temp_c, ordered[0].temp_c), ordered[-1].temp_c)
    for e in ordered:
        if abs(e.temp_c - t) <= 1e-6:
            return replace(e, temp_c=t)
    k = next(i for i, e in enumerate(ordered) if e.temp_c > t)
    return grid._mix(ordered[k].recipe_key, ordered[k - 1], ordered[k], t)


# ── an approved recipe, as served ───────────────────────────────────────


@dataclass(frozen=True)
class Stored:
    """A community recipe as the router reads it (plain values)."""

    id: uuid.UUID
    title: str
    pseudonym: str
    fermentation_type: str
    rows: tuple[Mapping[str, Any], ...]
    temperature_c: float
    duration_h: float
    forecasts: tuple[Mapping[str, Any], ...] = ()  # stats JSON of the current grid version
    made: int = 0  # other people who started a batch from it (routers/community.py)
    mean_liking: float | None = None  # B10


def stored(
    row: CommunityRecipe, forecasts: Iterable[CommunityRecipeForecast] = (), made: int = 0
) -> Stored:
    return Stored(
        row.id, row.title, row.pseudonym, row.fermentation_type, tuple(row.recipe),
        row.temperature_c, row.duration_h, tuple(f.stats for f in forecasts), made,
    )  # fmt: skip


@dataclass(frozen=True)
class Candidate:
    id: uuid.UUID
    title: str
    pseudonym: str
    recipe: Recipe
    forecasts: tuple[grid.Entry, ...]  # of the current grid version; () when none
    made: int
    mean_liking: float | None


def candidate(s: Stored) -> Candidate:
    recipe = as_recipe(
        str(s.id), s.title, s.fermentation_type, s.rows, s.temperature_c, s.duration_h
    )
    entries = tuple(entry_from_json(recipe.key, doc) for doc in s.forecasts)
    return Candidate(s.id, s.title, s.pseudonym, recipe, entries, s.made, s.mean_liking)


def candidates(rows: Iterable[Stored]) -> list[Candidate]:
    """The section's candidates; a stored recipe that cannot be read is logged and left out."""
    out = []
    for s in rows:
        try:
            out.append(candidate(s))
        except Exception:
            logger.exception("community recipe %s cannot be read: left out", s.id)
    return out


def basis(c: Candidate) -> service.Basis:
    """The window's basis: the duration span, the profile horizon, and the median time to the
    profile's main milestone at the recipe's own temperature (stored forecasts; else None,
    no kinetic shift)."""
    recipe = c.recipe
    d = recipe.duration_h
    assert d is not None and recipe.temp_c is not None
    profile = PROFILES[recipe.fermentation_type]
    m_source = None
    if c.forecasts:
        m = interp(c.forecasts, recipe.temp_c.median).milestones.get(profile.milestones[0].key)
        m_source = m.p50 if m else None
    return service.Basis((d.lo, d.median, d.hi), float(profile.horizon_h), m_source)


def community_card(
    c: Candidate,
    targets: Sequence[service.Target],
    temperature_c: float | None,
    batch_g: float,
    listed: Iterable[str] = (),
    *,
    stats: grid.Entry | None = None,
) -> service.Card | None:
    """The recipe's card, or None when the gate refuses it at a temperature the card can show
    (or it has no stored forecast and no live one is given). stats: a live forecast; default:
    the stored forecasts at the served temperature."""
    recipe = c.recipe
    temp = service.resolve_temperature(recipe, temperature_c)
    result = service.check_gate(recipe, temp)
    if not result.ok:
        return None
    live = stats is not None
    if stats is None:
        if not c.forecasts:
            return None
        stats = interp(c.forecasts, temp.served_c)
    ev = service.evaluate(recipe, stats, temp, targets, mode="community", basis=basis(c))
    nearest = service.IN_RANGE if live else service.PRECOMPUTED
    return service.Card(
        recipe=recipe, temperature=temp, schedule=(), model_c=stats.temp_c, evaluation=ev,
        safety_lines=result.safety_lines, batch_g=batch_g,
        to_buy=service.to_buy(recipe, listed), not_modelled=stats.not_modelled,
        notes=(*temp.notes, *service._model_note(stats.temp_c, temp, nearest), *ev.notes),
    )  # fmt: skip


def rank_key(card: service.Card, c: Candidate) -> tuple[float, int, float, str]:
    """§ 5.4 Community: E(peak), "made n×", the mean liking (0 until B10's tastings), then the
    id for a stable order."""
    e = card.evaluation.e
    liking = c.mean_liking if c.mean_liking is not None else 0.0
    return -(e if e is not None else 0.0), -c.made, -liking, str(c.id)


def card_json(card: service.Card, c: Candidate) -> dict[str, Any]:
    body = service.card_json(card)
    labels = [
        *service.CARD_LABELS, SECTION_LABEL,
        *library.trust_labels(card.recipe, card.temperature.served_c),
    ]  # fmt: skip
    return body | {
        "id": f"community:{c.id}",
        "section": "community",
        "source_kind": "community",
        "recipe_key": None,
        "name": c.title,
        "trust": body["trust"] | {"labels": labels},
        "community": {
            "id": str(c.id), "title": c.title, "pseudonym": c.pseudonym, "made": c.made,
            "mean_liking": c.mean_liking,
        },
    }  # fmt: skip


def section(
    candidates: Iterable[Candidate],
    listed: Sequence[str],
    aromas: Sequence[str],
    tastes: Sequence[str],
    temperature_c: float | None,
    batch_g: float = service.DEFAULT_BATCH_G,
) -> dict[str, Any]:
    """The "Community — not proven" section (schemas.RecommendationSectionOut). A candidate
    whose card cannot be built (a corrupt stored forecast, an engine error) is logged and
    left out: it never fails the request."""
    targets = service.parse_targets(aromas, tastes)
    listed = tuple(dict.fromkeys(listed))
    scored = []
    for c in candidates:
        if not c.forecasts or not service.contains(c.recipe, listed):
            continue
        try:
            card = community_card(c, targets, temperature_c, batch_g, listed)
        except Exception:
            logger.exception("community recipe %s: its card is left out", c.id)
            continue
        if card is not None:
            scored.append((rank_key(card, c), card, c))
    scored.sort(key=lambda x: x[0])
    top = scored[: service.CARDS_PER_SECTION]
    message = None if top else NO_MATCH
    return {"cards": [card_json(card, c) for _, card, c in top], "message": message}


def parent(c: Candidate) -> service.Parent:
    """The recipe as an Experimental parent (live, like your own batch)."""
    label = f"community recipe “{c.title}” by {c.pseudonym}"
    return service.Parent(c.recipe, "community", label, basis=basis(c), community_id=str(c.id))


def _live(c: Candidate, temp: service.Temperature, members: int) -> grid.Entry:
    model_c = service.model_temperature(c.recipe, temp.served_c)
    t_dst, end = axis(c.recipe)
    stats, _, _ = service.live_variant_statistics(c.recipe, model_c, members, t_dst, end)
    return stats


def forecast(
    c: Candidate,
    aromas: Sequence[str],
    tastes: Sequence[str],
    temperature_c: float | None,
    members: int = service.FORECAST_MEMBERS,
) -> dict[str, Any]:
    """POST /recommendations/forecast for a community card (its slider): the live forecast at
    the served temperature clamped to the profile (service.model_temperature), shaped like
    schemas.RecommendationForecastOut. Raises GateRefused."""
    targets = service.parse_targets(aromas, tastes)
    recipe = c.recipe
    temp = service.resolve_temperature(recipe, temperature_c)
    result = service.check_gate(recipe, temp)
    if not result.ok:
        raise service.GateRefused("this temperature does not pass the safety checks here")
    stats = _live(c, temp, members)
    ev = service.evaluate(recipe, stats, temp, targets, mode="community", basis=basis(c))
    body = service._forecast_body(None, "community", [], False, result, temp)
    return body | service._live_json(stats, temp, stats.temp_c, ev, targets)


def batch_plan(
    c: Candidate,
    aromas: Sequence[str],
    tastes: Sequence[str],
    temperature_c: float | None,
    batch_g: float,
    mode: str,
) -> service.BatchPlan:
    """Start batch from a community card, recomputed here: from its stored forecasts, or a
    live forecast when they are not (yet) of the current grid. The link carries
    community_recipe_id; a USDA row is booked like a USDA pick. Raises GateRefused."""
    targets = service.parse_targets(aromas, tastes)
    recipe = c.recipe
    stats = None
    if not c.forecasts:
        temp = service.resolve_temperature(recipe, temperature_c)
        if not service.check_gate(recipe, temp).ok:
            raise service.GateRefused("this recipe does not pass the safety checks here")
        stats = _live(c, temp, service.FORECAST_MEMBERS)
    card = community_card(c, targets, temperature_c, batch_g, (), stats=stats)
    if card is None:
        raise service.GateRefused("this recipe does not pass the safety checks here")
    booked, skipped = run.recipe_rows(recipe)
    fdc = {i.name: i.fdc_id for i in recipe.ingredients if i.fdc_id is not None}
    grams = [(r.name, round(r.quantity * batch_g / 1000.0, 1), r.role) for r in booked
             if r.quantity is not None]  # fmt: skip
    rows = tuple(g for g in grams if g[0] not in fdc)
    fdc_rows = tuple((fdc[n], q, role) for n, q, role in grams if n in fdc)
    link = service._link(card, mode, "community", [], community_recipe_id=c.id)
    return service.BatchPlan(
        card, float(card.temperature.served_c), rows, skipped,
        gate.needs_ph_reminder(recipe.fermentation_type), link, f"{c.title} (community)",
        fdc_rows,
    )  # fmt: skip


# ── the forecast job (kind "community_forecast") ────────────────────────


def job_fingerprint(recipe_id: uuid.UUID | str) -> str:
    """One per recipe: a second job is never queued while one is active."""
    return f"{COMMUNITY_FORECAST}:{recipe_id}"


def job_request(row: CommunityRecipe, grid_version: str) -> dict[str, Any]:
    """The job's request: the recipe itself (the steps run without the database), and the grid
    version it was queued for (`stale` reads it from a failed job)."""
    return {
        "recipe_id": str(row.id), "title": row.title, "fermentation_type": row.fermentation_type,
        "recipe": list(row.recipe), "temperature_c": row.temperature_c,
        "duration_h": row.duration_h, "grid_version": grid_version,
    }  # fmt: skip


def _requested(request: Mapping[str, Any]) -> Recipe:
    return as_recipe(
        str(request["recipe_id"]), str(request["title"]), str(request["fermentation_type"]),
        request["recipe"], float(request["temperature_c"]), float(request["duration_h"]),
    )  # fmt: skip


def plan_forecasts(request: Mapping[str, Any]) -> list[dict[str, float]]:
    return [{"temp_c": t} for t in forecast_temperatures(_requested(request))]


def run_forecast_step(request: Mapping[str, Any], step: Mapping[str, Any]) -> dict[str, Any]:
    """One live forecast at one model temperature, with the grid version it goes with."""
    recipe = _requested(request)
    t_dst, end = axis(recipe)
    temp_c = float(step["temp_c"])
    stats, _, _ = service.live_variant_statistics(
        recipe, temp_c, service.FORECAST_MEMBERS, t_dst, end
    )
    return {"temp_c": temp_c, "grid_version": grid.version(), "stats": entry_json(stats)}


async def store_forecasts(db: AsyncSession, job: jobs.Job) -> None:
    """The job's on_done (in the transaction that marks it done): the recipe's forecasts
    replaced by the job's; nothing when it was rejected or deleted meanwhile. The recipe's
    older finished jobs go (their results are these)."""
    recipe_id = uuid.UUID(str(job.request["recipe_id"]))
    row = await db.get(CommunityRecipe, recipe_id)
    if row is None or row.status != COMMUNITY_APPROVED:
        return
    await db.execute(
        delete(CommunityRecipeForecast).where(CommunityRecipeForecast.recipe_id == recipe_id)
    )
    now = datetime.now(UTC)
    db.add_all(
        CommunityRecipeForecast(
            recipe_id=recipe_id, temp_c=float(r["temp_c"]), grid_version=str(r["grid_version"]),
            stats=r["stats"], created_at=now,
        )
        for r in job.results
    )  # fmt: skip
    await db.execute(
        delete(RecommendationJob).where(
            RecommendationJob.kind == COMMUNITY_FORECAST,
            RecommendationJob.fingerprint == job_fingerprint(recipe_id),
            RecommendationJob.status.in_((JOB_DONE, JOB_FAILED)),
            RecommendationJob.id != job.id,
        )
    )


async def enqueue(
    db: AsyncSession, row: CommunityRecipe, grid_version: str
) -> RecommendationJob | None:
    """Queue the recipe's forecast job for this grid version, unless one is queued or running
    (None). Commits the session either way."""
    active = await db.execute(
        select(RecommendationJob.id)
        .where(
            RecommendationJob.kind == COMMUNITY_FORECAST,
            RecommendationJob.fingerprint == job_fingerprint(row.id),
            RecommendationJob.status.in_(ACTIVE_JOB_STATUSES),
        )
        .limit(1)
    )
    if active.scalar_one_or_none() is not None:
        await db.commit()
        return None
    return await jobs.submit(
        db, COMMUNITY_FORECAST, job_request(row, grid_version),
        fingerprint=job_fingerprint(row.id),
    )  # fmt: skip


async def latest_jobs(
    db: AsyncSession, recipe_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, RecommendationJob]:
    """Each recipe's newest forecast job (the admin list shows its status and error)."""
    by_fingerprint = {job_fingerprint(i): i for i in recipe_ids}
    if not by_fingerprint:
        return {}
    found = await db.execute(
        select(RecommendationJob)
        .where(
            RecommendationJob.kind == COMMUNITY_FORECAST,
            RecommendationJob.fingerprint.in_(by_fingerprint),
        )
        .order_by(RecommendationJob.created_at, RecommendationJob.id)
    )
    return {by_fingerprint[j.fingerprint]: j for j in found.scalars()}  # the newest wins


async def stale(db: AsyncSession, current: str) -> list[CommunityRecipe]:
    """The approved recipes whose forecasts are missing or not all of the current grid, except
    those whose newest job failed on the current grid: retrying would fail again. An admin's
    re-approval, or a new grid version, queues them again."""
    approved = await db.execute(
        select(CommunityRecipe)
        .where(CommunityRecipe.status == COMMUNITY_APPROVED)
        .order_by(CommunityRecipe.created_at, CommunityRecipe.id)
    )
    versions: dict[uuid.UUID, set[str]] = {}
    found = await db.execute(
        select(CommunityRecipeForecast.recipe_id, CommunityRecipeForecast.grid_version)
    )
    for recipe_id, version in found.tuples():
        versions.setdefault(recipe_id, set()).add(version)
    rows = [r for r in approved.scalars() if versions.get(r.id) != {current}]
    latest = await latest_jobs(db, [r.id for r in rows])

    def failed_here(recipe_id: uuid.UUID) -> bool:
        job = latest.get(recipe_id)
        return job is not None and job.status == JOB_FAILED and (
            job.request.get("grid_version") == current
        )  # fmt: skip

    return [r for r in rows if not failed_here(r.id)]


async def enqueue_stale(sessions: async_sessionmaker[AsyncSession]) -> int:
    """Enqueue every stale approved recipe (dedupe: not one whose job is active); how many."""
    current = await asyncio.to_thread(grid.version)
    queued = 0
    async with sessions() as db:
        for row in await stale(db, current):
            if await enqueue(db, row, current) is not None:
                queued += 1
    return queued


async def recompute_at_startup(sessions: async_sessionmaker[AsyncSession]) -> None:
    """The app's lifespan task: enqueue_stale, retried after a connection error (the app
    starts even when the database is not reachable yet); any other error is logged."""
    while True:
        try:
            queued = await enqueue_stale(sessions)
        except Exception as exc:
            if not jobs.transient(exc):
                logger.exception("community forecasts: the startup recompute failed")
                return
            logger.warning("community forecasts: database unreachable, retrying: %s", exc)
            await asyncio.sleep(jobs.RETRY_S)
            continue
        if queued:
            logger.info("community forecasts: %d recipe(s) queued for recompute", queued)
        return


jobs.register(
    COMMUNITY_FORECAST,
    jobs.Handler(
        plan=plan_forecasts, step=run_forecast_step, max_steps=3, step_s=jobs.DEFAULT_STEP_S,
        errors=(service.RecommendationError, engine.PredictionUnavailable, run.RecipeError),
        on_done=store_forecasts, version=FORECAST_VERSION,
    ),
)  # fmt: skip
