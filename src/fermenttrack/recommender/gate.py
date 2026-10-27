"""The recommender's safety gate (design § 7).

Every rule that can be checked from a recipe, at every temperature the card can show, before
anything is served, in every mode. A failure removes the candidate; `reasons` go to a debug
field only. `safety_lines` are mandatory on the card and follow each type's safety barrier:
acidity (the pH lines), temperature (koji) or salt (miso, garum). Predicted pH plays no part:
it is never clearance.

Thresholds mirror `safety/risk_rules.yaml` (tests pin them), except the salt-barrier minimums
for miso and garum (`SALT_BARRIER_MIN_PCT`, rule "SALT-BARRIER") and hot garum's TEMP-001
exemption (`GARUM_HOT_MIN_C`), owner decisions with no yaml rule. The rules' scheme mapping mirrors
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
SALT_MIN_PCT = 2.0  # SALT-001, of everything but the salt (salt_pct's of_rest)
SALT_MAX_PCT = 10.0  # SALT-002, of the whole batch
LACTIC_MAX_C = 45.0  # TEMP-001
# Hot garum (owner decision 2026-10-26): koji enzymes at ~60 °C and 10-12 % salt, no lactic
# bacteria (the Noma Guide's garums; the profile models 20-60 °C). At or above the FDA Food Code
# hot-holding line (2022, 3-501.16(A)(1): 57 °C / 135 °F) pathogens don't grow, so TEMP-001 does
# not apply; 45-57 °C, the warm band, stays refused.
GARUM_HOT_MIN_C = 57.0
KOJI_MIN_C = 25.0  # KOJI-002
KOJI_MAX_C = 33.0  # KOJI-001
CERTIFIED_KOJI_STARTER = "Koji spores (A. oryzae)"  # KOJI-001's certified tane-koji exception
# Made safe by acidity (design § 7, Q6): the profiles with a pH safety line. Sourdough is not
# one: a new starter can take days to reach pH 4.6, and baking is its barrier.
ACID_SAFETY_TYPES = frozenset({"lacto_ferment", "kombucha", "kefir", "cheese", "vinegar"})
SALT_BARRIER_TYPES = frozenset({"miso", "garum"})
# The salt-barrier types' minimum salt, % w/w (owner decision, B9; not a risk_rules.yaml rule):
# miso: BCCDC koji and miso guideline p. 14, "at least 4 %" (research/recipes/01-koji-miso-garum);
# garum: no sourced minimum exists, so the lowest salt of the sourced recipes (the Pacific sand
# lance fish sauce's 8.3 %, the low end of its 8.3-15.4 %, Jung et al. 2022; budu is 20-23 %):
# conservative. Every path (Proven, variants, own batch, community) goes through check(), and
# an unknown salt % fails, like SALT-001.
SALT_BARRIER_MIN_PCT = {"miso": 4.0, "garum": 8.3}

PH_DEADLINE_LINE = "Measure pH. It must reach ≤ 4.6 within 48 h at > 10 °C; if not, discard."
# Salted vegetables (owner decision 2026-10-26, VEG-001/VEG-002 in risk_rules.yaml): the Noma
# Guide's two steps instead of BOT-002, which a normal sauerkraut fails (pH 5.3-5.5 at 48 h,
# Kristek 2004).
VEG_PH_LINE = (
    "Measure pH. It must drop below 5.0 within 48 h at > 10 °C and reach ≤ 4.6 before you eat "
    "it; if not, discard."
)
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


def salt_pct(
    recipe: RecipeLike, *, with_optional: bool = True, of_rest: bool = False
) -> float | None:
    """Salt as % w/w of the total of the ingredient rows, or (of_rest) of everything but the
    salt: "2 % of the produce and water", the convention of the Noma Guide, NCHFP and Katz,
    which SALT-001's minimum uses (owner decision 2026-10-26). None (the gate fails closed)
    when a mass is missing, not finite or negative."""
    rows = [i for i in recipe.ingredients if with_optional or i.required != "optional"]
    valid = [m for i in rows if (m := i.g_per_kg) is not None and math.isfinite(m) and m >= 0]
    if not rows or len(valid) < len(rows):
        return None
    total = math.fsum(valid)
    salt = math.fsum(m for i, m in zip(rows, valid, strict=True) if i.name == SALT)
    base = total - salt if of_rest else total
    return 100.0 * salt / base if base > 0 else None


def ph_deadline_line(fermentation_type: str) -> str:
    """The pH line of an acid-safety type: the two-step rule for salted vegetables, BOT-002's
    otherwise."""
    return VEG_PH_LINE if fermentation_type == "lacto_ferment" else PH_DEADLINE_LINE


def needs_ph_reminder(fermentation_type: str) -> bool:
    """Acid-safety types: the card carries the pH lines and Start batch creates the reminder."""
    return fermentation_type in ACID_SAFETY_TYPES


def safety_lines(recipe: RecipeLike) -> tuple[str, ...]:
    ft = recipe.fermentation_type
    lines: list[str] = []
    if needs_ph_reminder(ft):
        lines += [ph_deadline_line(ft), PH_LOG_LINE]
    if ft == "koji":
        lines.append(KOJI_TEMP_LINE)
        if CERTIFIED_KOJI_STARTER in recipe.starters:
            lines.append(TANE_KOJI_LINE)
    if ft in SALT_BARRIER_TYPES:
        lines.append(SALT_BARRIER_LINE)
    if ft == "vinegar":
        lines += VINEGAR_LINES
    return tuple(lines)


def _salt_reasons(
    recipe: RecipeLike, rule: str, lo: float, hi: float | None, high_rule: str = "",
    *, lo_of_rest: bool = False,
) -> list[str]:
    # The user may leave optional rows out, so the salt must pass with and without them.
    variants = [(True, "all rows")]
    if any(i.required == "optional" for i in recipe.ingredients):
        variants.append((False, "core rows only"))
    reasons = []
    for with_optional, label in variants:
        pct = salt_pct(recipe, with_optional=with_optional)
        low = salt_pct(recipe, with_optional=with_optional, of_rest=lo_of_rest)
        if pct is None or low is None:
            reasons.append(f"{rule}: salt % unknown, a mass is missing or invalid ({label})")
        # compared as shown, to 0.01 %: masses are stored to 0.1 g/kg, so Noma's "2 % of 980.4 g"
        # (19.608 g) is stored as 19.6 g/kg, 1.9992 % of the rest
        elif round(low, 2) < lo:
            basis = "of the rest" if lo_of_rest else "w/w"
            reasons.append(f"{rule}: salt {low:.2f} % {basis} < {lo} % ({label})")
        elif hi is not None and round(pct, 2) > hi:
            reasons.append(f"{high_rule}: salt {pct:.2f} % w/w > {hi} % ({label})")
    return reasons


def _temperature_reasons(recipe: RecipeLike, temps: list[float]) -> list[str]:
    reasons = []
    if scheme(recipe.fermentation_type) == "lactic":
        hot = GARUM_HOT_MIN_C if recipe.fermentation_type == "garum" else math.inf
        reasons += [
            f"TEMP-001: {t:g} °C > {LACTIC_MAX_C:g} °C" for t in temps if LACTIC_MAX_C < t < hot
        ]
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
        reasons += _salt_reasons(
            recipe, "SALT-001", SALT_MIN_PCT, SALT_MAX_PCT, "SALT-002", lo_of_rest=True
        )
    barrier_min = SALT_BARRIER_MIN_PCT.get(recipe.fermentation_type)
    if barrier_min is not None:
        reasons += _salt_reasons(recipe, "SALT-BARRIER", barrier_min, None)
    reasons += _temperature_reasons(recipe, temps)
    return GateResult(not reasons, tuple(reasons), safety_lines(recipe))
