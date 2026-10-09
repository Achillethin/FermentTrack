"""The recommender's orchestration (design §§ 5, 6, 10.1, 11): Proven cards from the grid, the
live per-card forecast, and the batch that Start batch records.

Per card:
- **Temperature** (`resolve_temperature`, the one place every route takes it from; Q26 as
  agreed with the owner). The served temperature is the user's, else the recipe's median,
  clamped only to the documented span and the safety limits: gate-passing, and koji at most
  35 °C with certified tane-koji as the only starter (else 33 °C, KOJI-001). It is what the
  card shows, Start batch books (with the source's own stages) and a planner link carries.
  It may lie outside the profile's temp_range: the model then works at a nearby temperature
  it covers (see Statistics), and the window comes from the source. The slider spans
  the same safe documented range. The served temperature and both slider ends go through
  `check_gate` (the gate plus the tane-koji ceiling); a failure removes the card (the reasons
  go to `debug`).
- **Source-only window** (Q26): decided by `source_only` alone, when the served temperature
  is outside the profile's temp_range. The window is the documented duration, and the card
  names the safe documented temperatures, the range the model covers and where aroma is
  computed.
- **Statistics and model_c** (the temperature actually used, always reported as `model_c`):
  cards (POST /recommendations) read the precomputed grid at the served temperature,
  `grid.interp_temp`, which clamps to the recipe's grid temperatures (e.g. sauerkraut
  16–22.5 °C inside its 16–24 °C profile). The live forecast (POST
  /recommendations/forecast, the slider) runs the engine at the served temperature clamped
  to the profile's temp_range (`model_temperature`, the exact nearest in-range temperature)
  and summarises it through `recommender.run`, the grid builder's own code, with
  `member_values(members=64)`. When a card's model window comes from model_c ≠ served, it
  says "aroma, taste and timings computed at …".
- **Window** (`window.compute`, mode proven): the target-averaged E, the off-notes O \\ C,
  t_safe = the P90 of `ph_below_4_6` where the profile has a pH safety line (else 0). With
  no targets, the peak shift uses the profile's **first** milestone as its main milestone.
  Sourdough cards hand off to the planner (Q31): their window is the levain peak's
  P10 / P50 / P90 from the grid (the planner's own engine), or the source when it is
  source-only.
- **Targets:** an aroma or taste series the engine does not produce for a ferment is absent
  from the grid; it scores 0 and the card says "not modelled for this ferment".
- **Ranking** (§ 5.4): E(peak) with targets, then the fewest ingredients to buy, provenance,
  profile confidence and the recipe key (a stable order).

Experimental (R2, design §§ 5.2–5.4, 6, 8.5, Q13, Q16, Q19):
- **Variants** of every active library recipe: 1 to 3 operators (recommender.operators)
  holding every must-include ingredient (one missing from the parent is added by (i) or (v),
  or swapped in, and counts toward the 3). Each passes `variant_gate` (the gate at every
  temperature the card can show, plus the operators' bounds). Temperature (Q26 kept): a
  variant without a temperature operator is served like its parent; one with it at the
  operator's temperature (inside the profile and the gate, outside the documented span),
  without a slider.
- **Statistics** from the grid (`screened_statistics`): one grid operator alone is its grid
  entry; two or three, or a (v) USDA food, are screened additively in logit space
  (recommender.screen) and the card says "screened" until the live forecast confirms it
  (`variant_forecast`, 64 members: "interaction detected" when the confirmed E(peak) is below
  0.8 × the screened one). Live forecasts are kept by fingerprint and appended to
  FERMENTTRACK_CANDIDATES_PATH as grid and emulator candidates (`log_candidate`).
- **Window** in mode experimental: up to 1.5 · d_hi, never before d_lo; the off-notes are O
  minus the parent's character, and the penalty λ Σ max(0, P_var − P_par) at the peak compares
  with the parent as its Proven card serves it.
- **Ranking**: U(peak) − penalty with targets, then the Proven keys, the fewest operators and
  the card id; the best variant per parent, 3 parents.
- **Own batch** (Q16): the user's batch as a parent (`own_parent`), at most 3 variants run
  live per request; its best leads the section.

Responses carry no timestamps and round every number, so a request and a grid give the same
JSON (E5). Scores show as Low / Med / High until the calibration gate (§ 13.2).
"""

from __future__ import annotations

import base64
import json
import logging
import math
import threading
from collections import OrderedDict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from functools import lru_cache
from types import MappingProxyType
from typing import Any, Literal

import numpy as np

from fermenttrack.config import settings
from fermenttrack.prediction import aroma, aroma_data, derived
from fermenttrack.prediction import service as engine
from fermenttrack.prediction.priors import FloatArray
from fermenttrack.prediction.profiles import PROFILES
from fermenttrack.prediction.sourdough import STYLES

# `run`: how a recipe runs and how a run becomes grid statistics, shared with the grid builder
# so a live forecast is computed the way its grid entry was. The only source of that logic.
from fermenttrack.recommender import gate, grid, library, operators, run, score, screen, window
from fermenttrack.recommender.library import Recipe, Span
from fermenttrack.recommender.operators import Operator
from fermenttrack.recommender.window import Window

logger = logging.getLogger(__name__)

MAX_TARGETS = 3
# The card's own koji line (gate.KOJI_TEMP_LINE): "up to 35 °C only with certified tane-koji".
# KOJI-001 sets no ceiling when certified spores are the only starter; this is that ceiling.
CERTIFIED_KOJI_MAX_C = 35.0
CARDS_PER_SECTION = 3
DEFAULT_BATCH_G = 1000.0
FORECAST_MEMBERS = 64  # the live per-card forecast (design § 10.1)
AROMA_SERIES: tuple[str, ...] = run.AROMA_SERIES
TASTES: tuple[str, ...] = tuple(derived.TASTES)
# Q7: a series summed from 2 compounds or fewer gets a "low resolution" badge.
LOW_RESOLUTION: frozenset[str] = frozenset(
    s
    for s in AROMA_SERIES
    if sum(
        1
        for c in aroma_data.COMPOUNDS.values()
        if s in c.series and c.status == "active" and c.threshold is not None
    )
    <= 2
)
PROVENANCE_RANK = {"institutional_tested": 0, "peer_reviewed": 1, "traditional_documented": 2}
CONFIDENCE_RANK = {"established": 0, "exploratory": 1}
CARD_LABELS = ("Model-guided idea", "model estimate, not validated")
NOT_MODELLED = "not modelled for this ferment"

Level = Literal["Low", "Med", "High"]


class RecommendationError(ValueError):
    """A request the recommender cannot serve (the router answers 404 or 422)."""


class UnknownRecipe(RecommendationError):
    pass


class GateRefused(RecommendationError):
    pass


# ── targets ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Target:
    key: str
    kind: Literal["aroma", "taste"]


def parse_targets(aromas: Iterable[str], tastes: Iterable[str]) -> tuple[Target, ...]:
    """The request's targets, in order, deduplicated: at most 3, from the 16 aroma series and
    the 4 tastes. Raises ValueError (a 422)."""
    out: dict[str, Target] = {}
    for key in aromas:
        if key not in AROMA_SERIES:
            raise ValueError(f"unknown aroma series {key!r}; one of {', '.join(AROMA_SERIES)}")
        out.setdefault(key, Target(key, "aroma"))
    for key in tastes:
        if key not in TASTES:
            raise ValueError(f"unknown taste {key!r}; one of {', '.join(TASTES)}")
        out.setdefault(key, Target(key, "taste"))
    if len(out) > MAX_TARGETS:
        raise ValueError(f"at most {MAX_TARGETS} target aromas and tastes in total")
    return tuple(out.values())


# ── temperature ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Temperature:
    served_c: float  # shown, booked and carried by a planner link (documented span, safe)
    recipe_c: float  # the recipe's median
    documented_c: tuple[float, float]  # the recipe's (lo, hi)
    slider_c: tuple[float, float] | None  # the safe documented range; None: a single point
    source_only: bool  # Q26: the window comes from the source alone
    notes: tuple[str, ...]


def source_only(recipe: Recipe, served_c: float) -> bool:
    """Q26 (design § 4.3): the model can't place time at a temperature it doesn't cover, so the
    window comes from the source alone when the served temperature is outside the profile's
    temp_range. The one place this is decided."""
    lo, hi = PROFILES[recipe.fermentation_type].temp_range
    return not lo <= served_c <= hi


def _tane_koji_cap(like: gate.RecipeLike) -> float:
    """The ceiling the gate leaves open: koji with certified tane-koji as the only starter.
    Other koji stop at 33 °C in the gate itself (KOJI-001)."""
    certified = set(like.starters) == {gate.CERTIFIED_KOJI_STARTER}
    return CERTIFIED_KOJI_MAX_C if like.fermentation_type == "koji" and certified else math.inf


def _safe_span(like: gate.RecipeLike, lo: float, hi: float) -> tuple[float, float] | None:
    """The part of [lo, hi] that passes the gate and the tane-koji ceiling (None if empty).
    The gate's temperature rules are thresholds, so the passing set is an interval whose
    ends are lo, hi or a threshold; gate.check decides."""
    hi = min(hi, _tane_koji_cap(like))
    if lo > hi:
        return None
    probe = replace(like, temperatures_c=())
    cuts = (gate.LACTIC_MAX_C, gate.KOJI_MIN_C, gate.KOJI_MAX_C)
    ends = sorted({lo, hi, *(c for c in cuts if lo < c < hi)})
    passing = [t for t in ends if gate.check(probe, [t]).ok]
    return (passing[0], passing[-1]) if passing else None


def resolve_temperature(recipe: Recipe, requested_c: float | None) -> Temperature:
    """The card's temperature; every route (cards, live forecast, Start batch) takes it from
    here. Served = the user's temperature, else the median, clamped to the documented span
    and to the safety limits (_safe_span), never to the profile range: outside it the card is
    source-only and the model works at model_temperature."""
    if recipe.temp_c is None:  # active recipes always have one (library validation)
        raise RecommendationError(f"{recipe.key} has no documented temperature")
    span = recipe.temp_c
    asked = None if requested_c is None else round(requested_c, 1)
    source = span.median if asked is None else min(max(asked, span.lo), span.hi)
    safe = _safe_span(gate.from_recipe(recipe), span.lo, span.hi)
    served = source if safe is None else min(max(source, safe[0]), safe[1])  # None: refused
    notes: list[str] = []
    if served != source:
        side = "above" if served < source else "below"
        notes.append(
            f"{source if asked is None else asked:g} °C is {side} the safety limit for this "
            f"recipe; shown at {served:g} °C"
        )
    elif asked is not None and source != asked:
        notes.append(
            f"your temperature is outside this recipe's documented range; shown at {served:g} °C"
        )
    slider = safe if safe and safe[0] < safe[1] else None
    return Temperature(
        served, span.median, (span.lo, span.hi), slider, source_only(recipe, served), tuple(notes)
    )


def card_schedule(
    recipe: Recipe, temp: Temperature, requested_c: float | None
) -> tuple[tuple[float, float], ...]:
    """A staged recipe as shown and booked: the source's stages, the first moved to the
    served temperature when the user asked for one (Q27: the what-if shifts the first stage
    only); () when constant. The model runs run.planned_schedule at the model temperature."""
    if not recipe.temp_schedule or requested_c is None:
        return recipe.temp_schedule
    (h0, _), *later = recipe.temp_schedule
    return ((h0, temp.served_c), *later)


def check_gate(recipe: Recipe, temp: Temperature) -> gate.GateResult:
    """The gate at every temperature the card can show (its own median and stages, the served
    one, both slider ends), plus the tane-koji ceiling the gate leaves open."""
    like = gate.from_recipe(recipe)
    temps = [temp.served_c, *(temp.slider_c or ())]
    result = gate.check(like, temps)
    cap = _tane_koji_cap(like)
    over = [t for t in sorted({*like.temperatures_c, *temps}) if t > cap]
    if not over:
        return result
    why = tuple(f"tane-koji: {t:g} °C > {cap:g} °C, the card's own limit" for t in over)
    return replace(result, ok=False, reasons=(*result.reasons, *why))


# ── statistics: the grid, or a live forecast with the grid's schema ─────


def live_statistics(recipe: Recipe, model_c: float, members: int | None) -> grid.Entry:
    """A live forecast summarised with the grid's statistics on the grid's time axis (E / U / P
    per series, milestone P10 / P50 / P90), the way the grid builder's run_entry does it
    (recommender.run). members=None is the grid's own ensemble. Card labels (top compounds,
    ingredients without aroma data) come from the grid at the same temperature."""
    rg = grid.recipe(recipe.key)
    t_dst = grid.entry(recipe.key, rg.temps[0]).t_h
    inputs = run.prediction_inputs(recipe, model_c)
    t, values, w = engine.member_values(inputs, rg.end_h, members=members)
    stats, present = run.series_statistics(t, values, w, t_dst)
    kept = [(j, s) for j, s in enumerate(run.SERIES) if present[j]]
    e, u, p = (MappingProxyType({s: stats[k, j] for j, s in kept}) for k in range(3))
    milestones = {
        m.key: grid.MilestoneTimes(*run.summarise_times(c, w))
        for m in run.milestones_for(PROFILES[recipe.fermentation_type])
        if (c := run.crossing_times(m, t, values)) is not None
    }
    labels = grid.interp_temp(recipe.key, model_c)
    return grid.Entry(
        recipe_key=recipe.key, temp_c=model_c, t_h=t_dst, e=e, u=u, p=p,
        milestones=MappingProxyType(milestones), members=len(w),
        schedule=inputs.planned_temperature, top_compound=labels.top_compound,
        not_modelled=labels.not_modelled, skipped=labels.skipped,
    )  # fmt: skip


@lru_cache(maxsize=32)
def _live(recipe_key: str, model_c: float, members: int) -> grid.Entry:
    """Live statistics per (recipe, °C, members), kept: a slider position asked twice answers
    the same. The engine resamples a posterior it still holds, so an evicted entry recomputed
    can differ within the ensemble's noise."""
    recipe = library.get(recipe_key)
    assert recipe is not None
    return live_statistics(recipe, model_c, members)


def model_temperature(recipe: Recipe, served_c: float) -> float:
    """The live forecast's temperature (Q26): the served temperature clamped to the profile's
    temp_range, the exact nearest temperature the model covers. Safe by construction: the
    served temperature passes the gate, and so does any profile temperature between it and
    the profile's bounds. Cards read the grid instead (grid.interp_temp clamps to the recipe's
    grid temperatures)."""
    lo, hi = PROFILES[recipe.fermentation_type].temp_range
    return min(max(served_c, lo), hi)


# ── evaluation: window and scores at one temperature ────────────────────


@dataclass(frozen=True)
class TargetScore:
    target: Target
    modelled: bool
    e: float  # E at the peak (0 when not modelled)
    u: float
    top_compound: tuple[str, str] | None  # (compound key, evidence tier)

    @property
    def level(self) -> Level | None:
        return score.low_med_high(self.e) if self.modelled else None


@dataclass(frozen=True)
class Evaluation:
    window: Window | None
    basis: Literal["model", "source", "planner"]
    peak_h: float  # where the scores are read
    targets: tuple[TargetScore, ...]
    e: float | None  # the target-averaged E(peak); None without targets
    u: float | None  # the mean of per-target U(peak): optimistic, an approximation (§ 8.1)
    notes: tuple[str, ...]
    penalty: float = 0.0  # Experimental: the parent-relative off-note penalty at the peak
    rising: tuple[str, ...] = ()  # the off-notes behind it (more likely noticeable than the parent)


@dataclass(frozen=True)
class Basis:
    """What a window is measured against: the documented duration (lo, med, hi), the profile
    horizon and the median time to the profile's main milestone at the recipe's own
    temperature (the no-target peak shift). From the grid for library recipes."""

    duration_h: tuple[float, float, float] | None
    horizon_h: float
    m_source_h: float | None


@dataclass(frozen=True)
class Reference:
    """An Experimental variant's parent as served (design § 5.3): its character series C (the
    reported aromas plus every series with P ≥ 0.5 at d_med, or at the grid end before it) and
    its P per series on the same time axis, for the parent-relative off-note penalty."""

    character: frozenset[str]
    p: Mapping[str, FloatArray]


def _main_milestone(recipe: Recipe) -> str:
    return PROFILES[recipe.fermentation_type].milestones[0].key


def grid_basis(recipe: Recipe, recipe_c: float) -> Basis:
    rg = grid.recipe(recipe.key)
    m = grid.interp_temp(recipe.key, recipe_c).milestones.get(_main_milestone(recipe))
    return Basis(rg.duration_h, rg.horizon_h, m.p50 if m else None)


def character(recipe: Recipe, stats: grid.Entry, d_med: float | None) -> frozenset[str]:
    t = stats.t_h
    at = float(t[-1]) if d_med is None else min(d_med, float(t[-1]))
    return score.character_series(
        recipe.reported_aromas, {s: _at(t, v, at) for s, v in stats.p.items()}
    )


def _at(t: FloatArray, v: FloatArray, x: float) -> float:
    return float(np.interp(x, t, v))  # clamped at the ends: past the grid, its last value


def _scores(
    stats: grid.Entry, targets: Sequence[Target], peak_h: float
) -> tuple[tuple[TargetScore, ...], float | None, float | None]:
    out = []
    for tg in targets:
        modelled = tg.key in stats.e
        e = _at(stats.t_h, stats.e[tg.key], peak_h) if modelled else 0.0
        u = _at(stats.t_h, stats.u[tg.key], peak_h) if modelled else 0.0
        top = stats.top_compound.get(tg.key) if modelled else None
        out.append(TargetScore(tg, modelled, e, u, top))
    if not out:
        return (), None, None
    return tuple(out), float(np.mean([s.e for s in out])), float(np.mean([s.u for s in out]))


def source_note(recipe: Recipe, temp: Temperature, model_c: float) -> str:
    """The note on a source-only window (Q26): whose timings these are (the documented span
    within the safety limits: koji 27–35 °C, not the source's 27–40), what the model covers
    and where the aroma levels come from."""
    lo, hi = temp.slider_c or (temp.served_c, temp.served_c)
    p_lo, p_hi = PROFILES[recipe.fermentation_type].temp_range
    at = f"{lo:g} °C" if lo == hi else f"{lo:g}–{hi:g} °C"
    return (
        f"timings from the source at {at} (the model covers {p_lo:g}–{p_hi:g} °C); aroma "
        f"levels are computed at {model_c:g} °C"
    )


def _sourdough_window(
    recipe: Recipe, stats: grid.Entry, temp: Temperature
) -> tuple[Window | None, Literal["source", "planner"], tuple[str, ...]]:
    """Q31: the planner's levain peak (P10 / P50 / P90), or the source when source-only
    (Q26)."""
    d = recipe.duration_h
    if temp.source_only and d is not None:
        note = source_note(recipe, temp, stats.temp_c)
        return Window(d.lo, d.median, d.hi, (note,)), "source", ()
    peak = stats.milestones.get(grid.LEVAIN_PEAK)
    if peak is None or not all(math.isfinite(x) for x in (peak.p10, peak.p50, peak.p90)):
        return None, "planner", ("the planner could not place the levain peak here",)
    note = "levain peak from the planner's model (P10 to P90): watch the dough, not only the clock"
    return Window(peak.p10, peak.p50, peak.p90, (note,)), "planner", ()


def evaluate(
    recipe: Recipe,
    stats: grid.Entry,
    temp: Temperature,
    targets: Sequence[Target],
    *,
    clip: bool = True,
    mode: Literal["proven", "experimental"] = "proven",
    reference: Reference | None = None,
    basis: Basis | None = None,
) -> Evaluation:
    """The card's window and scores from one set of statistics (a grid entry, interpolated,
    screened, or a live forecast). clip=False is the model's own window (E3). Experimental
    (design §§ 5.3, 6): the window may run to 1.5 · d_hi, the off-notes are O minus the
    parent's character (reference) and the penalty is λ Σ max(0, P_var − P_par) at the peak.
    basis: the recipe's duration and horizon (default: its grid recipe)."""
    if basis is None:
        basis = grid_basis(recipe, temp.recipe_c)
    t = stats.t_h
    notes = [f"{tg.key}: {NOT_MODELLED}" for tg in targets if tg.key not in stats.e]
    keys = [tg.key for tg in targets]
    d_med = basis.duration_h[1] if basis.duration_h else None
    chars = reference.character if reference else character(recipe, stats, d_med)
    offs = score.off_note_series(keys, chars)
    basis_kind: Literal["model", "source", "planner"]
    if recipe.handoff == "planner":
        win, basis_kind, extra = _sourdough_window(recipe, stats, temp)
        notes += extra
        peak = win.peak_h if win else (d_med if d_med is not None else float(t[-1]))
    else:
        if basis.duration_h is None:
            raise RecommendationError(f"{recipe.key} has no documented duration")
        zeros = np.zeros_like(t)
        e = score.target_average({k: stats.e.get(k, zeros) for k in keys}, keys) if keys else None
        off = {o: stats.p[o] for o in offs if o in stats.p}
        safety = stats.milestones.get(grid.SAFETY_MILESTONE)
        m_user = stats.milestones.get(_main_milestone(recipe))
        win = window.compute(
            t, e, off, safety.p90 if safety else 0.0, basis.duration_h, basis.horizon_h, mode,
            m_user_h=m_user.p50 if m_user else None, m_source_h=basis.m_source_h,
            model_scope=recipe.model_scope, clip=clip, source_only=temp.source_only,
        )  # fmt: skip
        if temp.source_only:  # name the temperatures behind the source's timings
            specific = source_note(recipe, temp, stats.temp_c)
            win = replace(win, notes=tuple(
                specific if n == window.SOURCE_ONLY_NOTE else n for n in win.notes
            ))  # fmt: skip
        basis_kind = "source" if temp.source_only else "model"
        peak = win.peak_h
    scores, e_peak, u_peak = _scores(stats, targets, peak)
    penalty = 0.0
    rising: tuple[str, ...] = ()
    if mode == "experimental" and reference is not None:
        var_p = {o: _at(t, stats.p[o], peak) for o in offs if o in stats.p}
        par_p = {o: _at(t, reference.p[o], peak) for o in offs if o in reference.p}
        penalty = score.off_note_penalty(var_p, par_p, keys, chars)
        rising = tuple(o for o in sorted(var_p) if var_p[o] > par_p.get(o, 0.0))
    return Evaluation(
        win, basis_kind, peak, scores, e_peak, u_peak, tuple(notes), penalty, rising
    )


# ── cards ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Card:
    recipe: Recipe  # the served recipe: the library recipe, or the variant
    temperature: Temperature
    schedule: tuple[tuple[float, float], ...]
    model_c: float
    evaluation: Evaluation
    safety_lines: tuple[str, ...]
    batch_g: float
    to_buy: tuple[str, ...]
    not_modelled: tuple[str, ...]
    notes: tuple[str, ...]
    variant: Variant | None = None  # Experimental: the parent and its operators
    screened: bool = False  # Experimental: combined additively from single-operator entries


def to_buy(recipe: Recipe, listed: Iterable[str]) -> tuple[str, ...]:
    """Core ingredients that are neither staples nor in the user's list (§ 5.4 key 2)."""
    have = set(listed) | library.STAPLES
    core = (i.name for i in recipe.ingredients if i.required == "core")
    return tuple(dict.fromkeys(n for n in core if n not in have))


def must_include(listed: Iterable[str]) -> tuple[str, ...]:
    """The must-include ingredients (design § 5.2, Q3): the user's list, staples aside. Staples
    are always allowed and never exclude a recipe, listed or not."""
    return tuple(dict.fromkeys(n for n in listed if n not in library.STAPLES))


def contains(recipe: Recipe, ingredients: Iterable[str]) -> bool:
    """Every must-include ingredient is a row of the recipe."""
    return set(must_include(ingredients)) <= {i.name for i in recipe.ingredients}


def build_card(
    recipe: Recipe,
    targets: Sequence[Target],
    temperature_c: float | None,
    batch_g: float = DEFAULT_BATCH_G,
    listed: Iterable[str] = (),
) -> tuple[Card | None, gate.GateResult]:
    """One Proven card from the grid, or None when the gate refuses it."""
    temp = resolve_temperature(recipe, temperature_c)
    result = check_gate(recipe, temp)
    if not result.ok:
        return None, result
    stats = grid.interp_temp(recipe.key, temp.served_c)
    ev = evaluate(recipe, stats, temp, targets)
    card = Card(
        recipe=recipe, temperature=temp, schedule=card_schedule(recipe, temp, temperature_c),
        model_c=stats.temp_c, evaluation=ev, safety_lines=result.safety_lines, batch_g=batch_g,
        to_buy=to_buy(recipe, listed), not_modelled=stats.not_modelled,
        notes=(*temp.notes, *_model_note(stats.temp_c, temp, PRECOMPUTED), *ev.notes),
    )  # fmt: skip
    return card, result


PRECOMPUTED = "the nearest precomputed temperature"  # a card: the recipe's grid temperatures
IN_RANGE = "the nearest temperature the model covers"  # the live forecast: the profile range


def _model_note(model_c: float, temp: Temperature, nearest: str) -> tuple[str, ...]:
    """Where the model window and scores come from, when not the served temperature (a
    source-only window says it in its own note)."""
    if temp.source_only or abs(model_c - temp.served_c) <= 1e-9:
        return ()
    return (f"aroma, taste and timings computed at {model_c:g} °C, {nearest}",)


def rank_key(card: Card) -> tuple[float, int, int, int, str]:
    """§ 5.4 Proven: E(peak) when there are targets, the fewest to buy, provenance, profile
    confidence; the key last, for a stable order."""
    r = card.recipe
    e = card.evaluation.e
    return (
        -(e if e is not None else 0.0),
        len(card.to_buy),
        PROVENANCE_RANK.get(r.provenance, len(PROVENANCE_RANK)),
        CONFIDENCE_RANK.get(PROFILES[r.fermentation_type].confidence, len(CONFIDENCE_RANK)),
        r.key,
    )


def proven_cards(
    ingredients: Sequence[str],
    targets: Sequence[Target],
    temperature_c: float | None,
    batch_g: float = DEFAULT_BATCH_G,
) -> tuple[list[Card], list[tuple[str, tuple[str, ...]]]]:
    """(the ranked cards, at most 3; the gated-out recipes with the gate's reasons)."""
    cards: list[Card] = []
    refused: list[tuple[str, tuple[str, ...]]] = []
    for recipe in library.active():
        if not contains(recipe, ingredients):
            continue
        card, result = build_card(recipe, targets, temperature_c, batch_g, ingredients)
        if card is None:
            refused.append((recipe.key, result.reasons))
        else:
            cards.append(card)
    cards.sort(key=rank_key)  # one card per parent: each library recipe is its own parent
    return cards[:CARDS_PER_SECTION], refused


# ── Experimental: variants (design §§ 5.2–5.4, 6, 8.5, 10.1; Q13, Q16, Q19) ──

SCREENED = "screened"
SCREENED_NOTE = (
    "screened: combined from single-change forecasts; open the forecast to confirm it"
)
INTERACTION = "interaction detected"
INTERACTION_RATIO = 0.8  # design § 8.5: confirmed E(peak) < 0.8 × the screened value
OWN_BATCH_VARIANTS = 3  # Q16: live forecasts per request
OWN_BATCH_PROVENANCE = "your_batch"
LIVE_CACHE = 128  # live variant forecasts kept in process, by input fingerprint


class OperatorRefused(RecommendationError):
    """Operators the parent does not allow (a 422)."""


@dataclass(frozen=True)
class Parent:
    """An Experimental parent: an active library recipe, or the user's own batch (Q16) as a
    recipe (key "batch:<id>", no grid entry: its basis comes with it)."""

    recipe: Recipe
    kind: Literal["library", "own_batch"]
    label: str  # the recipe's name, or "your batch #n"
    batch_id: str | None = None
    basis: Basis | None = None  # own batch; library parents read the grid


@dataclass(frozen=True)
class OperatorRequest:
    """An operator as a client names it (a card's operator chip sent back): resolved against
    the parent's own operator catalogue, never trusted (shares come from the server)."""

    kind: operators.Kind
    ingredient: str | None = None
    replaces: str | None = None
    to_c: float | None = None
    fdc_id: int | None = None

    @property
    def key(self) -> str:
        to_c = None if self.to_c is None else round(float(self.to_c), 1)
        ingredient = None if self.fdc_id is not None else self.ingredient
        return Operator(self.kind, ingredient, self.replaces, None, to_c, self.fdc_id).key


@dataclass(frozen=True)
class Variant:
    parent: Parent
    operators: tuple[Operator, ...]  # sorted (operators.sort_key)
    recipe: Recipe  # the parent with the operators applied

    @property
    def key(self) -> str:
        return "+".join(op.key for op in self.operators)

    @property
    def id(self) -> str:
        p = self.parent
        if p.kind == "own_batch":
            return f"own_batch:{p.batch_id}:{self.key}"
        return f"variant:{p.recipe.key}:{self.key}"

    @property
    def source_kind(self) -> Literal["variant", "own_batch"]:
        return "own_batch" if self.parent.kind == "own_batch" else "variant"

    @property
    def link_key(self) -> str:
        """recommendation_links.recipe_key: the library recipe, or "batch:<id>"."""
        return self.parent.recipe.key

    @property
    def temperature_op(self) -> Operator | None:
        return next((op for op in self.operators if op.kind == "temperature"), None)

    @property
    def screened(self) -> bool:
        """A library variant read from the grid by additive screening: two or more operators,
        or a (v) USDA food (no grid entry: its term is 0 until confirmed). Own-batch variants
        are live forecasts."""
        if self.parent.kind != "library":
            return False
        return len(self.operators) >= 2 or any(op.kind == "usda" for op in self.operators)


def make_variant(parent: Parent, ops: Sequence[Operator]) -> Variant:
    """Raises OperatorRefused when the operators cannot be applied together."""
    ordered = tuple(sorted(ops, key=operators.sort_key))
    try:
        return Variant(parent, ordered, operators.apply(parent.recipe, ordered))
    except operators.OperatorError as exc:
        raise OperatorRefused(str(exc)) from None


def available_operators(
    parent: Parent,
    temperature_c: float | None = None,
    must_include: Iterable[str] = (),
    usda_ids: Iterable[int] = (),
) -> tuple[Operator, ...]:
    """The parent's single operators (operators.singles) the recommender can serve: for a
    library parent, (i) and (ii) only where the grid holds them."""
    temps = () if temperature_c is None else (temperature_c,)
    ops = operators.singles(
        parent.recipe, temperatures=temps, must_include=must_include, usda_ids=usda_ids
    )
    if parent.kind != "library":
        return ops
    key = parent.recipe.key
    held = set(grid.operators(key))
    return tuple(
        op for op in ops
        if op.kind not in ("add", "swap") or (op.key in held and grid.temps(key, op.key))
    )  # fmt: skip


def resolve_operators(parent: Parent, requests: Sequence[OperatorRequest]) -> tuple[Operator, ...]:
    """The server's own operators for a client's request. Raises OperatorRefused."""
    if not 1 <= len(requests) <= operators.MAX_OPERATORS:
        raise OperatorRefused(f"a variant has 1 to {operators.MAX_OPERATORS} operators")
    temps = [r.to_c for r in requests if r.kind == "temperature" and r.to_c is not None]
    # a client-named (v) food is a must-include ingredient: never a staple (must_include)
    names = must_include(
        [r.ingredient for r in requests if r.kind == "usda" and r.fdc_id is None and r.ingredient]
    )
    ids = [r.fdc_id for r in requests if r.kind == "usda" and r.fdc_id is not None]
    allowed: dict[str, Operator] = {}
    asked: list[float | None] = [*temps] or [None]
    for t in asked:
        allowed |= {op.key: op for op in available_operators(parent, t, names, ids)}
    out = []
    for r in requests:
        if r.key not in allowed:
            raise OperatorRefused(f"{r.key}: not an operator {parent.label} allows")
        out.append(allowed[r.key])
    if not operators.compatible(out):
        raise OperatorRefused("operators overlap: one temperature change, disjoint ingredients")
    return tuple(sorted(out, key=operators.sort_key))


def _names_after(names: set[str], ops: Iterable[Operator]) -> set[str]:
    out = set(names)
    for op in ops:
        if op.replaces:
            out.discard(op.replaces)
        if op.ingredient:
            out.add(op.ingredient)
    return out


def covers(parent: Recipe, ops: Iterable[Operator], must: Iterable[str]) -> bool:
    """Every must-include ingredient is a row of the variant (design § 5.2: one missing from
    the parent is added by (i) or (v), or swapped in, and counts toward the 3)."""
    return set(must) <= _names_after({i.name for i in parent.ingredients}, ops)


def variant_temperature(v: Variant, requested_c: float | None) -> Temperature:
    """Q26 for a variant: without a temperature operator, the parent's rule
    (resolve_temperature: the documented span within the safety limits); with one, served at
    the operator's temperature (inside the profile's range and the gate, outside the
    documented span) with no slider."""
    op = v.temperature_op
    if op is None or op.to_c is None:
        return resolve_temperature(v.recipe, requested_c)
    span = v.parent.recipe.temp_c
    assert span is not None  # operators.singles only offers (iii) with a documented span
    notes: tuple[str, ...] = ()
    if requested_c is not None and round(requested_c, 1) != op.to_c:
        notes = (f"this idea changes the temperature to {op.to_c:g} °C",)
    return Temperature(
        op.to_c, span.median, (span.lo, span.hi), None, source_only(v.recipe, op.to_c), notes
    )


def variant_gate(v: Variant, temp: Temperature) -> gate.GateResult:
    """The gate at every temperature the card can show (check_gate) plus the operators' own
    bounds (design § 7, "also gated")."""
    result = check_gate(v.recipe, temp)
    why = tuple(operators.bounds_reasons(v.parent.recipe, v.operators))
    return replace(result, ok=False, reasons=(*result.reasons, *why)) if why else result


def screened_statistics(v: Variant, temp: Temperature) -> grid.Entry:
    """A library variant's statistics from the grid (design § 8.5): the parent read at the
    served temperature (with a temperature operator, on its axis: the grid temperatures plus
    the temperature operators'), plus each (i) / (ii) operator's difference read at the model
    temperature clamped to that operator's grid temperatures, interpolated there like for like
    (the operator's entry and the parent's); (v) adds 0. One (i) / (ii) operator alone is its
    grid entry, exact. The entry's temp_c is the model temperature."""
    key = v.parent.recipe.key
    t_op = v.temperature_op
    comps = [op for op in v.operators if op.kind in ("add", "swap")]
    if not comps:
        if t_op is not None:
            return grid.interp_axis(key, temp.served_c)
        return grid.interp_temp(key, temp.served_c)
    if len(v.operators) == 1:
        return grid.interp_temp(key, temp.served_c, comps[0].key)
    keys = tuple(run.SERIES)
    version = grid.version()
    base, base_logits = _grid_logits(version, key, temp.served_c, None, t_op is not None, keys)
    diffs, variants = [], []
    for op in comps:
        temps = grid.temps(key, op.key)
        c = min(max(base.temp_c, temps[0]), temps[-1])
        entry, diff = _grid_difference(version, key, op.key, c, keys)
        variants.append(entry)
        diffs.append(diff)
    return screen.assemble(base, base_logits, diffs, variants)


@lru_cache(maxsize=4096)
def _grid_logits(
    version: str, key: str, temp_c: float, operator: str | None, axis: bool,
    series: tuple[str, ...],
) -> tuple[grid.Entry, screen.Logits]:  # fmt: skip
    """A grid entry (interpolated; on the recipe's axis when `axis`) and its logits. Keyed by
    the grid version: screening many combinations reuses them."""
    entry = grid.interp_axis(key, temp_c) if axis else grid.interp_temp(key, temp_c, operator)
    return entry, screen.logits(entry, series)


@lru_cache(maxsize=4096)
def _grid_difference(
    version: str, key: str, operator: str, temp_c: float, series: tuple[str, ...]
) -> tuple[grid.Entry, screen.Logits]:
    """(the operator's entry, its logit difference from the parent) at one grid temperature."""
    entry, with_op = _grid_logits(version, key, temp_c, operator, False, series)
    _, without = _grid_logits(version, key, temp_c, None, False, series)
    return entry, screen.difference(with_op, without)


def library_reference(parent: Recipe, temperature_c: float | None) -> Reference:
    """The parent as its Proven card serves it (same temperature rule), on the grid."""
    temp = resolve_temperature(parent, temperature_c)
    stats = grid.interp_temp(parent.key, temp.served_c)
    d = grid.recipe(parent.key).duration_h
    return Reference(character(parent, stats, d[1] if d else None), stats.p)


def not_modelled(recipe: Recipe) -> tuple[str, ...]:
    """The recipe's ingredients without aroma data (the grid's own rule)."""
    if recipe.handoff == "planner":
        return ()
    rows = run.recipe_rows(recipe)[0]
    items = [(r.name, r.quantity, r.role) for r in rows]
    return tuple(aroma.ingredient_shares(items, recipe.fermentation_type)[1])


def variant_card(
    v: Variant,
    targets: Sequence[Target],
    temperature_c: float | None,
    batch_g: float,
    listed: Iterable[str],
    reference: Reference | None,
    *,
    stats: grid.Entry | None = None,
) -> tuple[Card | None, gate.GateResult]:
    """One Experimental card, or None when the gate or the operator bounds refuse it. stats:
    a live forecast (own batch, a confirmation); default: the grid (screened_statistics)."""
    temp = variant_temperature(v, temperature_c)
    result = variant_gate(v, temp)
    if not result.ok:
        return None, result
    live = stats is not None
    if stats is None:
        stats = screened_statistics(v, temp)
    basis = v.parent.basis or grid_basis(v.parent.recipe, temp.recipe_c)
    ev = evaluate(
        v.recipe, stats, temp, targets, mode="experimental", reference=reference, basis=basis
    )
    nearest = IN_RANGE if live else PRECOMPUTED
    notes = [*temp.notes, *_model_note(stats.temp_c, temp, nearest), *ev.notes]
    if v.parent.kind == "own_batch" and v.parent.recipe.notes:
        notes.append(v.parent.recipe.notes)  # e.g. a batch still running: typical timings
    if ev.rising:
        notes.append(f"{', '.join(ev.rising)}: likely more noticeable than in {v.parent.label}")
    screened = v.screened and not live
    if screened:
        notes.append(SCREENED_NOTE)
    requested = None if v.temperature_op else temperature_c
    card = Card(
        recipe=v.recipe, temperature=temp, schedule=card_schedule(v.recipe, temp, requested),
        model_c=stats.temp_c, evaluation=ev, safety_lines=result.safety_lines, batch_g=batch_g,
        to_buy=to_buy(v.recipe, listed), not_modelled=not_modelled(v.recipe),
        notes=tuple(notes), variant=v, screened=screened,
    )  # fmt: skip
    return card, result


def experimental_rank_key(card: Card) -> tuple[float, int, int, int, int, str]:
    """§ 5.4 Experimental: U(peak) − penalty with targets, then the fewest to buy, provenance,
    profile confidence; then the fewest operators and the card id, for a stable order."""
    v = card.variant
    assert v is not None
    ev = card.evaluation
    r = v.parent.recipe
    return (
        -(ev.u - ev.penalty if ev.u is not None else 0.0),
        len(card.to_buy),
        PROVENANCE_RANK.get(r.provenance, len(PROVENANCE_RANK)),
        CONFIDENCE_RANK.get(PROFILES[r.fermentation_type].confidence, len(CONFIDENCE_RANK)),
        len(v.operators),
        v.id,
    )


def _combos(
    parent: Parent, listed: Sequence[str], temperature_c: float | None, usda_ids: Sequence[int]
) -> list[tuple[Operator, ...]]:
    """The parent's operator combinations (up to 3) that contain every must-include
    ingredient."""
    must = must_include(listed)
    names = {i.name for i in parent.recipe.ingredients}
    missing = [n for n in must if n not in names]
    ops = available_operators(parent, temperature_c, missing, usda_ids)
    if any(all(op.ingredient != n for op in ops) for n in missing):
        return []
    return [c for c in operators.combinations(ops) if covers(parent.recipe, c, must)]


EXACT_PER_PARENT = 4  # combinations per parent scored exactly after the vectorised pre-ranking


def _prerank(
    parent: Parent,
    combos: Sequence[tuple[Operator, ...]],
    targets: Sequence[Target],
    temperature_c: float | None,
    reference: Reference,
) -> list[int]:
    """The combinations' indices, best first, by an approximation of § 5.4's score computed
    for all of them at once: screened E, U and P on the grid's time knots (the exact screening
    sums, vectorised), the window's peak on those knots (taste from max(d_lo, t_safe); stop at
    the first off-note P ≥ 0.5; the source's d_med when source-only; the levain peak for
    sourdough) and U(peak) − penalty. best_variant then scores the first few exactly."""
    key = parent.recipe.key
    rg = grid.recipe(key)
    keys = [t.key for t in targets]
    offs = sorted(score.off_note_series(keys, reference.character))
    series = tuple(dict.fromkeys((*keys, *offs)))
    version = grid.version()
    planner = parent.recipe.handoff == "planner"
    approx = np.full(len(combos), -np.inf)
    groups: dict[float | None, list[int]] = {}
    for i, combo in enumerate(combos):
        t_op = next((op for op in combo if op.kind == "temperature"), None)
        groups.setdefault(None if t_op is None else t_op.to_c, []).append(i)
    for to_c, members in groups.items():
        if to_c is None:
            served = resolve_temperature(parent.recipe, temperature_c).served_c
        else:
            served = to_c
        base, base_lg = _grid_logits(version, key, served, None, to_c is not None, series)
        t = base.t_h
        ops = sorted({op.key: op for i in members for op in combos[i]
                      if op.kind in ("add", "swap")}.values(), key=operators.sort_key)  # fmt: skip
        pos = {op.key: j for j, op in enumerate(ops)}
        diffs, entries = [], []
        for op in ops:
            temps = grid.temps(key, op.key)
            entry, diff = _grid_difference(
                version, key, op.key, min(max(base.temp_c, temps[0]), temps[-1]), series
            )
            entries.append(entry)
            diffs.append(diff)
        stack = np.zeros((len(ops) + 1, 3, len(series), len(t)))  # the last row: no operator
        for j, d in enumerate(diffs):
            for k, stat in enumerate(screen.STATS):
                for s_i, s in enumerate(series):
                    if s in d[stat]:
                        stack[j, k, s_i] = d[stat][s]
        b = np.array([[base_lg[stat].get(s, np.full(len(t), -screen.CLIP)) for s in series]
                      for stat in screen.STATS])  # fmt: skip
        idx = np.full((len(members), operators.MAX_OPERATORS), len(ops))
        for row, i in enumerate(members):
            comp = [pos[op.key] for op in combos[i] if op.key in pos]
            idx[row, : len(comp)] = comp
        values = screen.expit(np.clip(b[None] + stack[idx].sum(axis=1), -screen.CLIP, screen.CLIP))
        u = values[:, 1, : len(keys)].mean(axis=1)  # (combos, times)
        e = values[:, 0, : len(keys)].mean(axis=1)
        p_off = values[:, 2, len(keys) :]  # (combos, off-notes, times)
        def latest(per_entry: FloatArray, i: int, pos: dict[str, int] = pos) -> float:
            """The latest over the parent's entry and the combination's operators'."""
            return float(max([per_entry[0], *(per_entry[1 + pos[op.key]] for op in combos[i]
                                              if op.key in pos)]))  # fmt: skip

        safe_ms = [m.milestones.get(grid.SAFETY_MILESTONE) for m in (base, *entries)]
        safe = np.array([m.p90 if m else 0.0 for m in safe_ms])
        t_safe = np.array([latest(safe, i) for i in members])
        model_end = min(rg.horizon_h, float(t[-1]))
        t_safe = np.where(np.isfinite(t_safe), t_safe, model_end)
        if planner:
            peak_ms = [m.milestones.get(grid.LEVAIN_PEAK) for m in (base, *entries)]
            p50 = np.array([m.p50 if m else model_end for m in peak_ms])
            peak_t = np.array([latest(p50, i) for i in members])
        elif source_only(parent.recipe, served) and rg.duration_h is not None:
            peak_t = np.full(len(members), rg.duration_h[1])
        else:
            assert rg.duration_h is not None
            d_lo, _, d_hi = rg.duration_h
            end = min(window.EXPERIMENTAL_CEILING * d_hi, model_end)
            start = np.maximum(d_lo, t_safe)
            inside = (t[None, :] >= start[:, None] - 1e-9) & (t[None, :] <= end + 1e-9)
            off_hit = inside & (p_off >= window.OFF_NOTE_P).any(axis=1)
            first_off = np.where(off_hit.any(axis=1), off_hit.argmax(axis=1), len(t))
            masked = np.where(inside, e, -np.inf)
            peak_i = masked.argmax(axis=1)
            early = first_off < peak_i
            before = np.where(np.arange(len(t))[None, :] <= first_off[:, None], masked, -np.inf)
            peak_i = np.where(early, before.argmax(axis=1), peak_i)
            peak_t = np.where(inside.any(axis=1), t[peak_i], start)
        rise = np.zeros(len(members))
        p_at = _interp_rows(t, p_off, peak_t)  # (combos, off-notes)
        for o_i, o in enumerate(offs):
            par = np.interp(peak_t, t, reference.p[o]) if o in reference.p else 0.0
            rise += np.maximum(0.0, p_at[:, o_i] - par)
        approx[members] = _interp_rows(t, u, peak_t) - score.LAMBDA * rise
    return sorted(range(len(combos)), key=lambda i: (-approx[i], len(combos[i]),
                                                     [op.key for op in combos[i]]))  # fmt: skip


def _interp_rows(t: FloatArray, v: FloatArray, x: FloatArray) -> FloatArray:
    """Row r of v, (rows, times) or (rows, k, times), linear in time at x[r], clamped at the
    ends like np.interp."""
    j = np.clip(np.searchsorted(t, x, side="right"), 1, len(t) - 1)
    f = np.clip((x - t[j - 1]) / (t[j] - t[j - 1]), 0.0, 1.0)
    r = np.arange(len(x))
    if v.ndim == 2:
        return np.asarray(v[r, j - 1] * (1.0 - f) + v[r, j] * f, dtype=np.float64)
    g = f[:, None]
    return np.asarray(v[r, :, j - 1] * (1.0 - g) + v[r, :, j] * g, dtype=np.float64)


def best_variant(
    parent: Parent,
    combos: Sequence[tuple[Operator, ...]],
    targets: Sequence[Target],
    temperature_c: float | None,
    batch_g: float,
    listed: Sequence[str],
    reference: Reference,
) -> Card | None:
    """The parent's best served variant (§ 5.4). With targets, every combination is pre-ranked
    from the grid (_prerank) and the first EXACT_PER_PARENT that pass the gate are scored
    exactly; the best of those wins. Without targets the keys need no forecast: the first
    combination in key order (fewest to buy, fewest operators, id) that passes the gate."""
    if targets:
        order = [combos[i] for i in _prerank(parent, combos, targets, temperature_c, reference)]
        scored = []
        for combo in order:
            card, _ = variant_card(
                make_variant(parent, combo), targets, temperature_c, batch_g, listed, reference
            )
            if card is not None:
                scored.append(card)
            if len(scored) == EXACT_PER_PARENT:
                break
        return min(scored, key=experimental_rank_key) if scored else None

    def cheap(combo: tuple[Operator, ...]) -> tuple[int, int, str]:
        v = make_variant(parent, combo)
        return len(to_buy(v.recipe, listed)), len(combo), v.id

    for combo in sorted(combos, key=cheap):
        card, _ = variant_card(
            make_variant(parent, combo), targets, temperature_c, batch_g, listed, reference
        )
        if card is not None:
            return card
    return None


def experimental_cards(
    listed: Sequence[str],
    targets: Sequence[Target],
    temperature_c: float | None,
    batch_g: float = DEFAULT_BATCH_G,
    usda_ids: Sequence[int] = (),
) -> list[Card]:
    """The best variant of each active library recipe, ranked (§ 5.4); at most 3."""
    cards = []
    for recipe in library.active():
        parent = Parent(recipe, "library", recipe.name)
        combos = _combos(parent, listed, temperature_c, usda_ids)
        if not combos:
            continue
        reference = library_reference(recipe, temperature_c)
        card = best_variant(parent, combos, targets, temperature_c, batch_g, listed, reference)
        if card is not None:
            cards.append(card)
    cards.sort(key=experimental_rank_key)
    return cards[:CARDS_PER_SECTION]


# ── own batch as a parent (Q16) ─────────────────────────────────────────


@dataclass(frozen=True)
class OwnBatchRow:
    name: str
    # None: no quantity, an unknown unit or a retired ingredient. Such a row stays in the
    # recipe without a mass, so the salt gate fails closed (gate.salt_pct is None).
    grams: float | None
    role: str  # the batch row's role
    nutrients: tuple[tuple[str, float], ...]  # g/100 g, as the batch forecast reads them


@dataclass(frozen=True)
class OwnBatch:
    """A user's batch, as the router reads it (owned: checked there). Every row is kept; a
    retired ingredient's row has no mass (see OwnBatchRow)."""

    batch_id: str
    number: int  # the batch's place in its culture, by start time: "your batch #n"
    culture_name: str
    fermentation_type: str
    rows: tuple[OwnBatchRow, ...]
    temperature_c: float | None  # the mean logged temperature, else the expected one
    duration_h: float | None  # a finished batch's actual duration


def _typical_duration(ferment_type: str) -> tuple[float, float, float] | None:
    """The library's documented durations for a type: (lowest lo, median of medians, highest
    hi)."""
    spans = [r.duration_h for r in library.active() if r.fermentation_type == ferment_type]
    ds = [d for d in spans if d is not None]
    if not ds:
        return None
    return min(d.lo for d in ds), float(np.median([d.median for d in ds])), max(d.hi for d in ds)


def own_parent(own: OwnBatch) -> Parent:
    """The batch as a recipe (Q16): its weighed rows as g/kg of their weighed total (a row
    without a mass keeps none: the salt gate then fails closed, and the card names it), its
    temperature widened ±3 °C (Q25, clipped to the profile while keeping the batch's own),
    and as duration its actual one widened ±30 % (Q25), or for a batch still running the
    library's typical span for the type. Raises RecommendationError for a type the
    Experimental mode does not take (sourdough starts in the planner)."""
    ft = own.fermentation_type
    if ft not in PROFILES:
        raise RecommendationError(f"a {ft} batch cannot be a parent: no forecast for this type")
    if ft == "sourdough":
        raise RecommendationError("sourdough batches: use the levain planner for variants")
    profile = PROFILES[ft]
    p_lo, p_hi = profile.temp_range
    t = own.temperature_c if own.temperature_c is not None else profile.temp_c
    temp = Span(t, min(t, max(t - 3.0, p_lo)), max(t, min(t + 3.0, p_hi)))
    notes = []
    if own.duration_h is not None and own.duration_h > 0:
        d = own.duration_h
        duration: tuple[float, float, float] | None = (0.7 * d, d, 1.3 * d)
    else:
        duration = _typical_duration(ft)
        notes.append(f"no end time yet: timings typical of {ft} recipes in the library")
    if duration is None:
        raise RecommendationError(f"no duration to measure a {ft} batch against")
    unweighed = [r.name for r in own.rows if r.grams is None]
    if unweighed:
        notes.append(
            f"no usable mass (no quantity, an unknown unit or a retired ingredient): "
            f"{', '.join(unweighed)}"
        )
    total = math.fsum(r.grams for r in own.rows if r.grams is not None and r.grams > 0)
    rows = tuple(
        library.RecipeIngredient(
            r.name, "existing" if r.name in library.CATALOGUE_NAMES else "user", r.role,
            None if r.grams is None or total <= 0 else Span(*(1000.0 * r.grams / total,) * 3),
            "core", "your batch", "", None,
            nutrients=None if r.name in library.CATALOGUE_NAMES else r.nutrients,
        )
        for r in own.rows
    )  # fmt: skip
    scope = []
    if not (p_lo <= temp.lo and temp.hi <= p_hi):
        scope.append("temp_outside_profile")
    if duration[2] > profile.horizon_h:
        scope.append("beyond_horizon")
    label = f"your batch #{own.number}"
    recipe = Recipe(
        key=f"batch:{own.batch_id}", name=f"{own.culture_name}, {label}", fermentation_type=ft,
        style_region="", provenance=OWN_BATCH_PROVENANCE, temp_c=temp,
        duration_h=Span(duration[1], duration[0], duration[2]), salt_pct=None,
        sugar_g_per_kg=None, aerobic=profile.aerobic, method="", stages="", safety_targets="",
        reported_aromas=(), sources=(), status="active", notes="; ".join(notes),
        temp_schedule=(), envelope_basis="widened_single_value",
        model_scope=tuple(scope) or ("in_range",), handoff=None, planner_style=None,
        ingredients=rows,
    )  # fmt: skip
    basis = Basis(duration, float(profile.horizon_h), None)
    return Parent(recipe, "own_batch", label, own.batch_id, basis)


def own_axis(parent: Parent) -> tuple[FloatArray, float]:
    assert parent.basis is not None
    return run.time_axis(parent.basis.duration_h, parent.basis.horizon_h)


def own_reference(parent: Parent) -> tuple[Parent, Reference]:
    """The own batch run live at its own temperature (64 members): its character and P for
    the penalty, and the main milestone's median for the no-target peak shift."""
    assert parent.basis is not None and parent.recipe.temp_c is not None
    t_dst, end = own_axis(parent)
    model_c = model_temperature(parent.recipe, parent.recipe.temp_c.median)
    stats, _, _ = live_variant_statistics(parent.recipe, model_c, FORECAST_MEMBERS, t_dst, end)
    m = stats.milestones.get(_main_milestone(parent.recipe))
    parent = replace(parent, basis=replace(parent.basis, m_source_h=m.p50 if m else None))
    d = parent.basis.duration_h if parent.basis else None
    ref = Reference(character(parent.recipe, stats, d[1] if d else None), stats.p)
    return parent, ref


def _relevance(combo: Sequence[Operator], targets: Sequence[Target]) -> int:
    """How many (operator, aroma target) pairs could move: the ingredient an operator brings
    in has curated odorants of that series (aroma_data). Pre-selection only, not a score."""
    hits = 0
    for op in combo:
        priors = aroma_data.AROMA_INGREDIENTS.get(op.ingredient or "", {})
        compounds = [aroma_data.COMPOUNDS[k] for k in priors if k in aroma_data.COMPOUNDS]
        hits += sum(
            1 for tg in targets if tg.kind == "aroma" and any(tg.key in c.series for c in compounds)
        )
    return hits


def own_batch_cards(
    own: Parent,
    listed: Sequence[str],
    targets: Sequence[Target],
    temperature_c: float | None,
    batch_g: float = DEFAULT_BATCH_G,
    usda_ids: Sequence[int] = (),
) -> list[Card]:
    """Q16: at most OWN_BATCH_VARIANTS variants of the user's batch, run live (64 members),
    ranked (§ 5.4). They are picked before any forecast: combinations that hold every
    must-include ingredient and pass the gate, the ones whose new ingredients carry odorants
    of the aroma targets first, then the fewest operators, then their keys."""
    combos = _combos(own, listed, temperature_c, usda_ids)
    combos.sort(key=lambda c: (-_relevance(c, targets), len(c), [operators.sort_key(o) for o in c]))
    chosen: list[Variant] = []
    for combo in combos:
        v = make_variant(own, combo)
        if variant_gate(v, variant_temperature(v, temperature_c)).ok:
            chosen.append(v)
        if len(chosen) == OWN_BATCH_VARIANTS:
            break
    if not chosen:
        return []
    own, reference = own_reference(own)
    t_dst, end = own_axis(own)
    cards = []
    for v in chosen:
        v = replace(v, parent=own)
        temp = variant_temperature(v, temperature_c)
        model_c = model_temperature(v.recipe, temp.served_c)
        stats, fp, fresh = live_variant_statistics(v.recipe, model_c, FORECAST_MEMBERS, t_dst, end)
        card, _ = variant_card(
            v, targets, temperature_c, batch_g, listed, reference, stats=stats
        )
        if card is not None:
            cards.append(card)
            if fresh:
                log_candidate(candidate_record(v, stats, fp, card.evaluation, None))
    cards.sort(key=experimental_rank_key)
    return cards


# ── live variant forecasts: cached by fingerprint, logged as candidates ──

_LIVE: OrderedDict[str, grid.Entry] = OrderedDict()
_LIVE_LOCK = threading.Lock()
_LOG_LOCK = threading.Lock()


def live_variant_statistics(
    recipe: Recipe, model_c: float, members: int, t_dst: FloatArray, end_h: float
) -> tuple[grid.Entry, str, bool]:
    """(statistics, fingerprint, fresh): a live forecast of any recipe (a variant, an own
    batch) summarised like a grid entry on t_dst, with its own card labels; kept in process by
    the engine inputs' fingerprint (design § 8.5: "cached by fingerprint")."""
    inputs = run.prediction_inputs(recipe, model_c)
    fp = f"{inputs.fingerprint()}|{members}|{end_h:g}|{len(t_dst)}"
    with _LIVE_LOCK:
        if fp in _LIVE:
            _LIVE.move_to_end(fp)
            return _LIVE[fp], fp, False
    t, values, w = engine.member_values(inputs, end_h, members=members)
    stats, present = run.series_statistics(t, values, w, t_dst)
    kept = [(j, s) for j, s in enumerate(run.SERIES) if present[j]]
    e, u, p = (MappingProxyType({s: stats[k, j] for j, s in kept}) for k in range(3))
    milestones = {
        m.key: grid.MilestoneTimes(*run.summarise_times(c, w))
        for m in run.milestones_for(PROFILES[recipe.fermentation_type])
        if (c := run.crossing_times(m, t, values)) is not None
    }
    top = run.top_compounds(recipe.fermentation_type, t, values, w, t_dst, stats)
    entry = grid.Entry(
        recipe_key=recipe.key, temp_c=model_c, t_h=t_dst, e=e, u=u, p=p,
        milestones=MappingProxyType(milestones), members=len(w),
        schedule=inputs.planned_temperature,
        top_compound=MappingProxyType({s: (c, tier) for s, (c, tier) in top.items()}),
        not_modelled=not_modelled(recipe), skipped=run.recipe_rows(recipe)[1],
    )  # fmt: skip
    with _LIVE_LOCK:
        _LIVE[fp] = entry
        while len(_LIVE) > LIVE_CACHE:
            _LIVE.popitem(last=False)
    return entry, fp, True


def _finite(x: float) -> float | None:
    return round(x, 4) if math.isfinite(x) else None


def candidate_record(
    v: Variant, stats: grid.Entry, fingerprint: str, ev: Evaluation, screened_e: float | None
) -> dict[str, Any]:
    """A confirmed live forecast as a grid / emulator training candidate (design §§ 8.5,
    15.2): the variant, where it ran and its statistics. Nothing that identifies a user: an
    own batch is logged as "own_batch" (no batch or owner id, no culture name); operator keys
    hold catalogue names, USDA food ids and temperatures only."""
    interaction = None
    if screened_e is not None and ev.e is not None:
        interaction = ev.e < INTERACTION_RATIO * screened_e
    return {
        "kind": "variant",
        "fingerprint": fingerprint,
        "parent_kind": v.parent.kind,
        "parent": v.link_key if v.parent.kind == "library" else "own_batch",
        "fermentation_type": v.recipe.fermentation_type,
        "operators": [op.key for op in v.operators],
        "model_c": round(stats.temp_c, 2),
        "members": stats.members,
        "model_version": engine.MODEL_VERSION,
        "grid_version": grid.version() if v.parent.kind == "library" else None,
        "targets": [s.target.key for s in ev.targets],
        "confirmed_e_peak": None if ev.e is None else round(ev.e, 4),
        "screened_e_peak": None if screened_e is None else round(screened_e, 4),
        "interaction_detected": interaction,
        "t_h": [round(float(x), 3) for x in stats.t_h],
        "series": {
            s: {k: [round(float(x), 4) for x in getattr(stats, k)[s]] for k in ("e", "u", "p")}
            for s in sorted(stats.e)
        },
        "milestones": {
            name: [_finite(m.p10), _finite(m.p50), _finite(m.p90), _finite(m.reached)]
            for name, m in sorted(stats.milestones.items())
        },
    }


def log_candidate(record: Mapping[str, Any]) -> None:
    """Append one JSON line to FERMENTTRACK_CANDIDATES_PATH (unset: nothing is written).
    Best effort: a write failure is logged, never raised."""
    path = settings.candidates_path
    if not path:
        return
    line = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    try:
        with _LOG_LOCK, open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError as exc:
        logger.warning("could not log a recommender candidate to %s: %s", path, exc)


# ── JSON (plain dicts shaped like schemas.RecommendationsOut) ───────────


def _num(x: float, digits: int = 1) -> float | int:
    """Rounded; whole numbers as int, so JSON writes them as JavaScript would (`50`, not
    `50.0`): the planner link must decode to the planner's own encoding."""
    v = round(float(x), digits)
    return int(v) if v.is_integer() else v


def _encode(obj: Mapping[str, Any]) -> str:
    raw = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def planner_plan(recipe: Recipe, served_c: float, batch_g: float) -> dict[str, Any]:
    """The style's levain build (run.bake_plan) at served_c, scaled to batch_g, in the planner's
    plan JSON (keys in the order of frontend/src/sourdough/share.js cleanPlan); hours: the
    style's fixed build time, else null (use it at the peak)."""
    style = STYLES[recipe.planner_style or ""]
    built = run.bake_plan(recipe, served_c, 0.0)["levain"]
    scale = batch_g / 1000.0
    return {
        "style": style.key,
        "starter": "ripe",
        "culture_id": None,
        "levain": {
            "seed_g": _num(built["seed_g"] * scale), "flour_g": _num(built["flour_g"] * scale),
            "water_g": _num(built["water_g"] * scale),
            "flour": {k: _num(v, 3) for k, v in built["flour"].items()},
            "temperature_c": _num(served_c),
            "hours": None if style.hours is None else _num(style.hours),
        },
        "dough": None,
        "proof": None,
    }  # fmt: skip


def planner_link(recipe: Recipe, served_c: float, batch_g: float = DEFAULT_BATCH_G) -> str:
    """`#/levain?p=<token>`: the planner's share link (frontend/src/sourdough/share.js
    encodePlan: base64url of the UTF-8 JSON {"v":1,"plan":…}, unpadded)."""
    return "#/levain?p=" + _encode({"v": 1, "plan": planner_plan(recipe, served_c, batch_g)})


def _compound(top: tuple[str, str] | None) -> dict[str, str] | None:
    if top is None:
        return None
    key, tier = top
    c = aroma_data.COMPOUNDS.get(key)
    return {"key": key, "name": c.name if c else key, "tier": tier}


def _target_json(s: TargetScore) -> dict[str, Any]:
    return {
        "key": s.target.key,
        "kind": s.target.kind,
        "level": s.level,
        "modelled": s.modelled,
        "low_resolution": s.target.key in LOW_RESOLUTION,
        "top_compound": _compound(s.top_compound),
    }


def _window_json(ev: Evaluation) -> dict[str, Any] | None:
    w = ev.window
    if w is None:
        return None
    return {
        "taste_from_h": _num(w.taste_from_h), "peak_h": _num(w.peak_h),
        "stop_by_h": _num(w.stop_by_h), "basis": ev.basis, "notes": list(w.notes),
    }  # fmt: skip


def _temperature_json(temp: Temperature, model_c: float) -> dict[str, Any]:
    return {
        "served_c": _num(temp.served_c), "recipe_c": _num(temp.recipe_c),
        "documented_c": {"lo": _num(temp.documented_c[0]), "hi": _num(temp.documented_c[1])},
        "model_c": _num(model_c),
        "slider": None if temp.slider_c is None
        else {"min_c": _num(temp.slider_c[0]), "max_c": _num(temp.slider_c[1])},
        "source_only": temp.source_only,
    }  # fmt: skip


def _pct(recipe: Recipe, name: str) -> float | None:
    """% w/w of the total of the ingredient rows (as the gate computes salt)."""
    masses = [(i.name, i.g_per_kg.median) for i in recipe.ingredients if i.g_per_kg is not None]
    total = math.fsum(m for _, m in masses)
    part = math.fsum(m for n, m in masses if n == name)
    return _num(100.0 * part / total, 2) if part > 0 and total > 0 else None


def scaled_grams(recipe: Recipe, batch_g: float) -> list[tuple[library.RecipeIngredient, float]]:
    """Each row with a mass, its median g/kg scaled to batch_g, to 0.1 g."""
    return [
        (i, round(i.g_per_kg.median * batch_g / 1000.0, 1))
        for i in recipe.ingredients
        if i.g_per_kg is not None
    ]


def operator_json(op: Operator, parent: Recipe) -> dict[str, Any]:
    """An operator chip (design § 11.1): what changes, for the card and for sending back."""
    from_c = None
    if op.kind == "temperature" and parent.temp_c is not None:
        from_c = parent.temp_schedule[0][1] if parent.temp_schedule else parent.temp_c.median
    return {
        "op": op.kind,
        "key": op.key,
        "ingredient": op.ingredient,
        "replaces": op.replaces,
        "share": None if op.share is None else _num(op.share, 4),
        "from_c": None if from_c is None else _num(from_c),
        "to_c": None if op.to_c is None else _num(op.to_c),
        "fdc_id": op.fdc_id,
        "label": operators.AROMA_UNKNOWN if op.kind == "usda" else None,
    }


def _parent_json(v: Variant) -> dict[str, Any]:
    p = v.parent
    return {
        "kind": p.kind,
        "recipe_key": p.recipe.key if p.kind == "library" else None,
        "batch_id": p.batch_id,
        "name": p.recipe.name,
        "label": p.label,
    }


def _bookable(i: library.RecipeIngredient) -> bool:
    """Start batch can book the row: a catalogue name, a USDA food or a row of your batch."""
    return i.name in library.CATALOGUE_NAMES or i.nutrients is not None


def card_json(card: Card) -> dict[str, Any]:
    r, ev, v = card.recipe, card.evaluation, card.variant
    parent = v.parent.recipe if v else r
    served = card.temperature.served_c
    planner = r.handoff == "planner"
    link = planner_link(r, served, card.batch_g) if planner else None
    labels = [*CARD_LABELS]
    if v is not None:
        labels.append(f"Experimental — departs from {v.parent.label}")
    labels += library.trust_labels(parent, served)
    if card.screened:
        labels.append(SCREENED)
    if v is not None and any(op.kind == "usda" for op in v.operators):
        labels.append(operators.AROMA_UNKNOWN)
    return {
        "id": v.id if v else f"library:{r.key}",
        "section": "experimental" if v else "proven",
        "source_kind": v.source_kind if v else "library",
        "recipe_key": (v.parent.recipe.key if v.parent.kind == "library" else None) if v
        else r.key,
        "name": parent.name,
        "fermentation_type": r.fermentation_type,
        "style_region": r.style_region,
        "parent": _parent_json(v) if v else None,
        "operators": [operator_json(op, parent) for op in v.operators] if v else [],
        "screened": card.screened,
        "interaction_detected": None,  # known after the live confirmation (the forecast)
        "recipe": {
            "batch_g": _num(card.batch_g),
            "ingredients": [
                {
                    "name": i.name, "role": i.role, "grams": _num(g), "required": i.required,
                    "in_catalogue": _bookable(i), "label": i.label, "fdc_id": i.fdc_id,
                }
                for i, g in scaled_grams(r, card.batch_g)
            ],
            "salt_pct": _pct(r, gate.SALT),
            "sugar_pct": _pct(r, operators.SUGAR),
            "starters": [i.name for i in r.ingredients if i.role == "starter"],
            "temperature_c": _num(served),
            "temp_schedule": [[_num(h), _num(c)] for h, c in card.schedule],
            "stages": r.stages,
            "aerobic": r.aerobic,
        },  # fmt: skip
        "temperature": _temperature_json(card.temperature, card.model_c),
        "window": _window_json(ev),
        "level": None if ev.e is None else score.low_med_high(ev.e),
        "targets": [_target_json(s) for s in ev.targets],
        "to_buy": list(card.to_buy),
        "not_modelled": list(card.not_modelled),
        "trust": {
            "provenance": parent.provenance,
            "sources": list(parent.sources),
            "profile_confidence": PROFILES[r.fermentation_type].confidence,
            "envelope_basis": parent.envelope_basis,
            "labels": labels,
        },
        "safety_lines": list(card.safety_lines),
        "handoff": "planner" if planner else None,
        "planner_link": link,
        "notes": list(card.notes),
    }


def recommend(
    ingredients: Sequence[str],
    aromas: Sequence[str],
    tastes: Sequence[str],
    mode: str = "proven",
    temperature_c: float | None = None,
    batch_g: float = DEFAULT_BATCH_G,
    usda_fdc_ids: Sequence[int] = (),
    own: Parent | None = None,
) -> dict[str, Any]:
    """POST /recommendations (design § 5), shaped like schemas.RecommendationsOut: the Proven
    section (mode proven or both) and the Experimental one (experimental or both). own: the
    user's batch as a parent (Q16, live forecasts); its best variant leads the Experimental
    section, the user asked for it."""
    targets = parse_targets(aromas, tastes)
    listed = tuple(dict.fromkeys(ingredients))
    required = must_include(listed)
    proven = None
    refused: list[tuple[str, tuple[str, ...]]] = []
    if mode in ("proven", "both"):
        cards, refused = proven_cards(listed, targets, temperature_c, batch_g)
        message = None
        if not cards:
            message = (
                "No proven recipe passes the safety checks here."
                if refused or not required
                else f"No proven recipe contains all of: {', '.join(required)}."
            )
        proven = {"cards": [card_json(c) for c in cards], "message": message}
    experimental = None
    if mode in ("experimental", "both"):
        considered, cards = experimental_section(
            listed, targets, temperature_c, batch_g, usda_fdc_ids, own
        )
        message = None
        if not cards:
            message = (
                f"No variant can include all of: {', '.join(required)}."
                if required and not considered
                else "No experimental idea passes the safety checks here."
            )
        experimental = {"cards": [card_json(c) for c in cards], "message": message}
    return {
        "mode": mode,
        "grid_version": grid.version(),
        "targets": [
            {"key": t.key, "kind": t.kind, "low_resolution": t.key in LOW_RESOLUTION}
            for t in targets
        ],
        "proven": proven,
        "experimental": experimental,
        "notes": [],
        "debug": {"gated_out": [{"recipe_key": k, "reasons": list(why)} for k, why in refused]},
    }


def experimental_section(
    listed: Sequence[str],
    targets: Sequence[Target],
    temperature_c: float | None,
    batch_g: float,
    usda_ids: Sequence[int],
    own: Parent | None,
) -> tuple[bool, list[Card]]:
    """(any combination held the must-include ingredients, the section's cards): the own
    batch's best variant first, then the library parents' best ones (§ 5.4), 3 in all, one
    per parent."""
    cards = experimental_cards(listed, targets, temperature_c, batch_g, usda_ids)
    considered = bool(cards) or any(
        _combos(Parent(r, "library", r.name), listed, temperature_c, usda_ids)
        for r in library.active()
    )
    if own is not None:
        mine = own_batch_cards(own, listed, targets, temperature_c, batch_g, usda_ids)
        considered = considered or bool(_combos(own, listed, temperature_c, usda_ids))
        cards = [*mine[:1], *cards][:CARDS_PER_SECTION]
    return considered, cards


# ── the live per-card forecast (design § 10.1) ──────────────────────────


def active_recipe(key: str) -> Recipe:
    recipe = library.get(key)
    if recipe is None or recipe.status != "active":
        raise UnknownRecipe(f"no active library recipe {key!r}")
    return recipe


def forecast(
    recipe_key: str | None,
    aromas: Sequence[str],
    tastes: Sequence[str],
    temperature_c: float | None,
    batch_g: float = DEFAULT_BATCH_G,
    members: int = FORECAST_MEMBERS,
    *,
    ops: Sequence[OperatorRequest] = (),
    own: Parent | None = None,
) -> dict[str, Any]:
    """POST /recommendations/forecast: the card at a slider temperature from a live forecast,
    shaped like schemas.RecommendationForecastOut. Sourdough answers with its planner link.
    With operators, or an own batch (own), the variant's live forecast: the confirmation of a
    screened card (variant_forecast). Raises UnknownRecipe, GateRefused, OperatorRefused,
    ValueError, engine.PredictionUnavailable."""
    if ops or own is not None:
        parent = own if own is not None else library_parent(recipe_key or "")
        return variant_forecast(parent, ops, aromas, tastes, temperature_c, batch_g, members)
    recipe = active_recipe(recipe_key or "")
    targets = parse_targets(aromas, tastes)
    temp = resolve_temperature(recipe, temperature_c)
    result = check_gate(recipe, temp)
    if not result.ok:
        raise GateRefused("this temperature does not pass the safety checks for this recipe")
    body = _forecast_body(recipe.key, "library", [], False, result, temp)
    if recipe.handoff == "planner":
        return body | {
            "handoff": "planner",
            "planner_link": planner_link(recipe, temp.served_c, batch_g),
            "notes": [*temp.notes, "sourdough timing comes from the levain planner"],
        }
    model_c = model_temperature(recipe, temp.served_c)
    stats = _live(recipe.key, model_c, members)
    ev = evaluate(recipe, stats, temp, targets)
    return body | _live_json(stats, temp, model_c, ev, targets)


def _forecast_body(
    recipe_key: str | None,
    source_kind: str,
    chips: list[dict[str, Any]],
    screened: bool,
    result: gate.GateResult,
    temp: Temperature,
) -> dict[str, Any]:
    return {
        "recipe_key": recipe_key, "source_kind": source_kind, "operators": chips,
        "screened": screened, "screened_e_peak": None, "interaction_detected": None,
        "members": None, "temperature": None, "window": None, "level": None, "e_peak": None,
        "u_peak": None, "targets": [], "bands": [], "safety_lines": list(result.safety_lines),
        "handoff": None, "planner_link": None, "notes": list(temp.notes),
    }  # fmt: skip


def _live_json(
    stats: grid.Entry, temp: Temperature, model_c: float, ev: Evaluation, targets: Sequence[Target]
) -> dict[str, Any]:
    return {
        "members": stats.members,
        "temperature": _temperature_json(temp, model_c),
        "window": _window_json(ev),
        "level": None if ev.e is None else score.low_med_high(ev.e),
        "e_peak": None if ev.e is None else _num(ev.e, 3),
        "u_peak": None if ev.u is None else _num(ev.u, 3),
        "targets": [
            _target_json(s) | {"e_peak": _num(s.e, 3), "u_peak": _num(s.u, 3)} for s in ev.targets
        ],
        "bands": [
            {
                "key": tg.key, "kind": tg.kind, "t_h": [_num(x) for x in stats.t_h],
                "e": [_num(x, 3) for x in stats.e[tg.key]],
                "u": [_num(x, 3) for x in stats.u[tg.key]],
            }
            for tg in targets
            if tg.key in stats.e
        ],  # fmt: skip
        "notes": [*temp.notes, *_model_note(model_c, temp, IN_RANGE), *ev.notes],
    }


def library_parent(recipe_key: str) -> Parent:
    recipe = active_recipe(recipe_key)
    return Parent(recipe, "library", recipe.name)


def _live_variant(
    v: Variant, temp: Temperature, members: int, temperature_c: float | None
) -> tuple[Variant, grid.Entry, str, bool, Reference]:
    """A variant's live forecast at the nearest temperature the model covers, on its parent's
    time axis, with the parent as served (library: from the grid; own batch: live)."""
    parent = v.parent
    if parent.kind == "library":
        rg = grid.recipe(parent.recipe.key)
        t_dst, end = grid.entry(parent.recipe.key, rg.temps[0]).t_h, rg.end_h
        reference = library_reference(parent.recipe, temperature_c)
    else:
        parent, reference = own_reference(parent)
        v = replace(v, parent=parent)
        t_dst, end = own_axis(parent)
    model_c = model_temperature(v.recipe, temp.served_c)
    stats, fp, fresh = live_variant_statistics(v.recipe, model_c, members, t_dst, end)
    return v, stats, fp, fresh, reference


def variant_forecast(
    parent: Parent,
    requests: Sequence[OperatorRequest],
    aromas: Sequence[str],
    tastes: Sequence[str],
    temperature_c: float | None,
    batch_g: float = DEFAULT_BATCH_G,
    members: int = FORECAST_MEMBERS,
) -> dict[str, Any]:
    """A variant's live forecast (design §§ 8.5, 10.1): the slider, and the lazy confirmation
    of a screened card. When the card was screened, the screened E(peak) at the same
    temperature comes back too, and "interaction detected" when the confirmed one is below
    0.8 times it. A fresh confirmation is kept by fingerprint and logged (log_candidate)."""
    targets = parse_targets(aromas, tastes)
    v = make_variant(parent, resolve_operators(parent, requests))
    temp = variant_temperature(v, temperature_c)
    result = variant_gate(v, temp)
    if not result.ok:
        raise GateRefused("this variant does not pass the safety checks at this temperature")
    chips = [operator_json(op, parent.recipe) for op in v.operators]
    key = parent.recipe.key if parent.kind == "library" else None
    body = _forecast_body(key, v.source_kind, chips, v.screened, result, temp)
    if v.recipe.handoff == "planner":
        return body | {
            "handoff": "planner",
            "planner_link": planner_link(v.recipe, temp.served_c, batch_g),
            "notes": [*temp.notes, "sourdough timing comes from the levain planner"],
        }
    v, stats, fp, fresh, reference = _live_variant(v, temp, members, temperature_c)
    basis = v.parent.basis or grid_basis(v.parent.recipe, temp.recipe_c)
    ev = evaluate(
        v.recipe, stats, temp, targets, mode="experimental", reference=reference, basis=basis
    )
    screened_e = None
    if v.screened and targets:
        screened_ev = evaluate(
            v.recipe, screened_statistics(v, temp), temp, targets, mode="experimental",
            reference=reference, basis=basis,
        )  # fmt: skip
        screened_e = screened_ev.e
    interaction = None
    if screened_e is not None and ev.e is not None:
        interaction = ev.e < INTERACTION_RATIO * screened_e
    if fresh:
        log_candidate(candidate_record(v, stats, fp, ev, screened_e))
    out = body | _live_json(stats, temp, stats.temp_c, ev, targets)
    if interaction:
        out["notes"] = [
            *out["notes"],
            f"{INTERACTION}: the confirmed forecast is below {INTERACTION_RATIO:g} × the "
            "screened one",
        ]
    return out | {
        "screened_e_peak": None if screened_e is None else _num(screened_e, 3),
        "interaction_detected": interaction,
    }


# ── Start batch (design § 11.2) ─────────────────────────────────────────


@dataclass(frozen=True)
class BatchPlan:
    """What POST /batches/from-recommendation writes, computed from the card the server
    serves (never from the client's copy)."""

    card: Card
    expected_temperature_c: float  # the served temperature; a staged recipe's first stage
    rows: tuple[tuple[str, float, str], ...]  # (ingredient name, grams, batch role)
    skipped: tuple[str, ...]  # rows not booked (run.recipe_rows): not in the catalogue yet
    ph_reminder: bool
    link: dict[str, Any]  # the recommendation_links columns besides batch_id and created_at
    name: str = ""  # the new culture's default name
    fdc_rows: tuple[tuple[int, float, str], ...] = ()  # operator (v): (USDA food, grams, role)


def _link(card: Card, mode: str, source_kind: str, key: str, chips: list[Any]) -> dict[str, Any]:
    ev = card.evaluation
    return {
        "source_kind": source_kind,
        "recipe_key": key,
        "community_recipe_id": None,
        "operators": chips,
        "mode": mode,
        "temperature_c": _num(card.temperature.served_c),
        "temp_schedule": [[_num(h), _num(c)] for h, c in card.schedule] or None,
        "window": _window_json(ev),
        "targets": [
            {"key": s.target.key, "kind": s.target.kind, "e": _num(s.e, 4), "u": _num(s.u, 4)}
            for s in ev.targets
        ],
        "grid_version": grid.version(),
    }


def batch_plan(
    recipe_key: str | None,
    aromas: Sequence[str],
    tastes: Sequence[str],
    temperature_c: float | None,
    batch_g: float,
    mode: str,
    *,
    ops: Sequence[OperatorRequest] = (),
    own: Parent | None = None,
) -> BatchPlan:
    """The batch a card books. With operators (and an own batch, own) the variant's, the
    card recomputed here: from the grid for a library variant, live for an own batch."""
    if ops or own is not None:
        parent = own if own is not None else library_parent(recipe_key or "")
        return variant_batch_plan(parent, ops, aromas, tastes, temperature_c, batch_g, mode)
    recipe = active_recipe(recipe_key or "")
    card, result = build_card(recipe, parse_targets(aromas, tastes), temperature_c, batch_g)
    if card is None:
        raise GateRefused("this recipe does not pass the safety checks at this temperature")
    assert card.evaluation.window is not None  # only sourdough lacks one: the planner starts it
    booked, skipped = run.recipe_rows(recipe)  # what the forecast runs is what gets booked
    rows = tuple(
        (r.name, round(r.quantity * batch_g / 1000.0, 1), r.role)
        for r in booked
        if r.quantity is not None  # always set: recipe_rows skips rows without a mass
    )
    first = card.schedule[0][1] if card.schedule else card.temperature.served_c
    link = _link(card, mode, "library", recipe.key, [])
    return BatchPlan(
        card, float(first), rows, skipped, gate.needs_ph_reminder(recipe.fermentation_type), link,
        recipe.name,
    )  # fmt: skip


def variant_batch_plan(
    parent: Parent,
    requests: Sequence[OperatorRequest],
    aromas: Sequence[str],
    tastes: Sequence[str],
    temperature_c: float | None,
    batch_g: float,
    mode: str,
) -> BatchPlan:
    targets = parse_targets(aromas, tastes)
    v = make_variant(parent, resolve_operators(parent, requests))
    if parent.kind == "library":
        reference = library_reference(parent.recipe, temperature_c)
        card, _ = variant_card(v, targets, temperature_c, batch_g, (), reference)
    else:
        temp = variant_temperature(v, temperature_c)
        if not variant_gate(v, temp).ok:
            raise GateRefused("this variant does not pass the safety checks at this temperature")
        v, stats, fp, fresh, reference = _live_variant(v, temp, FORECAST_MEMBERS, temperature_c)
        card, _ = variant_card(v, targets, temperature_c, batch_g, (), reference, stats=stats)
        if card is not None and fresh:
            log_candidate(candidate_record(v, stats, fp, card.evaluation, None))
    if card is None:
        raise GateRefused("this variant does not pass the safety checks at this temperature")
    assert card.evaluation.window is not None  # only sourdough lacks one: the planner starts it
    booked, skipped = run.recipe_rows(v.recipe)
    fdc = {i.name: i.fdc_id for i in v.recipe.ingredients if i.fdc_id is not None}
    grams = [(r.name, round(r.quantity * batch_g / 1000.0, 1), r.role) for r in booked
             if r.quantity is not None]  # fmt: skip
    rows = tuple(g for g in grams if g[0] not in fdc)
    fdc_rows = tuple((fdc[n], q, role) for n, q, role in grams if n in fdc)
    first = card.schedule[0][1] if card.schedule else card.temperature.served_c
    chips = [operator_json(op, parent.recipe) for op in v.operators]
    link = _link(card, mode, v.source_kind, v.link_key, chips)
    return BatchPlan(
        card, float(first), rows, skipped, gate.needs_ph_reminder(v.recipe.fermentation_type),
        link, f"{parent.recipe.name} (variant)", fdc_rows,
    )  # fmt: skip


def planner_handoff(
    recipe_key: str | None,
    temperature_c: float | None,
    batch_g: float,
    ops: Sequence[OperatorRequest] = (),
) -> str | None:
    """A sourdough card's (or variant's) planner link: Start batch hands it to the planner
    (Q31). None for every other type. A variant goes through variant_gate first, like every
    other variant (raises GateRefused)."""
    if recipe_key is None:
        return None
    recipe = active_recipe(recipe_key)
    if recipe.handoff != "planner":
        return None
    if not ops:
        return planner_link(recipe, resolve_temperature(recipe, temperature_c).served_c, batch_g)
    parent = Parent(recipe, "library", recipe.name)
    v = make_variant(parent, resolve_operators(parent, ops))
    temp = variant_temperature(v, temperature_c)
    if not variant_gate(v, temp).ok:
        raise GateRefused("this variant does not pass the safety checks at this temperature")
    return planner_link(v.recipe, temp.served_c, batch_g)
