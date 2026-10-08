"""The recommender's safety gate (design § 7).

Every rule that can be checked from a recipe, at every temperature the card can show, before
anything is served, in every mode. A failure removes the candidate; `reasons` go to a debug
field only. `safety_lines` are mandatory on the card and follow each type's safety barrier:
acidity (the pH lines), temperature (koji) or salt (miso, garum). Predicted pH plays no part:
it is never clearance.

Thresholds mirror `safety/risk_rules.yaml` (tests pin them). The rules' scheme mapping mirrors
`safety/service.py`: koji is `enzymatic_koji`, every other type `lactic`.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

from fermenttrack.prediction.profiles import PROFILES
from fermenttrack.recommender.library import Recipe

# The catalogue's only salt row. Salt inside other ingredients (kimchi's optional salted
# shrimp) is not counted: stricter on SALT-001, intended.
SALT = "Salt"
# The salt rules say "vegetable"; the batch service would apply them to every lactic-scheme
# type and flag miso and garum salt. The gate scopes them explicitly (design § 7).
SALT_GATED_TYPES = frozenset({"lacto_ferment"})
SALT_MIN_PCT = 2.0  # SALT-001
SALT_MAX_PCT = 10.0  # SALT-002
LACTIC_MAX_C = 45.0  # TEMP-001
KOJI_MIN_C = 25.0  # KOJI-002
KOJI_MAX_C = 33.0  # KOJI-001
CERTIFIED_KOJI_STARTER = "Koji spores (A. oryzae)"  # KOJI-001's certified tane-koji exception
# Made safe by acidity (design § 7, Q6): the profiles with a pH safety line. Sourdough is not
# one: a new starter can take days to reach pH 4.6, and baking is its barrier.
ACID_SAFETY_TYPES = frozenset({"lacto_ferment", "kombucha", "kefir", "cheese", "vinegar"})
SALT_BARRIER_TYPES = frozenset({"miso", "garum"})

PH_DEADLINE_LINE = "Measure pH. It must reach ≤ 4.6 within 48 h at > 10 °C; if not, discard."
PH_LOG_LINE = "Log pH by 48 h."
KOJI_TEMP_LINE = "Keep the bed at 25–33 °C; up to 35 °C only with certified tane-koji."
TANE_KOJI_LINE = "Use certified tane-koji."
SALT_BARRIER_LINE = "Safety comes from salt, not acidity: do not reduce the salt."
# Curation spec § 3 (wine and cider vinegar cards). Not a gate rule: acidity isn't in the recipe.
VINEGAR_LINES = (
    "Check ≥ 5 % acetic acid before using to pickle.",
    "Acidity varies: do not use for canning or room-temperature storage unless verified.",
)


@dataclass(frozen=True)
class IngredientRow:
    name: str
    role: str  # base | starter | flavoring | additive | liquid
    g_per_kg: float | None  # the served mass; None: unknown
    required: str = "core"  # core | optional


@dataclass(frozen=True)
class RecipeLike:
    """What the gate reads: a library recipe (`from_recipe`), a variant or a community recipe."""

    fermentation_type: str
    ingredients: tuple[IngredientRow, ...]
    starters: tuple[str, ...] = ()  # catalogue names, whether or not they have a mass row
    temperatures_c: tuple[float, ...] = ()  # the recipe's own: served temperature, schedule steps


@dataclass(frozen=True)
class GateResult:
    ok: bool
    reasons: tuple[str, ...]  # debug only
    safety_lines: tuple[str, ...]  # mandatory card lines


def scheme(fermentation_type: str) -> str:
    return "enzymatic_koji" if fermentation_type == "koji" else "lactic"


def from_recipe(recipe: Recipe) -> RecipeLike:
    """The served recipe: median masses, the median temperature and the schedule steps."""
    temps = {c for _, c in recipe.temp_schedule}
    if recipe.temp_c is not None:
        temps.add(recipe.temp_c.median)
    return RecipeLike(
        fermentation_type=recipe.fermentation_type,
        ingredients=tuple(
            IngredientRow(i.name, i.role, i.g_per_kg.median if i.g_per_kg else None, i.required)
            for i in recipe.ingredients
        ),
        starters=tuple(i.name for i in recipe.ingredients if i.role == "starter"),
        temperatures_c=tuple(sorted(temps)),
    )


def salt_pct(recipe: RecipeLike, *, with_optional: bool = True) -> float | None:
    """Salt as % w/w of the total of the ingredient rows; None (the gate fails closed) when a
    mass is missing, not finite or negative."""
    rows = [i for i in recipe.ingredients if with_optional or i.required != "optional"]
    valid = [m for i in rows if (m := i.g_per_kg) is not None and math.isfinite(m) and m >= 0]
    if not rows or len(valid) < len(rows):
        return None
    total = math.fsum(valid)
    salt = math.fsum(m for i, m in zip(rows, valid, strict=True) if i.name == SALT)
    return 100.0 * salt / total if total > 0 else None


def needs_ph_reminder(fermentation_type: str) -> bool:
    """Acid-safety types: the card carries the pH lines and Start batch creates the reminder."""
    return fermentation_type in ACID_SAFETY_TYPES


def safety_lines(recipe: RecipeLike) -> tuple[str, ...]:
    ft = recipe.fermentation_type
    lines: list[str] = []
    if needs_ph_reminder(ft):
        lines += [PH_DEADLINE_LINE, PH_LOG_LINE]
    if ft == "koji":
        lines.append(KOJI_TEMP_LINE)
        if CERTIFIED_KOJI_STARTER in recipe.starters:
            lines.append(TANE_KOJI_LINE)
    if ft in SALT_BARRIER_TYPES:
        lines.append(SALT_BARRIER_LINE)
    if ft == "vinegar":
        lines += VINEGAR_LINES
    return tuple(lines)


def _salt_reasons(recipe: RecipeLike) -> list[str]:
    # The user may leave optional rows out, so the salt must pass with and without them.
    variants = [(True, "all rows")]
    if any(i.required == "optional" for i in recipe.ingredients):
        variants.append((False, "core rows only"))
    reasons = []
    for with_optional, label in variants:
        pct = salt_pct(recipe, with_optional=with_optional)
        if pct is None:
            reasons.append(f"SALT-001: salt % unknown, a mass is missing or invalid ({label})")
        elif pct < SALT_MIN_PCT:
            reasons.append(f"SALT-001: salt {pct:.2f} % w/w < {SALT_MIN_PCT} % ({label})")
        elif pct > SALT_MAX_PCT:
            reasons.append(f"SALT-002: salt {pct:.2f} % w/w > {SALT_MAX_PCT} % ({label})")
    return reasons


def _temperature_reasons(recipe: RecipeLike, temps: list[float]) -> list[str]:
    reasons = []
    if scheme(recipe.fermentation_type) == "lactic":
        reasons += [f"TEMP-001: {t:g} °C > {LACTIC_MAX_C:g} °C" for t in temps if t > LACTIC_MAX_C]
    else:
        reasons += [f"KOJI-002: {t:g} °C < {KOJI_MIN_C:g} °C" for t in temps if t < KOJI_MIN_C]
        # The exception holds only when the certified strain is the recipe's sole starter.
        certified = set(recipe.starters) == {CERTIFIED_KOJI_STARTER}
        if not certified:
            reasons += [
                f"KOJI-001: {t:g} °C > {KOJI_MAX_C:g} °C without {CERTIFIED_KOJI_STARTER} "
                "as the only starter"
                for t in temps
                if t > KOJI_MAX_C
            ]
    return reasons


def check(recipe: RecipeLike, temperatures: Iterable[float]) -> GateResult:
    """Gate `recipe` at its own temperatures plus `temperatures` (the grid temperatures, the
    slider range): every one must pass. Fails closed on anything it cannot check."""
    temps = sorted({*recipe.temperatures_c, *temperatures})
    reasons: list[str] = []
    if recipe.fermentation_type not in PROFILES:
        reasons.append(f"unknown fermentation type {recipe.fermentation_type!r}")
    if not temps:
        reasons.append("no temperature to check")
    if not all(math.isfinite(t) for t in temps):
        reasons.append("a temperature is not a finite number")
    if recipe.fermentation_type in SALT_GATED_TYPES:
        reasons += _salt_reasons(recipe)
    reasons += _temperature_reasons(recipe, temps)
    return GateResult(not reasons, tuple(reasons), safety_lines(recipe))
