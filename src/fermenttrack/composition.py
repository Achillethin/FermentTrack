"""Batch nutrient composition at t=0: recipe quantities × reference nutrients per 100 g.

Pure, no DB. Figures are LOWER BOUNDS whenever coverage < 1 or a nutrient's
missing_from is non-empty — unmapped / unreported means unknown, never zero.
Design: docs/superpowers/specs/2026-09-23-ingredient-nutrients-design.md § 3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import NamedTuple

from fermenttrack.seed_data import FLOURS

# ponytail: ml/L assume density 1.0 — exact for water, ~3 % low for milk, ~40 % for
# honey. Add a per-ingredient density column when a recipe needs it.
_GRAMS_PER_UNIT = {"g": 1.0, "kg": 1000.0, "mg": 0.001, "ml": 1.0, "l": 1000.0}


class RecipeItem(NamedTuple):
    name: str
    quantity: float | None
    unit: str | None
    per_100g: dict[str, float]  # empty = ingredient has no reference data
    role: str = "base"


# ferment type -> (salt fraction, basis). Basis None = every logged base-role
# item (vegetables + brine water, soy + grain, fish); otherwise only those names.
# Spec § 3.1. lacto_ferment's 3 % sits in SALT-001's recommended 2-5 % band.
SALT_DEFAULTS: dict[str, tuple[float, frozenset[str] | None]] = {
    "lacto_ferment": (0.03, None),
    "miso": (0.21, None),  # of DRY soy + grain (~12 % of finished miso)
    "garum": (0.20, None),
    "sourdough": (0.02, FLOURS),
}


class SaltSuggestion(NamedTuple):
    pct: float
    basis_g: float
    grams: float


@dataclass
class NutrientTotal:
    grams: float = 0.0
    missing_from: list[str] = field(default_factory=list)


@dataclass
class Composition:
    total_mass_g: float
    mapped_mass_g: float
    nutrients: dict[str, NutrientTotal]
    unmapped: list[str]
    unquantified: list[str]

    @property
    def coverage(self) -> float:
        return self.mapped_mass_g / self.total_mass_g if self.total_mass_g else 0.0

    salt_g: float | None = None  # grams of logged Salt rows; None = no Salt row logged

    def per_100g(self, nutrient: str) -> float:
        if not self.total_mass_g:
            return 0.0
        return self.nutrients[nutrient].grams / self.total_mass_g * 100

    @property
    def salt_pct(self) -> float | None:
        """Added-salt share of batch mass. None = salt not logged (unknown), or any
        recipe row has no usable quantity/unit (the denominator would be incomplete).
        A logged 0 g is a known 0. Intrinsic food sodium stays in nutrients["sodium"],
        not here - otherwise unsalted cabbage would read as ~0.05 % "salt". Not fed to
        safety."""
        if self.salt_g is None or self.unquantified:
            return None
        return self.salt_g / self.total_mass_g * 100 if self.total_mass_g else 0.0


def to_grams(quantity: float | None, unit: str | None) -> float | None:
    if quantity is None or unit is None:
        return None
    factor = _GRAMS_PER_UNIT.get(unit.strip().lower())
    return None if factor is None else quantity * factor


def compose(items: list[RecipeItem]) -> Composition:
    total = mapped = 0.0
    salt_g: float | None = None
    unmapped: list[str] = []
    unquantified: list[str] = []
    weighed: list[tuple[RecipeItem, float]] = []
    for item in items:
        grams = to_grams(item.quantity, item.unit)
        if grams is None:
            unquantified.append(item.name)
            continue
        total += grams
        if item.name == "Salt":
            salt_g = (salt_g or 0.0) + grams
        if not item.per_100g:
            unmapped.append(item.name)
            continue
        mapped += grams
        weighed.append((item, grams))

    reported = sorted({n for item, _ in weighed for n in item.per_100g})
    nutrients = {n: NutrientTotal() for n in reported}
    for item, grams in weighed:
        for n, acc in nutrients.items():
            if n in item.per_100g:
                acc.grams += item.per_100g[n] * grams / 100
            else:
                acc.missing_from.append(item.name)
    return Composition(total, mapped, nutrients, unmapped, unquantified, salt_g)


def suggest_salt(ferment_type: str, items: list[RecipeItem]) -> SaltSuggestion | None:
    """Default salt to PRE-FILL in the recipe form — never auto-logged (spec § 3.1).

    None when the ferment takes no salt, any Salt row exists (even 0 g, an
    explicit choice), or no base mass is logged yet.
    """
    default = SALT_DEFAULTS.get(ferment_type)
    if default is None or any(i.name == "Salt" for i in items):
        return None
    fraction, basis_names = default
    basis = 0.0
    for i in items:
        grams = to_grams(i.quantity, i.unit)
        if (
            grams is not None
            and i.role == "base"
            and (basis_names is None or i.name in basis_names)
        ):
            basis += grams
    if basis == 0.0:
        return None
    return SaltSuggestion(
        pct=round(fraction * 100, 2),
        basis_g=basis,
        grams=round(basis * fraction, 1),
    )
