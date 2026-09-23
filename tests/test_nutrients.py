"""Pure checks on the nutrient registry and FDC → snapshot conversion. No network, no DB."""

from __future__ import annotations

import uuid

import pytest

from fermenttrack.nutrients import (
    SnapshotRow,
    fdc_amount_to_grams,
    nutrient_seed_rows,
    snapshot_rows,
)


def test_fdc_amount_to_grams_converts_mass_units() -> None:
    assert fdc_amount_to_grams(500.0, "MG") == pytest.approx(0.5)
    assert fdc_amount_to_grams(3.0, "UG") == pytest.approx(3e-6)
    assert fdc_amount_to_grams(12.5, "G") == 12.5


def test_fdc_amount_to_grams_rejects_non_mass_units() -> None:
    with pytest.raises(ValueError):
        fdc_amount_to_grams(52.0, "KCAL")


def _food(description: str, nutrients: list[tuple[int, float, str]]) -> dict:
    return {
        "fdcId": 111,
        "description": description,
        "foodNutrients": [
            {"nutrientId": nid, "value": value, "unitName": unit} for nid, value, unit in nutrients
        ],
    }


def test_snapshot_rows_uses_exact_match_prefers_first_id_and_skips_unreported() -> None:
    foods = [
        _food("Cabbage, red, raw", [(1003, 9.9, "G")]),
        _food(
            "Cabbage, raw",
            [
                (1003, 1.28, "G"),      # protein
                (2000, 3.2, "G"),       # sugars_total, preferred id
                (1063, 3.0, "G"),       # sugars_total, fallback id, must be ignored
                (1093, 18.0, "MG"),     # sodium, converted to g
                (1008, 25.0, "KCAL"),   # energy, not in NUTRIENTS, ignored
            ],
        ),
    ]
    rows = snapshot_rows("Cabbage", "Cabbage, raw", foods)
    by_code = {r.nutrient: r for r in rows}

    assert by_code["protein"].amount_per_100g == 1.28
    assert by_code["sugars_total"].amount_per_100g == 3.2
    assert by_code["sodium"].amount_per_100g == pytest.approx(0.018)
    assert "lactose" not in by_code  # unreported, so absent, never 0
    assert {r.fdc_id for r in rows} == {"111"}
    assert {r.ingredient_name for r in rows} == {"Cabbage"}


def test_snapshot_rows_fails_loudly_without_exactly_one_match() -> None:
    foods = [_food("Cabbage, red, raw", [(1003, 1.0, "G")])]
    with pytest.raises(ValueError, match="Cabbage, red, raw"):
        snapshot_rows("Cabbage", "Cabbage, raw", foods)


def test_nutrient_seed_rows_rejects_names_missing_from_ingredients_table() -> None:
    snapshot = [SnapshotRow("Unicorn", "1", "protein", 1.0)]
    with pytest.raises(ValueError, match="Unicorn"):
        nutrient_seed_rows(snapshot, {"Cabbage": uuid.uuid4()})


def test_nutrient_seed_rows_carries_provenance() -> None:
    cabbage_id = uuid.uuid4()
    rows = nutrient_seed_rows(
        [SnapshotRow("Cabbage", "169975", "protein", 1.28)], {"Cabbage": cabbage_id}
    )
    assert rows[0]["ingredient_id"] == cabbage_id
    assert rows[0]["source"] == "usda_fdc"
    assert rows[0]["source_food_id"] == "169975"
    assert rows[0]["source_version"] == "fdc_nutrients_v1"
