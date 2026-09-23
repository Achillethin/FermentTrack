"""Sanity checks on the committed, frozen FDC snapshot — catches a wrong food match."""

from __future__ import annotations

from collections import defaultdict

from fermenttrack.nutrients import NUTRIENTS, load_snapshot
from fermenttrack.seed_data import (
    INGREDIENT_FDC_MAP,
    INGREDIENT_SEED_DATA,
    INGREDIENT_SEED_DATA_V2,
    INGREDIENT_SEED_DATA_V3,
    RETIRED_V3,
)

ROWS = load_snapshot()
BY_ING: dict[str, dict[str, float]] = defaultdict(dict)
for _r in ROWS:
    BY_ING[_r.ingredient_name][_r.nutrient] = _r.amount_per_100g


def test_every_mapped_ingredient_is_in_snapshot_and_active_seed() -> None:
    all_seed = INGREDIENT_SEED_DATA + INGREDIENT_SEED_DATA_V2 + INGREDIENT_SEED_DATA_V3
    active = {n for n, _r, _s in all_seed} - set(RETIRED_V3)
    assert set(BY_ING) == set(INGREDIENT_FDC_MAP)
    assert set(INGREDIENT_FDC_MAP) <= active


def test_codes_known_and_amounts_are_plausible_grams_per_100g() -> None:
    for r in ROWS:
        assert r.nutrient in NUTRIENTS
        assert 0.0 <= r.amount_per_100g <= 100.0, r


def test_proximates_do_not_exceed_100g() -> None:
    for name, n in BY_ING.items():
        proximate = sum(n.get(k, 0.0) for k in ("water", "protein", "fat", "carbohydrate"))
        assert proximate <= 102.0, (name, proximate)  # FDC rounding / ash slack


def test_anchor_foods_match_known_composition() -> None:
    sugar = BY_ING["Cane sugar"]
    assert max(sugar.get("sucrose", 0.0), sugar.get("sugars_total", 0.0)) >= 99.0
    assert 38.0 <= BY_ING["Salt"]["sodium"] <= 39.5  # NaCl is 39.3 % Na
    assert 4.0 <= BY_ING["Milk"]["sugars_total"] <= 6.0
    assert 65.0 <= BY_ING["White wheat flour"]["carbohydrate"] <= 80.0
    assert 30.0 <= BY_ING["Soybeans"]["protein"] <= 40.0
    assert 75.0 <= BY_ING["White rice"]["carbohydrate"] <= 82.0
    assert BY_ING["Water"]["water"] >= 99.0
