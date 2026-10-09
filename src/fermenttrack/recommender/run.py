"""How a library recipe runs through the forecast engine, and how a run becomes the grid's
statistics (design §§ 5.3, 8.1). The grid builder (scripts/build_recommender_grid.py) and the
live paths (B5: /recommendations/forecast, /batches/from-recommendation) share these, so a
card's live forecast is computed the way its grid entry was.

How a recipe runs:
- Service types run like a logged batch: RecipeIn rows from the recipe's catalogue rows at
  their median g/kg (`liquid` booked as `base`, the batch role vocabulary; `new` rows and rows
  without a mass are skipped), per_100g as the database seeds it (the fdc_nutrients_v1
  snapshot, migration 0006, else the fdc_catalog_v1 food of INGREDIENT_FDC_IDS_V4, migration
  0018, else none), the type's default organisms (biochem, sorted by name like the router; no
  KEGG links, which only label the output), and expected_temperature_c, or for a staged
  recipe a planned_temperature whose first stage is the requested temperature and whose later
  stages are clipped into the profile's temp_range (Q26, Q27).
- Sourdough styles (handoff = planner) run through prediction.bake: a levain build with the
  recipe's masses, the style's own flour (the v1 rows book every wheat as White wheat flour;
  a flour swapped in by operator (ii) bakes as its BAKE_FLOUR grade) and the requested
  temperature.
- Variants (recommender.operators) are recipes too and run the same way. A row with its own
  nutrients (an operator (v) USDA food, a user's USDA pick on their own batch) runs with them.

Statistics, per series s (16 aroma series, 4 tastes) and member n: L = `aroma:<s>` (log10
summed odour activity) or `taste:<s>` (log10 activity ratio); E, U, P = score.central,
score.optimistic, score.noticeable. A series the engine does not produce is absent.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from functools import cache
from itertools import pairwise
from types import MappingProxyType
from typing import Any

import numpy as np
from numpy.typing import NDArray

from fermenttrack.biochem import FERMENTATION_TYPE_ORGANISMS, ORGANISMS
from fermenttrack.fdc_catalog import load_catalog
from fermenttrack.nutrients import NUTRIENTS, load_snapshot
from fermenttrack.prediction import aroma_data as A
from fermenttrack.prediction import derived
from fermenttrack.prediction.inference import weighted_quantiles
from fermenttrack.prediction.priors import FloatArray
from fermenttrack.prediction.profiles import PROFILES, FermentProfile, Milestone
from fermenttrack.prediction.service import (
    OrganismIn,
    PredictionInputs,
    RecipeIn,
    _first_crossing,
)
from fermenttrack.prediction.sourdough import FLOURS, STYLES
from fermenttrack.recommender import grid, library, score
from fermenttrack.recommender.library import Recipe
from fermenttrack.seed_data import INGREDIENT_FDC_IDS_V4

QUANTILES = (0.1, 0.5, 0.9)  # milestone crossing quantiles
N_LOG_TIMES = 24  # the grid's time axis (design § 8.1)
FIRST_H = 1.0
CEILING = 1.5  # the axis runs to the Experimental ceiling, 1.5 x d_hi, within the horizon
# Catalogue flour -> planner grade, for a flour swapped in by operator (ii).
BAKE_FLOUR = {"White wheat flour": "t65", "Whole wheat flour": "t150", "Rye flour": "rye_t130"}
AROMA_SERIES = tuple(sorted({s for c in A.COMPOUNDS.values() for s in c.series}))
SERIES = (*AROMA_SERIES, *derived.TASTES)  # the grid's series order
SAFETY = Milestone(
    grid.SAFETY_MILESTONE, "pH below 4.6",
    "the food-safety acidity threshold; confirm with a pH reading", "ph", "below", 4.6,
)  # fmt: skip


class RecipeError(ValueError):
    """A recipe that cannot be run as given."""


# ── recipe -> engine inputs ─────────────────────────────────────────────


def validate_schedule(schedule: tuple[tuple[float, float], ...]) -> None:
    if not all(math.isfinite(x) for step in schedule for x in step):
        raise RecipeError(f"temp_schedule {schedule}: every hour and °C must be finite")
    hours = [h for h, _ in schedule]
    if hours and (hours[0] < 0 or any(b <= a for a, b in pairwise(hours))):
        raise RecipeError(f"temp_schedule {schedule}: start hours must be >= 0 and increasing")


def planned_schedule(recipe: Recipe, temp_c: float) -> tuple[tuple[float, float], ...]:
    """A staged recipe at temperature temp_c: the first stage moves to it, later stages keep
    their own temperature clipped into the profile's range (Q26); () when constant."""
    if not recipe.temp_schedule:
        return ()
    validate_schedule(recipe.temp_schedule)
    lo, hi = PROFILES[recipe.fermentation_type].temp_range
    (h0, _), *later = recipe.temp_schedule
    return ((h0, temp_c), *((h, min(max(c, lo), hi)) for h, c in later))


@cache
def per_100g_table() -> Mapping[str, Mapping[str, float]]:
    """Ingredient name -> nutrients g/100 g, as the database seeds them (see the header)."""
    table: dict[str, dict[str, float]] = {}
    for row in load_snapshot():
        table.setdefault(row.ingredient_name, {})[row.nutrient] = row.amount_per_100g
    foods = {int(r["fdc_id"]): r for r in load_catalog()}
    for name, fdc_id in INGREDIENT_FDC_IDS_V4.items():
        if name not in table:
            food = foods[fdc_id]
            table[name] = {k: float(food[k]) for k in NUTRIENTS if food[k] != ""}
    return MappingProxyType({k: MappingProxyType(v) for k, v in table.items()})


def recipe_rows(recipe: Recipe) -> tuple[tuple[RecipeIn, ...], tuple[str, ...]]:
    """(RecipeIn rows, skipped names): rows at their median mass, with the catalogue's
    nutrients, or a row's own (an own-batch USDA pick, an operator (v) food)."""
    rows: list[RecipeIn] = []
    skipped: list[str] = []
    for i in recipe.ingredients:
        own = i.nutrients is not None
        if (not own and i.name not in library.CATALOGUE_NAMES) or i.g_per_kg is None:
            skipped.append(i.name)
            continue
        role = "base" if i.role == "liquid" else i.role
        per_100g = dict(i.nutrients or ()) if own else dict(per_100g_table().get(i.name, {}))
        rows.append(RecipeIn(i.name, i.g_per_kg.median, "g", per_100g, role))
    return tuple(rows), tuple(skipped)


def prediction_inputs(recipe: Recipe, temp_c: float) -> PredictionInputs:
    """A service-type recipe at temp_c as the engine's inputs: no readings, from hour 0."""
    schedule = planned_schedule(recipe, temp_c)
    names = sorted(FERMENTATION_TYPE_ORGANISMS[recipe.fermentation_type])
    return PredictionInputs(
        fermentation_type=recipe.fermentation_type, now_h=0.0,
        expected_temperature_c=None if schedule else temp_c,
        organisms=tuple(OrganismIn(n, ORGANISMS[n], ()) for n in names),
        organism_source="default", recipe=recipe_rows(recipe)[0], measurements=(),
        planned_temperature=schedule,
    )  # fmt: skip


def _booked_as(flour_key: str) -> str:
    """The catalogue row a planner flour is booked as (the v1 rows book every white wheat as
    White wheat flour)."""
    flour = FLOURS[flour_key]
    if flour.grain == "rye":
        return "Rye flour"
    return "Whole wheat flour" if flour.ash_pct >= 1.0 else "White wheat flour"


def bake_plan(recipe: Recipe, temp_c: float, hours: float) -> dict[str, Any]:
    """A sourdough style's levain build (sourdough.plan_from_dict input): the recipe's masses,
    the style's own flour, held for `hours`. A flour row swapped by operator (ii) bakes as
    that flour's planner grade (BAKE_FLOUR) instead."""
    style = STYLES[recipe.planner_style or ""]
    grams = {i.role: i.g_per_kg.median for i in recipe.ingredients if i.g_per_kg is not None}
    if sorted(i.role for i in recipe.ingredients) != ["base", "liquid", "starter"]:
        raise RecipeError(f"{recipe.key}: a levain build is one starter, flour and water row")
    flour_row = next(i.name for i in recipe.ingredients if i.role == "base")
    if flour_row == _booked_as(style.flour):
        flour = style.flour
    elif flour_row in BAKE_FLOUR:
        flour = BAKE_FLOUR[flour_row]
    else:
        raise RecipeError(f"{recipe.key}: {flour_row!r} is not a planner flour")
    return {
        "style": style.key,
        "levain": {
            "seed_g": grams["starter"], "flour_g": grams["base"], "water_g": grams["liquid"],
            "flour": {flour: 1.0}, "temperature_c": temp_c, "hours": hours,
        },
    }  # fmt: skip


# ── the time axis ───────────────────────────────────────────────────────


def time_axis(
    duration_h: tuple[float, float, float] | None, horizon_h: float
) -> tuple[FloatArray, float]:
    """(times, end): 24 log-spaced times from 1 h to min(1.5 * d_hi, horizon), plus the
    documented (lo, med, hi) that fall inside; without a duration (planner styles), to the
    horizon."""
    extra: tuple[float, ...] = ()
    end = float(horizon_h)
    if duration_h is not None:
        end, extra = min(CEILING * duration_h[2], end), duration_h
    t = np.geomspace(FIRST_H, end, N_LOG_TIMES)
    inside = [x for x in extra if FIRST_H <= x <= end]
    return np.unique(np.concatenate([t, np.asarray(inside, dtype=float)])), end


# ── run -> statistics ───────────────────────────────────────────────────


def at_times(t_src: FloatArray, v: FloatArray, t_dst: FloatArray) -> FloatArray:
    """Each member's series (members, len(t_src)), linear in time, at t_dst."""
    i = np.clip(np.searchsorted(t_src, t_dst, side="right"), 1, len(t_src) - 1)
    f = (t_dst - t_src[i - 1]) / (t_src[i] - t_src[i - 1])
    return np.asarray(v[:, i - 1] * (1.0 - f) + v[:, i] * f)


def engine_key(series: str) -> str:
    """The member_values key of a grid series: `taste:<s>` or `aroma:<s>`."""
    return f"taste:{series}" if series in derived.TASTES else f"aroma:{series}"


def series_statistics(
    t_src: FloatArray, values: Mapping[str, FloatArray], w: FloatArray, t_dst: FloatArray
) -> tuple[FloatArray, NDArray[np.bool_]]:
    """(3, len(SERIES), len(t_dst)) E, U, P (NaN for an absent series) and the presence."""
    out = np.full((3, len(SERIES), len(t_dst)), np.nan)
    present = np.zeros(len(SERIES), dtype=bool)
    for j, s in enumerate(SERIES):
        v = values.get(engine_key(s))
        if v is None:
            continue
        L = at_times(t_src, v, t_dst)
        out[:, j] = score.central(L, w), score.optimistic(L, w), score.noticeable(L, w)
        present[j] = True
    return out, present


def milestones_for(profile: FermentProfile) -> list[Milestone]:
    """The profile's milestones, plus the pH 4.6 safety milestone where it has
    ph_safety_line."""
    ms = list(profile.milestones)
    if profile.ph_safety_line and all(m.key != SAFETY.key for m in ms):
        ms.append(SAFETY)
    return ms


def crossing_times(
    ms: Milestone, t: FloatArray, values: Mapping[str, FloatArray]
) -> FloatArray | None:
    """Each member's first crossing (inf if none); None when the milestone does not apply.
    The same rule as prediction.service._milestone, which reports P05/P50/P95 instead."""
    v = values.get(ms.series)
    if v is None:
        return None
    if ms.kind in ("below", "above"):
        target = np.full(v.shape[0], ms.threshold)
    elif ms.kind == "consumed_fraction":
        if float(np.max(v[:, 0])) <= 0.1:
            return None
        target = (1.0 - ms.threshold) * v[:, 0]
    else:
        ref = values.get(ms.ref or "")
        if ref is None or float(np.max(ref[:, 0])) <= 0.1:
            return None
        target = ms.threshold * ref[:, 0]
    return _first_crossing(t, v, target, below=ms.kind in ("below", "consumed_fraction"))


def summarise_times(times: FloatArray, w: FloatArray) -> list[float]:
    """[P10, P50, P90, reached share] of the members' crossing times (inf: not crossed)."""
    q = weighted_quantiles(times, w, QUANTILES)
    return [*(float(x) for x in q), float(np.sum(w[np.isfinite(times)]) / np.sum(w))]


def top_compounds(
    ftype: str, t_src: FloatArray, values: Mapping[str, FloatArray], w: FloatArray,
    t_dst: FloatArray, stats: FloatArray,
) -> dict[str, list[str]]:  # fmt: skip
    """Aroma series -> [its top compound, that compound's evidence tier]: the compound with
    the largest mean odour activity at the time the series' E peaks (card labels, § 8.1)."""
    evidence = A.EVIDENCE.get(ftype, {})
    made = sorted(k.removeprefix("odor:") for k in values if k.startswith("odor:"))
    wn = w / np.sum(w)
    out: dict[str, list[str]] = {}
    for j, s in enumerate(AROMA_SERIES):
        if engine_key(s) not in values:
            continue
        summed = [
            k for k in made
            if A.COMPOUNDS[k].status == "active" and A.COMPOUNDS[k].threshold is not None
            and s in A.COMPOUNDS[k].series
        ]  # fmt: skip
        t_ref = t_dst[int(np.argmax(stats[0, j]))]
        oav = {
            k: float(wn @ 10.0 ** at_times(t_src, values[f"odor:{k}"], np.array([t_ref]))[:, 0])
            for k in summed
        }
        top = max(summed, key=lambda k: (oav[k], k))
        out[s] = [top, evidence.get(top, ("plausible", "", ()))[0]]
    return out
