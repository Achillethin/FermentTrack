"""Experimental variant operators (design § 5.2, Q13, Q31; § 7 "also gated").

A variant is a parent recipe (an active library recipe, or the user's own batch, Q16) with 1 to
MAX_OPERATORS operators applied:

- (i) **add**: a tier-T3 flavouring of the parent's type (ingredient_use_levels_v1.csv, role
  flavoring) at its use-level median share;
- (ii) **swap**: a core catalogue row of role base or flavoring (never salt or sugar; liquids
  and starters are other roles) replaced, mass kept, by another catalogue ingredient of the
  same role and kind (tagged for the parent's type and for every type the original is tagged
  for), at tier T2 or above;
- (iii) **temperature**: the first (active) stage moved to a temperature inside the profile's
  temp_range, outside the parent's documented span, that passes the gate. (The koji profile
  tops out at 35 °C, the certified tane-koji ceiling, so the range already holds that cap.)
- (v) **usda**: a user-picked USDA food (fdc_catalog_v1 nutrients) or a must-include catalogue
  ingredient at tier T0 or T1 that is not a staple (library.STAPLES), at USDA_SHARE of the
  mass (at most USDA_MAX_SHARE), labelled "aroma effect unknown"; salted or acidified types
  only.

Every operator keeps the salt and sugar % w/w of the total: an added row takes its share of the
parent's total mass and the rows other than salt and sugar shrink to make room, so the total
and the salt and sugar masses are unchanged. Sourdough (Q31) takes (ii) on its flour row and
(iii) only. In a variant the operators touch disjoint ingredients and at most one moves the
temperature. The gate itself (gate.check) runs on every variant in the service.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from functools import cache
from itertools import combinations as _combinations
from types import MappingProxyType
from typing import Literal

from fermenttrack.fdc_catalog import load_catalog
from fermenttrack.nutrients import NUTRIENTS
from fermenttrack.prediction.profiles import PROFILES
from fermenttrack.recommender import gate, library
from fermenttrack.recommender.library import Recipe, RecipeIngredient, Span

Kind = Literal["add", "swap", "temperature", "usda"]

MAX_OPERATORS = 3  # Q13, owner decision
USDA_MAX_SHARE = 0.10  # design § 7: operator (v) keeps the share at most 10 %
USDA_SHARE = 0.05  # the share operator (v) adds: half the ceiling (no typical use level exists)
USDA_TYPES = frozenset({"lacto_ferment", "kombucha", "kefir", "vinegar", "miso", "garum"})
SUGAR = "Cane sugar"
PRESERVED = frozenset({gate.SALT, SUGAR})  # their % w/w of the total never changes
SWAPPABLE_ROLES = frozenset({"base", "flavoring"})
SOURDOUGH_KINDS = frozenset({"swap", "temperature"})  # Q31
AROMA_UNKNOWN = "aroma effect unknown"
KIND_ORDER = {"add": 0, "swap": 1, "temperature": 2, "usda": 3}


class OperatorError(ValueError):
    """Operators that cannot be applied to this parent together."""


@dataclass(frozen=True)
class Operator:
    kind: Kind
    ingredient: str | None = None  # add, usda: the new row; swap: the row swapped in
    replaces: str | None = None  # swap: the parent's row it replaces
    share: float | None = None  # add, usda: mass share of the total
    to_c: float | None = None  # temperature: the first stage's new °C
    fdc_id: int | None = None  # usda: a USDA food (None: a catalogue ingredient)

    @property
    def key(self) -> str:
        """A stable identity: what the grid manifest, card ids and requests use."""
        if self.kind == "add":
            return f"add:{self.ingredient}"
        if self.kind == "swap":
            return f"swap:{self.replaces}>{self.ingredient}"
        if self.kind == "temperature":
            return f"temp:{self.to_c:g}"
        return f"usda:fdc:{self.fdc_id}" if self.fdc_id is not None else f"usda:{self.ingredient}"

    def touches(self) -> frozenset[str]:
        """The ingredient names this operator adds, removes or replaces."""
        return frozenset(n for n in (self.ingredient, self.replaces) if n is not None)


def sort_key(op: Operator) -> tuple[int, str]:
    return KIND_ORDER[op.kind], op.key


# ── USDA foods (operator v) ─────────────────────────────────────────────


@cache
def _usda_foods() -> Mapping[int, tuple[str, tuple[tuple[str, float], ...]]]:
    """fdc_id -> (description, nutrients g/100 g) from the bundled fdc_catalog_v1, the
    nutrients a USDA pick copies into the database (routers/batches.py)."""
    return MappingProxyType({
        int(r["fdc_id"]): (
            r["description"], tuple((k, float(r[k])) for k in NUTRIENTS if r[k] != "")
        )
        for r in load_catalog()
    })  # fmt: skip


def usda_food(fdc_id: int) -> tuple[str, tuple[tuple[str, float], ...]] | None:
    return _usda_foods().get(fdc_id)


# ── the parent's single operators ───────────────────────────────────────


def _total(recipe: Recipe) -> float:
    return math.fsum(i.g_per_kg.median for i in recipe.ingredients if i.g_per_kg is not None)


def _swappable(row: RecipeIngredient, ferment_type: str) -> bool:
    if ferment_type == "sourdough" and row.role != "base":
        return False  # Q31: the flour row only
    return (
        row.required == "core" and row.role in SWAPPABLE_ROLES and row.name not in PRESERVED
        and row.name in library.CATALOGUE_NAMES and row.g_per_kg is not None
    )  # fmt: skip


def temperature_ok(parent: Recipe, temp_c: float) -> bool:
    """Operator (iii)'s bounds: inside the profile's range, outside the parent's documented
    span, and through the gate with the first stage moved there."""
    lo, hi = PROFILES[parent.fermentation_type].temp_range
    if parent.temp_c is None or not lo <= temp_c <= hi:
        return False
    if parent.temp_c.lo <= temp_c <= parent.temp_c.hi:
        return False
    variant = apply(parent, (Operator("temperature", to_c=temp_c),))
    return gate.check(gate.from_recipe(variant), [temp_c]).ok


def singles(
    parent: Recipe,
    *,
    temperatures: Iterable[float] = (),
    must_include: Iterable[str] = (),
    usda_ids: Iterable[int] = (),
) -> tuple[Operator, ...]:
    """Every single operator the parent allows, sorted (sort_key). The grid's set is the call
    with no arguments: (i), (ii) and (iii) at the profile's temp_range[0], temp_c and
    temp_range[1] (design § 8.1's temperatures). temperatures adds (iii) candidates (the
    user's kitchen); must_include and usda_ids feed (v)."""
    ft = parent.fermentation_type
    names = {i.name for i in parent.ingredients}
    has_mass = _total(parent) > 0
    ops: list[Operator] = []
    if ft != "sourdough" and has_mass:
        ops += [
            Operator("add", u.ingredient, share=u.share_median)
            for u in library.use_levels()
            if u.fermentation_type == ft and u.role == "flavoring" and u.ingredient not in names
            and library.ingredient_tier(u.ingredient, ft) == 3
        ]  # fmt: skip
    for row in parent.ingredients:
        if not _swappable(row, ft):
            continue
        # "Same type": tagged for the parent's type and wherever the original is used, so a
        # substitute is of the same kind (rice koji never becomes fish in a fish sauce).
        uses = {ft, *library.CATALOGUE[row.name][1]}
        ops += [
            Operator("swap", name, replaces=row.name)
            for name, (role, systems) in sorted(library.CATALOGUE.items())
            if role == row.role and uses <= set(systems) and name not in names
            and name not in PRESERVED and library.ingredient_tier(name, ft) >= 2
        ]  # fmt: skip
    profile = PROFILES[ft]
    trio = (profile.temp_range[0], profile.temp_c, profile.temp_range[1])
    for t in sorted({round(float(x), 1) for x in (*trio, *temperatures) if math.isfinite(x)}):
        if temperature_ok(parent, t):
            ops.append(Operator("temperature", to_c=t))
    if ft in USDA_TYPES and has_mass:
        for name in dict.fromkeys(must_include):
            # staples (salt, sugar, water, flours, tea, starters) are never a (v) food: they
            # are the rows the recipe already sets, and salt and sugar must stay as they are
            if name not in names and name not in library.STAPLES and (
                library.ingredient_tier(name, ft) in (0, 1)
            ):
                ops.append(Operator("usda", name, share=USDA_SHARE))
        for fdc_id in sorted(set(usda_ids)):
            food = usda_food(fdc_id)
            if food is not None and food[0] not in names:
                ops.append(Operator("usda", food[0], share=USDA_SHARE, fdc_id=fdc_id))
    return tuple(sorted(ops, key=sort_key))


def grid_operators(parent: Recipe) -> tuple[Operator, ...]:
    """The single operators precomputed in the grid: all but (v), which is user-specific."""
    return singles(parent)


def combinations(
    ops: Iterable[Operator], max_n: int = MAX_OPERATORS
) -> Iterator[tuple[Operator, ...]]:
    """Every compatible combination of 1 to max_n operators, in a fixed order."""
    pool = sorted(ops, key=sort_key)
    for n in range(1, max_n + 1):
        for combo in _combinations(pool, n):
            if compatible(combo):
                yield combo


def compatible(ops: Sequence[Operator]) -> bool:
    """At most one temperature operator; the operators touch disjoint ingredients."""
    if sum(op.kind == "temperature" for op in ops) > 1 or len({op.key for op in ops}) < len(ops):
        return False
    seen: set[str] = set()
    for op in ops:
        if op.touches() & seen:
            return False
        seen |= op.touches()
    return True


# ── applying operators ──────────────────────────────────────────────────


def bounds_reasons(parent: Recipe, ops: Sequence[Operator]) -> list[str]:
    """Why these operators cannot form a variant of this parent (empty: they can). Design
    § 7's operator bounds plus the structural rules; the gate runs separately."""
    ft = parent.fermentation_type
    names = {i.name for i in parent.ingredients}
    reasons = []
    if not 1 <= len(ops) <= MAX_OPERATORS:
        reasons.append(f"a variant has 1 to {MAX_OPERATORS} operators, not {len(ops)}")
    if not compatible(ops):
        reasons.append("operators overlap: one temperature change, disjoint ingredients")
    rows = {i.name: i for i in parent.ingredients}
    lo, hi = PROFILES[ft].temp_range
    for op in ops:
        if ft == "sourdough" and op.kind not in SOURDOUGH_KINDS:
            reasons.append(f"{op.key}: sourdough takes a flour swap or a temperature only")
        if op.kind in ("add", "usda"):
            if op.ingredient in names:
                reasons.append(f"{op.key}: already in the recipe")
            if op.share is None or not 0.0 < op.share < 1.0:
                reasons.append(f"{op.key}: a share must be between 0 and 1")
        if op.kind == "usda":
            if ft not in USDA_TYPES:
                reasons.append(f"{op.key}: USDA foods go in salted or acidified types only")
            if op.share is not None and op.share > USDA_MAX_SHARE:
                reasons.append(f"{op.key}: share {op.share:g} > {USDA_MAX_SHARE:g}")
            if op.fdc_id is None and op.ingredient in library.STAPLES:
                reasons.append(f"{op.key}: a staple is never a USDA food")
        if op.kind == "swap":
            row = rows.get(op.replaces or "")
            if row is None or not _swappable(row, ft):
                reasons.append(f"{op.key}: {op.replaces!r} is not a swappable row")
            if op.ingredient in names:
                reasons.append(f"{op.key}: already in the recipe")
        if op.kind == "temperature":
            t = op.to_c
            if t is None or not math.isfinite(t) or not lo <= t <= hi:
                reasons.append(f"{op.key}: outside the profile's {lo:g}-{hi:g} °C")
            elif parent.temp_c is not None and parent.temp_c.lo <= t <= parent.temp_c.hi:
                reasons.append(f"{op.key}: inside the documented span, not a change")
    return reasons


def _scaled(row: RecipeIngredient, f: float) -> RecipeIngredient:
    s = row.g_per_kg
    assert s is not None
    return replace(row, g_per_kg=Span(s.median * f, s.lo * f, s.hi * f))


def _new_row(op: Operator, grams: float, ferment_type: str) -> RecipeIngredient:
    span = Span(grams, grams, grams)
    name = op.ingredient or ""
    if op.kind == "add":
        level = library.use_level(name, ferment_type)
        source = level.source if level else ""
        return RecipeIngredient(
            name, "existing", "flavoring", span, "core", source,
            "operator (i): typical use level", None,
        )  # fmt: skip
    if op.fdc_id is not None:
        food = usda_food(op.fdc_id)
        nutrients = food[1] if food else ()
        return RecipeIngredient(
            name, "usda", "flavoring", span, "core", f"USDA FoodData Central {op.fdc_id}",
            "operator (v): your USDA pick", AROMA_UNKNOWN, nutrients=nutrients, fdc_id=op.fdc_id,
        )  # fmt: skip
    return RecipeIngredient(
        name, "existing", "flavoring", span, "core", "", "operator (v): your ingredient",
        AROMA_UNKNOWN,
    )  # fmt: skip


def apply(parent: Recipe, ops: Sequence[Operator]) -> Recipe:
    """The parent with the operators applied (its key, name and documented spans kept). Raises
    OperatorError on overlapping or misplaced operators; it does not check the bounds
    (bounds_reasons) or the gate."""
    if not compatible(ops):
        raise OperatorError("operators overlap: one temperature change, disjoint ingredients")
    names = [i.name for i in parent.ingredients]
    rows = list(parent.ingredients)
    for op in ops:
        if op.kind != "swap":
            continue
        if op.replaces not in names or op.ingredient in names or op.ingredient is None:
            raise OperatorError(f"{op.key}: not a swap of a row of {parent.key}")
        i = names.index(op.replaces)
        rows[i] = replace(
            rows[i], name=op.ingredient, catalogue_status="existing", source="",
            notes=f"operator (ii): swapped in for {op.replaces}", label=None, nutrients=None,
            fdc_id=None,
        )  # fmt: skip
    added = [op for op in ops if op.kind in ("add", "usda")]
    if added:
        if any(op.ingredient in names or op.ingredient is None for op in added):
            raise OperatorError("an added ingredient is already in the recipe")
        shares = [op.share or 0.0 for op in added]
        if any(not 0.0 < s < 1.0 for s in shares):
            raise OperatorError("an added share must be between 0 and 1")
        total = math.fsum(r.g_per_kg.median for r in rows if r.g_per_kg is not None)
        fixed = math.fsum(
            r.g_per_kg.median for r in rows if r.g_per_kg is not None and r.name in PRESERVED
        )
        room = total - fixed - math.fsum(shares) * total
        if total <= 0 or room <= 0:
            raise OperatorError("no room for the added ingredients")
        f = room / (total - fixed)
        rows = [r if r.g_per_kg is None or r.name in PRESERVED else _scaled(r, f) for r in rows]
        rows += [
            _new_row(op, s * total, parent.fermentation_type)
            for op, s in zip(added, shares, strict=True)
        ]
    schedule = parent.temp_schedule
    temp = next((op for op in ops if op.kind == "temperature"), None)
    if temp is not None:
        if temp.to_c is None or not math.isfinite(temp.to_c):
            raise OperatorError("a temperature operator needs a finite temperature")
        if schedule:  # Q27: the active (first) stage moves; later stages keep their own
            (h0, _), *later = schedule
            schedule = ((h0, temp.to_c), *later)
    return replace(parent, ingredients=tuple(rows), temp_schedule=schedule)
