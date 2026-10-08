"""The recipe library (R0, design § 4) and the derived ingredient tiers (design § 12).

`recipes_v1.csv` and `recipe_ingredients_v1.csv` are frozen: only scripts/build_recipes.py
writes them, from the research drafts and the curation spec
(docs/superpowers/specs/2026-10-07-recipe-curation.md).
"""

from __future__ import annotations

import csv
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from types import MappingProxyType

from fermenttrack.prediction.aroma_data import AROMA_INGREDIENTS
from fermenttrack.prediction.profiles import PROFILES
from fermenttrack.seed_data import (
    INGREDIENT_FDC_IDS_V4,
    INGREDIENT_FDC_MAP,
    INGREDIENT_SEED_DATA,
    INGREDIENT_SEED_DATA_V2,
    INGREDIENT_SEED_DATA_V3,
    INGREDIENT_SEED_DATA_V4,
    RETIRED_V3,
)

HERE = Path(__file__).parent
RECIPES_CSV = HERE / "recipes_v1.csv"
INGREDIENTS_CSV = HERE / "recipe_ingredients_v1.csv"
USE_LEVELS_CSV = HERE / "ingredient_use_levels_v1.csv"  # T3; arrives with the Experimental mode

# Live catalogue names (tier T0): every seed-data version, minus the retired generic rows.
CATALOGUE_NAMES: frozenset[str] = frozenset(
    name
    for seed in (
        INGREDIENT_SEED_DATA,
        INGREDIENT_SEED_DATA_V2,
        INGREDIENT_SEED_DATA_V3,
        INGREDIENT_SEED_DATA_V4,
    )
    for name, _role, _systems in seed
) - frozenset(RETIRED_V3)

# Always allowed beside the user's must-include ingredients (design Q3): salt, water, sugar,
# flour, tea leaves and starter cultures. Rennet is a coagulant, not a culture: it counts as an
# ingredient to buy.
STAPLES: frozenset[str] = frozenset({
    "Salt", "Water", "Cane sugar",
    "White wheat flour", "Whole wheat flour", "Rye flour",
    "Black tea leaves", "Green tea leaves",
    "SCOBY / starter liquid", "Starter/levain", "Koji spores (A. oryzae)",
    "Starter/cheese culture", "Kefir grains", "Mother of vinegar (Acetobacter)",
})  # fmt: skip

# AROMA_INGREDIENTS keys that are not live catalogue names.
ALIASES: frozenset[str] = frozenset({
    "Napa cabbage (salted)",  # kimchi's post-salting state; aroma_data merges it into Napa cabbage
    "Black/green tea",  # retired V3 row: historical batches keep their tea aroma
    "Fish",  # retired V3 row: historical garum batches keep their fish aroma
})  # fmt: skip

_FDC_MAPPED = frozenset(INGREDIENT_FDC_MAP) | frozenset(INGREDIENT_FDC_IDS_V4)


@dataclass(frozen=True)
class Span:
    median: float
    lo: float
    hi: float


@dataclass(frozen=True)
class RecipeIngredient:
    name: str  # catalogue name, unless catalogue_status is "new"
    catalogue_status: str  # existing | existing_no_aroma | new (at curation time)
    role: str  # base | starter | flavoring | additive | liquid
    g_per_kg: Span | None  # None: the source gives no mass (draft recipes only)
    required: str  # core | optional
    source: str
    notes: str
    label: str | None  # card label, e.g. a stand-in species


@dataclass(frozen=True)
class Recipe:
    key: str
    name: str
    fermentation_type: str  # a prediction.profiles.PROFILES key
    style_region: str
    provenance: str  # institutional_tested | peer_reviewed | traditional_documented
    temp_c: Span | None
    duration_h: Span | None  # None: the sourdough planner sets the timing
    salt_pct: Span | None  # % w/w of the total batch
    sugar_g_per_kg: Span | None
    aerobic: bool
    method: str
    stages: str
    safety_targets: str
    reported_aromas: tuple[str, ...]
    sources: tuple[str, ...]  # citation keys from docs/superpowers/research/recipes/01-*.md
    status: str  # active | draft
    notes: str
    temp_schedule: tuple[tuple[float, float], ...]  # (start hour, °C) steps; () = constant
    envelope_basis: str  # sourced | widened_single_value (Q25)
    model_scope: tuple[str, ...]  # in_range, or temp_outside_profile and/or beyond_horizon (Q26)
    handoff: str | None  # "planner" for sourdough (Q31)
    planner_style: str | None  # prediction.sourdough.STYLES key
    ingredients: tuple[RecipeIngredient, ...]


def _span(row: dict[str, str], name: str) -> Span | None:
    vals = [row[f"{name}_{s}"] for s in ("median", "lo", "hi")]
    return Span(*(float(v) for v in vals)) if all(vals) else None


def _split(value: str) -> tuple[str, ...]:
    return tuple(s.strip() for s in value.split(";") if s.strip())


def _schedule(value: str) -> tuple[tuple[float, float], ...]:
    steps = (step.split(":") for step in _split(value))
    return tuple((float(h), float(t)) for h, t in steps)


def _ingredient(row: dict[str, str]) -> RecipeIngredient:
    return RecipeIngredient(
        name=row["ingredient"], catalogue_status=row["catalogue_status"], role=row["role"],
        g_per_kg=_span(row, "g_per_kg"), required=row["required"], source=row["source"],
        notes=row["notes"], label=row["label"] or None,
    )  # fmt: skip


@cache
def load_library() -> Mapping[str, Recipe]:
    """Every v1 recipe (active and draft) by key, in file order."""
    with INGREDIENTS_CSV.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    with RECIPES_CSV.open(encoding="utf-8", newline="") as f:
        recipes = {
            r["key"]: Recipe(
                key=r["key"], name=r["name"], fermentation_type=r["fermentation_type"],
                style_region=r["style_region"], provenance=r["provenance"],
                temp_c=_span(r, "temp_c"), duration_h=_span(r, "duration_h"),
                salt_pct=_span(r, "salt_pct"), sugar_g_per_kg=_span(r, "sugar_g_per_kg"),
                aerobic=r["aerobic"] == "yes", method=r["method"], stages=r["stages"],
                safety_targets=r["safety_targets"], reported_aromas=_split(r["reported_aromas"]),
                sources=_split(r["sources"]), status=r["status"], notes=r["notes"],
                temp_schedule=_schedule(r["temp_schedule"]), envelope_basis=r["envelope_basis"],
                model_scope=_split(r["model_scope"]), handoff=r["handoff"] or None,
                planner_style=r["planner_style"] or None,
                ingredients=tuple(_ingredient(i) for i in rows if i["recipe_key"] == r["key"]),
            )
            for r in csv.DictReader(f)
        }  # fmt: skip
    return MappingProxyType(recipes)


def active() -> tuple[Recipe, ...]:
    """The servable recipes; draft recipes are never served (design § 4.3)."""
    return tuple(r for r in load_library().values() if r.status == "active")


def get(key: str) -> Recipe | None:
    """Any v1 recipe, drafts included. Code that serves recipes must use active() or check
    `status`: draft recipes are never served (design § 4.3)."""
    return load_library().get(key)


def trust_labels(recipe: Recipe) -> tuple[str, ...]:
    """The card's Q25 and Q26 labels (design § 4.3)."""
    profile = PROFILES[recipe.fermentation_type]
    labels = []
    if recipe.envelope_basis == "widened_single_value":
        labels.append("single-value source, widened")
    if "temp_outside_profile" in recipe.model_scope:
        lo, hi = profile.temp_range
        if recipe.temp_c is not None and not lo <= recipe.temp_c.median <= hi:
            labels.append(
                "source temperature outside the model's range: forecasts use the nearest "
                "in-range temperature"
            )
        else:  # the served temperature is modelled; only part of the documented span is not
            labels.append("part of the documented temperature range is outside the model's range")
    if "beyond_horizon" in recipe.model_scope:
        labels.append(f"aroma estimate covers the first {profile.horizon_h / 24:g} days only")
    return tuple(labels)


@cache
def _use_levels() -> frozenset[tuple[str, str]]:
    if not USE_LEVELS_CSV.exists():
        return frozenset()
    with USE_LEVELS_CSV.open(encoding="utf-8", newline="") as f:
        lines = [line for line in f if not line.startswith("#")]
    return frozenset((r["ingredient"], r["fermentation_type"]) for r in csv.DictReader(lines))


def ingredient_tier(name: str, ferment_type: str) -> int:
    """The plug-in tier (design § 12), derived from what exists:
    3 = aroma data and a use-level row for this type (a use-level row resolves to T2),
    2 = aroma data, 1 = an FDC nutrient link, 0 = a live catalogue name;
    -1 = not a live catalogue name (a `new` or retired ingredient)."""
    if name not in CATALOGUE_NAMES:
        return -1
    if name in AROMA_INGREDIENTS:
        return 3 if (name, ferment_type) in _use_levels() else 2
    if name in _FDC_MAPPED:
        return 1
    return 0
