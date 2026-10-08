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

Responses carry no timestamps and round every number, so a request and a grid give the same
JSON (E5). Scores show as Low / Med / High until the calibration gate (§ 13.2).
"""

from __future__ import annotations

import base64
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from functools import lru_cache
from types import MappingProxyType
from typing import Any, Literal

import numpy as np

from fermenttrack.prediction import aroma_data, derived
from fermenttrack.prediction import service as engine
from fermenttrack.prediction.priors import FloatArray
from fermenttrack.prediction.profiles import PROFILES
from fermenttrack.prediction.sourdough import STYLES

# `run`: how a recipe runs and how a run becomes grid statistics, shared with the grid builder
# so a live forecast is computed the way its grid entry was. The only source of that logic.
from fermenttrack.recommender import gate, grid, library, run, score, window
from fermenttrack.recommender.library import Recipe
from fermenttrack.recommender.window import Window

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
) -> Evaluation:
    """The card's window and scores from one set of statistics (a grid entry, interpolated, or
    a live forecast). clip=False is the model's own window (E3)."""
    rg = grid.recipe(recipe.key)
    t = stats.t_h
    notes = [f"{tg.key}: {NOT_MODELLED}" for tg in targets if tg.key not in stats.e]
    basis: Literal["model", "source", "planner"]
    if recipe.handoff == "planner":
        win, basis, extra = _sourdough_window(recipe, stats, temp)
        notes += extra
        d = recipe.duration_h
        peak = win.peak_h if win else (d.median if d else float(t[-1]))
    else:
        if rg.duration_h is None:
            raise RecommendationError(f"{recipe.key} has no documented duration")
        keys = [tg.key for tg in targets]
        zeros = np.zeros_like(t)
        e = score.target_average({k: stats.e.get(k, zeros) for k in keys}, keys) if keys else None
        # the character at d_med; past the grid end (red miso, sand lance), at its end
        at_dmed = min(rg.duration_h[1], float(t[-1]))
        character = score.character_series(
            recipe.reported_aromas, {s: _at(t, v, at_dmed) for s, v in stats.p.items()}
        )
        off = {o: stats.p[o] for o in score.off_note_series(keys, character) if o in stats.p}
        safety = stats.milestones.get(grid.SAFETY_MILESTONE)
        main = PROFILES[recipe.fermentation_type].milestones[0].key
        m_user = stats.milestones.get(main)
        m_source = grid.interp_temp(recipe.key, temp.recipe_c).milestones.get(main)
        win = window.compute(
            t, e, off, safety.p90 if safety else 0.0, rg.duration_h, rg.horizon_h, "proven",
            m_user_h=m_user.p50 if m_user else None,
            m_source_h=m_source.p50 if m_source else None,
            model_scope=recipe.model_scope, clip=clip, source_only=temp.source_only,
        )  # fmt: skip
        if temp.source_only:  # name the temperatures behind the source's timings
            specific = source_note(recipe, temp, stats.temp_c)
            win = replace(win, notes=tuple(
                specific if n == window.SOURCE_ONLY_NOTE else n for n in win.notes
            ))  # fmt: skip
        basis = "source" if temp.source_only else "model"
        peak = win.peak_h
    scores, e_peak, u_peak = _scores(stats, targets, peak)
    return Evaluation(win, basis, peak, scores, e_peak, u_peak, tuple(notes))


# ── cards ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Card:
    recipe: Recipe
    temperature: Temperature
    schedule: tuple[tuple[float, float], ...]
    model_c: float
    evaluation: Evaluation
    safety_lines: tuple[str, ...]
    batch_g: float
    to_buy: tuple[str, ...]
    not_modelled: tuple[str, ...]
    notes: tuple[str, ...]


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


def card_json(card: Card) -> dict[str, Any]:
    r, ev = card.recipe, card.evaluation
    planner = r.handoff == "planner"
    link = planner_link(r, card.temperature.served_c, card.batch_g) if planner else None
    return {
        "id": f"library:{r.key}",
        "section": "proven",
        "source_kind": "library",
        "recipe_key": r.key,
        "name": r.name,
        "fermentation_type": r.fermentation_type,
        "style_region": r.style_region,
        "recipe": {
            "batch_g": _num(card.batch_g),
            "ingredients": [
                {
                    "name": i.name, "role": i.role, "grams": _num(g), "required": i.required,
                    "in_catalogue": i.name in library.CATALOGUE_NAMES, "label": i.label,
                }
                for i, g in scaled_grams(r, card.batch_g)
            ],
            "salt_pct": _pct(r, gate.SALT),
            "sugar_pct": _pct(r, "Cane sugar"),
            "starters": [i.name for i in r.ingredients if i.role == "starter"],
            "temperature_c": _num(card.temperature.served_c),
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
            "provenance": r.provenance,
            "sources": list(r.sources),
            "profile_confidence": PROFILES[r.fermentation_type].confidence,
            "envelope_basis": r.envelope_basis,
            "labels": [*CARD_LABELS, *library.trust_labels(r)],
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
) -> dict[str, Any]:
    """POST /recommendations (design § 5): the Proven section, shaped like
    schemas.RecommendationsOut. Experimental arrives with B7 (`experimental` is null)."""
    targets = parse_targets(aromas, tastes)
    listed = tuple(dict.fromkeys(ingredients))
    cards, refused = proven_cards(listed, targets, temperature_c, batch_g)
    notes = []
    if mode != "proven":
        notes.append("Experimental ideas are not available yet: showing Proven recipes only.")
    message = None
    required = must_include(listed)
    if not cards:
        message = (
            "No proven recipe passes the safety checks here."
            if refused or not required
            else f"No proven recipe contains all of: {', '.join(required)}."
        )
    return {
        "mode": mode,
        "grid_version": grid.version(),
        "targets": [
            {"key": t.key, "kind": t.kind, "low_resolution": t.key in LOW_RESOLUTION}
            for t in targets
        ],
        "proven": {"cards": [card_json(c) for c in cards], "message": message},
        "experimental": None,
        "notes": notes,
        "debug": {"gated_out": [{"recipe_key": k, "reasons": list(why)} for k, why in refused]},
    }


# ── the live per-card forecast (design § 10.1) ──────────────────────────


def active_recipe(key: str) -> Recipe:
    recipe = library.get(key)
    if recipe is None or recipe.status != "active":
        raise UnknownRecipe(f"no active library recipe {key!r}")
    return recipe


def forecast(
    recipe_key: str,
    aromas: Sequence[str],
    tastes: Sequence[str],
    temperature_c: float | None,
    batch_g: float = DEFAULT_BATCH_G,
    members: int = FORECAST_MEMBERS,
) -> dict[str, Any]:
    """POST /recommendations/forecast: the card at a slider temperature from a live forecast,
    shaped like schemas.RecommendationForecastOut. Sourdough answers with its planner link.
    Raises UnknownRecipe, GateRefused, ValueError, engine.PredictionUnavailable."""
    recipe = active_recipe(recipe_key)
    targets = parse_targets(aromas, tastes)
    temp = resolve_temperature(recipe, temperature_c)
    result = check_gate(recipe, temp)
    if not result.ok:
        raise GateRefused("this temperature does not pass the safety checks for this recipe")
    body: dict[str, Any] = {
        "recipe_key": recipe.key, "members": None, "temperature": None, "window": None,
        "level": None, "e_peak": None, "u_peak": None, "targets": [], "bands": [],
        "safety_lines": list(result.safety_lines), "handoff": None, "planner_link": None,
        "notes": list(temp.notes),
    }  # fmt: skip
    if recipe.handoff == "planner":
        return body | {
            "handoff": "planner",
            "planner_link": planner_link(recipe, temp.served_c, batch_g),
            "notes": [*temp.notes, "sourdough timing comes from the levain planner"],
        }
    model_c = model_temperature(recipe, temp.served_c)
    stats = _live(recipe.key, model_c, members)
    ev = evaluate(recipe, stats, temp, targets)
    return body | {
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


# ── Start batch (design § 11.2) ─────────────────────────────────────────


@dataclass(frozen=True)
class BatchPlan:
    """What POST /batches/from-recommendation writes, computed from the card the server
    serves (never from the client's copy)."""

    card: Card
    expected_temperature_c: float  # the served temperature; a staged recipe's first stage
    rows: tuple[tuple[str, float, str], ...]  # (catalogue name, grams, batch role)
    skipped: tuple[str, ...]  # rows not booked (run.recipe_rows): not in the catalogue yet
    ph_reminder: bool
    link: dict[str, Any]  # the recommendation_links columns besides batch_id and created_at


def batch_plan(
    recipe_key: str,
    aromas: Sequence[str],
    tastes: Sequence[str],
    temperature_c: float | None,
    batch_g: float,
    mode: str,
) -> BatchPlan:
    recipe = active_recipe(recipe_key)
    card, result = build_card(recipe, parse_targets(aromas, tastes), temperature_c, batch_g)
    if card is None:
        raise GateRefused("this recipe does not pass the safety checks at this temperature")
    ev = card.evaluation
    assert ev.window is not None  # only sourdough lacks one, and it starts in the planner
    booked, skipped = run.recipe_rows(recipe)  # what the forecast runs is what gets booked
    rows = tuple(
        (r.name, round(r.quantity * batch_g / 1000.0, 1), r.role)
        for r in booked
        if r.quantity is not None  # always set: recipe_rows skips rows without a mass
    )
    first = card.schedule[0][1] if card.schedule else card.temperature.served_c
    link = {
        "source_kind": "library",
        "recipe_key": recipe.key,
        "community_recipe_id": None,
        "operators": [],
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
    return BatchPlan(
        card, float(first), rows, skipped, gate.needs_ph_reminder(recipe.fermentation_type), link
    )
