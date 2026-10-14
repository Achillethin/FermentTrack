"""The recipe library (R0, design § 4) and the derived ingredient tiers (design § 12).

`recipes_v1.csv` and `recipe_ingredients_v1.csv` are frozen: only scripts/build_recipes.py
writes them, from the research drafts and the curation spec
(docs/superpowers/specs/2026-10-07-recipe-curation.md).

`ingredient_use_levels_v1.csv` (tier T3, docs/ADDING_AN_INGREDIENT.md) is frozen too. Its v1
rows were bootstrapped from the shares of tier-T2 ingredients in the active library recipes
(tests/test_recommender_library.py re-derives them); the lacto-ingredients research round adds
rows. Lines starting with `#` are comments.
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
USE_LEVELS_CSV = HERE / "ingredient_use_levels_v1.csv"  # T3

_SEEDS = (
    INGREDIENT_SEED_DATA, INGREDIENT_SEED_DATA_V2, INGREDIENT_SEED_DATA_V3, INGREDIENT_SEED_DATA_V4,
)  # fmt: skip

# Live catalogue names (tier T0): every seed-data version, minus the retired generic rows.
CATALOGUE_NAMES: frozenset[str] = frozenset(
    name for seed in _SEEDS for name, _role, _systems in seed
) - frozenset(RETIRED_V3)

# Live catalogue name -> (default role, fermentation systems), as the migrations seed it (the
# first seed version naming it wins, like the database's insert order).
CATALOGUE: Mapping[str, tuple[str, tuple[str, ...]]] = MappingProxyType({
    name: (role, tuple(systems))
    for seed in reversed(_SEEDS)
    for name, role, systems in seed
    if name in CATALOGUE_NAMES
})  # fmt: skip

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
    # Not from the v1 files: nutrients (g/100 g) for a row that is not a catalogue name (a
    # user's USDA pick on their own batch, an Experimental operator (v) food); None = the
    # catalogue's (run.per_100g_table). fdc_id: the USDA food an operator (v) row books.
    nutrients: tuple[tuple[str, float], ...] | None = None
    fdc_id: int | None = None


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


OUTSIDE_RANGE_LABEL = (
    "source temperature outside the model's range: forecasts use the nearest in-range temperature"
)
PARTLY_OUTSIDE_LABEL = "part of the documented temperature range is outside the model's range"


def trust_labels(recipe: Recipe, served_c: float | None = None) -> tuple[str, ...]:
    """The card's Q25 and Q26 labels (design § 4.3). served_c: the temperature the card is
    served at (default: the recipe's median). A recipe whose documented span leaves the
    profile's range says the model works at the nearest in-range temperature only when the
    served temperature is outside that range; otherwise that only part of the span is."""
    profile = PROFILES[recipe.fermentation_type]
    labels = []
    if recipe.envelope_basis == "widened_single_value":
        labels.append("single-value source, widened")
    if "temp_outside_profile" in recipe.model_scope:
        lo, hi = profile.temp_range
        served = served_c if served_c is not None else (
            recipe.temp_c.median if recipe.temp_c is not None else None
        )  # fmt: skip
        outside = served is not None and not lo <= served <= hi
        labels.append(OUTSIDE_RANGE_LABEL if outside else PARTLY_OUTSIDE_LABEL)
    if "beyond_horizon" in recipe.model_scope:
        labels.append(f"aroma estimate covers the first {profile.horizon_h / 24:g} days only")
    return tuple(labels)


@dataclass(frozen=True)
class UseLevel:
    """A tier-T3 row (design § 12): the typical mass share of the whole batch."""

    ingredient: str
    fermentation_type: str
    role: str
    share_median: float
    share_lo: float
    share_hi: float
    source: str
    notes: str


@cache
def _use_levels() -> tuple[UseLevel, ...]:
    if not USE_LEVELS_CSV.exists():
        return ()
    with USE_LEVELS_CSV.open(encoding="utf-8", newline="") as f:
        lines = [line for line in f if not line.startswith("#")]
    return tuple(
        UseLevel(
            r["ingredient"], r["fermentation_type"], r["role"], float(r["share_median"]),
            float(r["share_lo"]), float(r["share_hi"]), r["source"], r["notes"],
        )
        for r in csv.DictReader(lines)
    )  # fmt: skip


def use_levels() -> tuple[UseLevel, ...]:
    """Every row of ingredient_use_levels_v1.csv, in file order."""
    return _use_levels()


def use_level(name: str, ferment_type: str) -> UseLevel | None:
    return next(
        (u for u in _use_levels() if (u.ingredient, u.fermentation_type) == (name, ferment_type)),
        None,
    )


def ingredient_tier(name: str, ferment_type: str) -> int:
    """The plug-in tier (design § 12), derived from what exists:
    3 = aroma data and a use-level row for this type (a use-level row resolves to T2),
    2 = aroma data, 1 = an FDC nutrient link, 0 = a live catalogue name;
    -1 = not a live catalogue name (a `new` or retired ingredient)."""
    if name not in CATALOGUE_NAMES:
        return -1
    if name in AROMA_INGREDIENTS:
        return 3 if use_level(name, ferment_type) is not None else 2
    if name in _FDC_MAPPED:
        return 1
    return 0
