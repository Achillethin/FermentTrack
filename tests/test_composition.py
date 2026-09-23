"""compose(): recipe × per-100 g nutrients → batch composition. Synthetic data, no DB."""

from __future__ import annotations

import pytest

from fermenttrack.composition import RecipeItem, SaltSuggestion, compose, suggest_salt, to_grams

SALT = {"sodium": 38.758}
CABBAGE = {"water": 92.2, "sugars_total": 3.2, "sodium": 0.018}
SUGAR = {"sucrose": 99.8, "sugars_total": 99.8}
WATER = {"water": 100.0, "sodium": 0.004}


def test_to_grams_closed_unit_set() -> None:
    assert to_grams(1.5, "kg") == 1500.0
    assert to_grams(1.0, "L") == 1000.0  # density 1.0 assumption
    assert to_grams(250.0, "ml") == 250.0
    assert to_grams(1.0, "cup") is None
    assert to_grams(None, "g") is None
    assert to_grams(5.0, None) is None


def test_lacto_ferment_brine_salt_pct() -> None:
    c = compose([RecipeItem("Cabbage", 1.0, "kg", CABBAGE), RecipeItem("Salt", 20.0, "g", SALT)])
    assert c.total_mass_g == 1020.0
    assert c.coverage == 1.0
    assert c.salt_pct == pytest.approx(20 / 1020 * 100)  # added salt only
    assert c.nutrients["sodium"].grams == pytest.approx(7.9316)  # incl. cabbage's own Na
    assert c.nutrients["sugars_total"].grams == pytest.approx(32.0)
    assert c.nutrients["sugars_total"].missing_from == ["Salt"]  # unknown, not zero


def test_kombucha_unmapped_tea_lowers_coverage() -> None:
    c = compose(
        [
            RecipeItem("Water", 1.0, "L", WATER),
            RecipeItem("Cane sugar", 80.0, "g", SUGAR),
            RecipeItem("Black/green tea", 8.0, "g", {}),
        ]
    )
    assert c.total_mass_g == 1088.0
    assert c.mapped_mass_g == 1080.0
    assert c.coverage == pytest.approx(1080 / 1088)
    assert c.unmapped == ["Black/green tea"]
    assert c.nutrients["sucrose"].grams == pytest.approx(79.84)
    assert c.per_100g("sucrose") == pytest.approx(79.84 / 1088 * 100)
    assert c.salt_pct is None  # water has sodium, but no Salt row = unknown, not ~0.01 %


def test_unquantified_items_are_excluded_not_guessed() -> None:
    c = compose([RecipeItem("Salt", 1.0, "tbsp", SALT), RecipeItem("Cabbage", None, None, CABBAGE)])
    assert c.unquantified == ["Salt", "Cabbage"]
    assert c.total_mass_g == 0.0
    assert c.coverage == 0.0
    assert c.nutrients == {}


def test_empty_recipe() -> None:
    c = compose([])
    assert (c.total_mass_g, c.coverage, c.salt_pct, c.nutrients) == (0.0, 0.0, None, {})


def test_explicit_zero_salt_is_a_known_zero() -> None:
    c = compose([RecipeItem("Cabbage", 1.0, "kg", CABBAGE), RecipeItem("Salt", 0.0, "g", SALT)])
    assert c.salt_pct == 0.0  # logged 0 g = known unsalted, despite cabbage's own sodium


def test_unsalted_cabbage_salt_is_unknown() -> None:
    assert compose([RecipeItem("Cabbage", 1.0, "kg", CABBAGE)]).salt_pct is None


def test_zero_total_mass_per_100g_does_not_divide_by_zero() -> None:
    c = compose([RecipeItem("Salt", 0.0, "g", SALT)])
    assert c.per_100g("sodium") == 0.0
    assert c.salt_pct == 0.0


# ── suggest_salt ──

def test_lacto_ferment_suggests_3pct_of_base_including_brine_water() -> None:
    s = suggest_salt(
        "lacto_ferment",
        [RecipeItem("Chilies", 500.0, "g", {}), RecipeItem("Water", 0.5, "L", WATER)],
    )
    assert s == SaltSuggestion(pct=3.0, basis_g=1000.0, grams=30.0)


def test_sourdough_basis_is_flour_only() -> None:
    s = suggest_salt(
        "sourdough",
        [RecipeItem("White wheat flour", 500.0, "g", {}), RecipeItem("Water", 350.0, "g", WATER)],
    )
    assert s == SaltSuggestion(pct=2.0, basis_g=500.0, grams=10.0)


def test_miso_and_garum_defaults() -> None:
    assert suggest_salt("miso", [RecipeItem("Soybeans", 1.0, "kg", {})]).grams == 210.0
    assert suggest_salt("garum", [RecipeItem("Anchovies", 1.0, "kg", {})]).grams == 200.0


def test_no_suggestion_once_salt_logged_even_zero() -> None:
    items = [RecipeItem("Cabbage", 1.0, "kg", {}), RecipeItem("Salt", 0.0, "g", SALT, "additive")]
    assert suggest_salt("lacto_ferment", items) is None


def test_no_suggestion_without_base_mass_or_for_unsalted_ferments() -> None:
    assert suggest_salt("lacto_ferment", []) is None
    assert suggest_salt("lacto_ferment", [RecipeItem("Cabbage", None, None, {})]) is None
    assert suggest_salt("lacto_ferment", [RecipeItem("Mint", 5.0, "g", {}, "flavoring")]) is None
    assert suggest_salt("kombucha", [RecipeItem("Water", 1.0, "L", WATER)]) is None
