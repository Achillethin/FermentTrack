"""Experimental variant operators (design § 5.2, Q13, Q31; § 7 "also gated"; build plan B7):
the catalogue each library recipe allows, salt and sugar kept by rescaling, the bounds, the
sourdough restrictions and the 3-operator limit."""

from __future__ import annotations

import math

import pytest

from fermenttrack.prediction.profiles import PROFILES
from fermenttrack.recommender import gate, library, run
from fermenttrack.recommender import operators as O
from fermenttrack.recommender.library import Recipe

KRAUT = "sauerkraut_dry_salted"
KIMCHI = "napa_kimchi_room_temp"
KOMBUCHA = "black_tea_kombucha_1f"
GARUM = "pacific_sand_lance_rice_koji_fish_sauce"
PERSIMMON = 169941  # USDA FDC: Persimmons, japanese, raw


def _recipe(key: str) -> Recipe:
    recipe = library.get(key)
    assert recipe is not None
    return recipe


def _keys(recipe: Recipe) -> list[str]:
    return [op.key for op in O.grid_operators(recipe)]


def _mass(recipe: Recipe, name: str) -> float:
    return math.fsum(
        i.g_per_kg.median for i in recipe.ingredients if i.name == name and i.g_per_kg is not None
    )


def _total(recipe: Recipe) -> float:
    return math.fsum(i.g_per_kg.median for i in recipe.ingredients if i.g_per_kg is not None)


def _pct(recipe: Recipe, name: str) -> float:
    return 100.0 * _mass(recipe, name) / _total(recipe)


# ── the catalogue ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        (KRAUT, ["add:Fresh ginger", "swap:Cabbage>Cucumber", "swap:Cabbage>Napa cabbage",
                 "temp:16", "temp:20", "temp:24"]),
        ("rice_koji_steamed_rice", ["swap:White rice>Pearl barley", "swap:White rice>Soybeans"]),
        # rice koji is never swapped for fish: Mackerel is not tagged where White rice is used
        (GARUM, ["swap:Anchovies>Mackerel", "temp:30"]),
        ("lactic_fresh_cheese_curd", ["temp:28", "temp:30", "temp:32"]),
        ("wine_orleans_surface", ["swap:Red wine>Hard cider", "swap:Red wine>White wine"]),
        ("green_dominant_kombucha", ["temp:20"]),  # Black tea leaves is already in it
        ("rye_sour", ["swap:Rye flour>White wheat flour", "swap:Rye flour>Whole wheat flour",
                      "temp:22"]),
    ],
)  # fmt: skip
def test_the_grid_operator_catalogue(key: str, expected: list[str]) -> None:
    assert _keys(_recipe(key)) == expected


def test_catalogue_summary_over_the_library() -> None:
    """Informational (the handoff's operator catalogue), pinned: 74 single grid operators
    over the 20 active recipes."""
    counts: dict[str, int] = {}
    per_type: dict[str, int] = {}
    for r in library.active():
        for op in O.grid_operators(r):
            counts[op.kind] = counts.get(op.kind, 0) + 1
            per_type[r.fermentation_type] = per_type.get(r.fermentation_type, 0) + 1
    print(f"\noperators by kind {counts}; by type {per_type}")
    assert counts == {"add": 1, "swap": 42, "temperature": 28}
    assert "usda" not in counts  # (v) is user-specific


def test_add_only_takes_a_t3_flavouring_of_the_same_type() -> None:
    for r in library.active():
        for op in O.grid_operators(r):
            if op.kind != "add":
                continue
            assert op.ingredient is not None
            level = library.use_level(op.ingredient, r.fermentation_type)
            assert level is not None and level.role == "flavoring"
            assert library.ingredient_tier(op.ingredient, r.fermentation_type) == 3
            assert op.share == level.share_median
    # ginger is T3 for lacto only: kimchi already has it, kombucha has no use-level row
    assert not [op for op in O.grid_operators(_recipe(KOMBUCHA)) if op.kind == "add"]


def test_a_swap_keeps_the_role_and_needs_t2() -> None:
    for r in library.active():
        rows = {i.name: i for i in r.ingredients}
        for op in O.grid_operators(r):
            if op.kind != "swap":
                continue
            assert op.replaces is not None and op.ingredient is not None
            old = rows[op.replaces]
            assert old.role in ("base", "flavoring") and old.required == "core"
            assert old.name not in O.PRESERVED
            role, systems = library.CATALOGUE[op.ingredient]
            assert role == old.role and r.fermentation_type in systems
            assert library.ingredient_tier(op.ingredient, r.fermentation_type) >= 2
            variant = O.apply(r, [op])
            assert _mass(variant, op.ingredient) == _mass(r, op.replaces)  # mass kept
            assert _total(variant) == pytest.approx(_total(r), abs=1e-9)


# ── salt and sugar kept by rescaling ────────────────────────────────────


@pytest.mark.parametrize("key", [r.key for r in library.active() if r.handoff != "planner"])
def test_every_combination_keeps_salt_and_sugar_and_the_total(key: str) -> None:
    recipe = _recipe(key)
    extra = [O.Operator("usda", food[0], share=O.USDA_SHARE, fdc_id=PERSIMMON)] if (
        recipe.fermentation_type in O.USDA_TYPES and (food := O.usda_food(PERSIMMON))
    ) else []  # fmt: skip
    n = 0
    for combo in O.combinations([*O.grid_operators(recipe), *extra]):
        variant = O.apply(recipe, combo)
        n += 1
        assert _total(variant) == pytest.approx(_total(recipe), rel=1e-12)
        for name in O.PRESERVED:
            assert _pct(variant, name) == pytest.approx(_pct(recipe, name), rel=1e-12)
        like, parent = gate.from_recipe(variant), gate.from_recipe(recipe)
        if recipe.fermentation_type in gate.SALT_GATED_TYPES:
            assert gate.salt_pct(like) == pytest.approx(gate.salt_pct(parent), rel=1e-12)
        for op in combo:
            if op.kind in ("add", "usda"):
                assert op.ingredient is not None and op.share is not None
                assert _mass(variant, op.ingredient) / _total(variant) == pytest.approx(op.share)
    assert n >= 1


def test_adding_shrinks_the_other_rows_not_salt() -> None:
    kraut = _recipe(KRAUT)
    variant = O.apply(kraut, [O.Operator("add", "Fresh ginger", share=0.0078)])
    assert _mass(variant, "Salt") == _mass(kraut, "Salt")
    assert _mass(variant, "Cabbage") == pytest.approx(_mass(kraut, "Cabbage") - 7.8)
    assert _mass(variant, "Fresh ginger") == pytest.approx(7.8)
    ginger = next(i for i in variant.ingredients if i.name == "Fresh ginger")
    assert ginger.role == "flavoring" and ginger.required == "core"
    assert ginger.source == library.use_level("Fresh ginger", "lacto_ferment").source  # type: ignore[union-attr]


def test_sugar_is_kept_in_kombucha() -> None:
    kombucha = _recipe(KOMBUCHA)
    food = O.usda_food(PERSIMMON)
    assert food is not None
    op = O.Operator("usda", food[0], share=O.USDA_SHARE, fdc_id=PERSIMMON)
    variant = O.apply(kombucha, [op])
    assert _pct(variant, O.SUGAR) == pytest.approx(_pct(kombucha, O.SUGAR), rel=1e-12)
    assert _mass(variant, O.SUGAR) == _mass(kombucha, O.SUGAR)


# ── (iii) temperature ───────────────────────────────────────────────────


def test_temperature_operators_stay_in_the_profile_outside_the_documented_span() -> None:
    for r in library.active():
        assert r.temp_c is not None
        lo, hi = PROFILES[r.fermentation_type].temp_range
        for op in O.grid_operators(r):
            if op.kind == "temperature":
                assert op.to_c is not None and lo <= op.to_c <= hi
                assert not r.temp_c.lo <= op.to_c <= r.temp_c.hi
                assert gate.check(gate.from_recipe(O.apply(r, [op])), [op.to_c]).ok
    kraut = _recipe(KRAUT)  # documented 21.1-23.9 °C, profile 16-24 °C
    assert O.temperature_ok(kraut, 18.0) and not O.temperature_ok(kraut, 22.0)
    assert not O.temperature_ok(kraut, 25.0)  # outside the profile
    assert not O.temperature_ok(_recipe(GARUM), 60.0)  # TEMP-001
    assert "temp:18" in [op.key for op in O.singles(kraut, temperatures=(18.04,))]


def test_a_temperature_operator_moves_the_first_stage_only() -> None:
    garum = _recipe(GARUM)
    assert garum.temp_schedule == ((0.0, 20.0), (48.0, 18.0))
    variant = O.apply(garum, [O.Operator("temperature", to_c=30.0)])
    assert variant.temp_schedule == ((0.0, 30.0), (48.0, 18.0))
    assert variant.ingredients == garum.ingredients and variant.temp_c == garum.temp_c
    kraut = _recipe(KRAUT)
    assert O.apply(kraut, [O.Operator("temperature", to_c=16.0)]) == kraut


# ── (v) USDA foods ──────────────────────────────────────────────────────


def test_usda_foods_go_in_salted_or_acidified_types_at_most_10_percent() -> None:
    food = O.usda_food(PERSIMMON)
    assert food is not None and food[0].startswith("Persimmons") and dict(food[1])["water"] > 50
    for r in library.active():
        ops = O.singles(r, must_include=["Garlic", "Fresh ginger"], usda_ids=[PERSIMMON, -1])
        usda = [op for op in ops if op.kind == "usda"]
        if r.fermentation_type not in O.USDA_TYPES:  # cheese, koji, sourdough
            assert not usda, r.key
            continue
        keys = {op.key for op in usda}
        assert f"usda:fdc:{PERSIMMON}" in keys and "usda:fdc:-1" not in keys
        assert "usda:Fresh ginger" not in keys  # T2: not a (v) food
        if "Garlic" not in {i.name for i in r.ingredients}:
            assert "usda:Garlic" in keys  # T1
        assert all(op.share == O.USDA_SHARE <= O.USDA_MAX_SHARE for op in usda)
    kraut = _recipe(KRAUT)
    over = O.Operator("usda", "Garlic", share=0.2)
    assert any("> 0.1" in why for why in O.bounds_reasons(kraut, [over]))
    cheese = _recipe("lactic_fresh_cheese_curd")
    assert any("salted or acidified" in why for why in O.bounds_reasons(
        cheese, [O.Operator("usda", "Garlic", share=0.05)]
    ))  # fmt: skip


def test_a_usda_row_runs_with_its_own_nutrients_and_is_labelled() -> None:
    kraut = _recipe(KRAUT)
    food = O.usda_food(PERSIMMON)
    assert food is not None
    variant = O.apply(kraut, [O.Operator("usda", food[0], share=0.05, fdc_id=PERSIMMON)])
    row = next(i for i in variant.ingredients if i.fdc_id == PERSIMMON)
    assert row.label == O.AROMA_UNKNOWN and row.nutrients == food[1]
    rows, skipped = run.recipe_rows(variant)
    booked = {r.name: r for r in rows}
    assert food[0] in booked and not skipped
    assert booked[food[0]].per_100g == dict(food[1])
    assert booked[food[0]].quantity == pytest.approx(50.0)


# ── sourdough (Q31) ─────────────────────────────────────────────────────


def test_sourdough_takes_a_flour_swap_or_a_temperature_only() -> None:
    for r in library.active():
        if r.handoff != "planner":
            continue
        kinds = {op.kind for op in O.singles(r, must_include=["Garlic"], usda_ids=[PERSIMMON])}
        assert kinds <= {"swap", "temperature"}, r.key
        for op in O.grid_operators(r):
            if op.kind == "swap":
                assert op.replaces in run.BAKE_FLOUR and op.ingredient in run.BAKE_FLOUR
    rye = _recipe("rye_sour")
    add = O.Operator("add", "Fresh ginger", share=0.01)
    assert any("sourdough takes" in why for why in O.bounds_reasons(rye, [add]))


@pytest.mark.parametrize(
    ("key", "swap", "flour"),
    [
        ("rye_sour", None, "rye_t130"),  # the style's own flour, unchanged
        ("lievito_madre", None, "t45"),  # booked as White wheat flour, baked as its T45
        ("rye_sour", "White wheat flour", "t65"),
        ("lievito_madre", "Whole wheat flour", "t150"),
        ("levain_liquide", "Rye flour", "rye_t130"),
    ],
)
def test_a_swapped_flour_bakes_as_its_planner_grade(key: str, swap: str | None, flour: str) -> None:
    recipe = _recipe(key)
    if swap is not None:
        old = next(i.name for i in recipe.ingredients if i.role == "base")
        recipe = O.apply(recipe, [O.Operator("swap", swap, replaces=old)])
    assert run.bake_plan(recipe, 26.0, 10.0)["levain"]["flour"] == {flour: 1.0}


# ── at most 3, disjoint, one temperature ────────────────────────────────


def test_at_most_three_operators_touching_disjoint_ingredients() -> None:
    kimchi = _recipe(KIMCHI)
    combos = list(O.combinations(O.grid_operators(kimchi)))
    assert max(len(c) for c in combos) == O.MAX_OPERATORS
    for combo in combos:
        assert O.compatible(combo)
        assert sum(op.kind == "temperature" for op in combo) <= 1
        touched = [n for op in combo for n in op.touches()]
        assert len(touched) == len(set(touched))
    ops = O.grid_operators(kimchi)
    four = [
        op for op in ops if op.key in ("swap:Garlic>Lemongrass", "swap:Napa cabbage>Cabbage",
                                       "swap:Onion>Dill", "swap:Chilies>Caraway seeds")
    ]  # fmt: skip
    assert len(four) == 4 and O.compatible(four)
    assert any("1 to 3 operators" in why for why in O.bounds_reasons(kimchi, four))
    two_temps = [O.Operator("temperature", to_c=16.0), O.Operator("temperature", to_c=24.0)]
    assert not O.compatible(two_temps)
    with pytest.raises(O.OperatorError):
        O.apply(kimchi, two_temps)
    same_row = [O.Operator("swap", "Dill", replaces="Onion"),
                O.Operator("swap", "Caraway seeds", replaces="Onion")]  # fmt: skip
    assert not O.compatible(same_row)
    with pytest.raises(O.OperatorError):
        O.apply(kimchi, [O.Operator("swap", "Dill", replaces="Not a row")])
    with pytest.raises(O.OperatorError):
        O.apply(kimchi, [O.Operator("add", "Fresh ginger", share=0.01)])  # already in it
