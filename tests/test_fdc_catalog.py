"""Pure checks on the FDC bulk-CSV → wide catalog conversion. No network, no DB."""

from __future__ import annotations

from pathlib import Path

import pytest

from fermenttrack.fdc_catalog import (
    COLUMNS,
    build_catalog_rows,
    catalog_seed_rows,
    load_catalog,
    write_catalog,
)

FOODS = [
    {
        "fdc_id": "1", "data_type": "sr_legacy_food",
        "description": "Cabbage, raw", "food_category_id": "11",
    },
    {
        "fdc_id": "2", "data_type": "foundation_food",
        "description": "Salt, table", "food_category_id": "2",
    },
    {
        "fdc_id": "3", "data_type": "sub_sample_food",
        "description": "Cabbage sample", "food_category_id": "11",
    },
    {
        "fdc_id": "4", "data_type": "branded_food",
        "description": "Brand X", "food_category_id": "",
    },
]
NUTRIENT_UNITS = [
    {"id": "1003", "unit_name": "G"},
    {"id": "1093", "unit_name": "MG"},
    {"id": "2000", "unit_name": "G"},
    {"id": "1063", "unit_name": "G"},
    {"id": "1008", "unit_name": "KCAL"},
]
CATEGORIES = [
    {"id": "11", "description": "Vegetables and Vegetable Products"},
    {"id": "2", "description": "Spices and Herbs"},
]
FOOD_NUTRIENTS = [
    {"fdc_id": "1", "nutrient_id": "1003", "amount": "1.28"},
    {"fdc_id": "1", "nutrient_id": "2000", "amount": "3.2"},   # sugars_total, preferred id
    {"fdc_id": "1", "nutrient_id": "1063", "amount": "3.0"},   # sugars_total fallback: ignored
    {"fdc_id": "1", "nutrient_id": "1093", "amount": "18"},    # sodium mg -> g
    {"fdc_id": "1", "nutrient_id": "1008", "amount": "25"},    # kcal: not in NUTRIENTS
    {"fdc_id": "2", "nutrient_id": "1093", "amount": "38758"},
    {"fdc_id": "3", "nutrient_id": "1003", "amount": "9"},     # excluded data_type
]


def _rows() -> list[dict[str, str]]:
    return build_catalog_rows(FOODS, iter(FOOD_NUTRIENTS), NUTRIENT_UNITS, CATEGORIES)


def test_keeps_only_sr_legacy_and_foundation_sorted_by_fdc_id() -> None:
    rows = _rows()
    assert [r["fdc_id"] for r in rows] == ["1", "2"]
    assert [r["data_type"] for r in rows] == ["SR Legacy", "Foundation"]
    assert list(rows[0]) == COLUMNS


def test_nutrients_precedence_units_and_missing_as_empty() -> None:
    cabbage, salt = _rows()
    assert cabbage["category"] == "Vegetables and Vegetable Products"
    assert cabbage["protein"] == "1.28"
    assert cabbage["sugars_total"] == "3.2"
    assert float(cabbage["sodium"]) == 0.018
    assert cabbage["lactose"] == ""  # unreported: unknown, never "0"
    assert float(salt["sodium"]) == 38.758
    assert salt["protein"] == ""


def test_write_load_roundtrip_is_byte_reproducible(tmp_path: Path) -> None:
    a, b = tmp_path / "a.csv.gz", tmp_path / "b.csv.gz"
    write_catalog(_rows(), a)
    write_catalog(_rows(), b)
    assert a.read_bytes() == b.read_bytes()  # gzip mtime=0
    assert load_catalog(a) == _rows()


def test_catalog_seed_rows_long_format_skips_missing() -> None:
    foods, nutrients = catalog_seed_rows(_rows())
    assert foods[0] == {
        "fdc_id": 1, "data_type": "SR Legacy",
        "description": "Cabbage, raw", "category": "Vegetables and Vegetable Products",
    }
    by_food = {(n["fdc_id"], n["nutrient"]): n["amount_per_100g"] for n in nutrients}
    assert by_food[(1, "protein")] == 1.28
    assert (1, "lactose") not in by_food
    assert (2, "protein") not in by_food


def test_negative_carbohydrate_clamped_other_negatives_raise() -> None:
    food = [
        {"fdc_id": "5", "data_type": "sr_legacy_food", "description": "X", "food_category_id": ""}
    ]
    units = [{"id": "1005", "unit_name": "G"}, {"id": "1093", "unit_name": "MG"}]

    carb = [{"fdc_id": "5", "nutrient_id": "1005", "amount": "-0.2"}]
    rows = build_catalog_rows(food, iter(carb), units, [])
    assert rows[0]["carbohydrate"] == "0.0"

    sodium = [{"fdc_id": "5", "nutrient_id": "1093", "amount": "-5"}]
    with pytest.raises(ValueError):
        build_catalog_rows(food, iter(sodium), units, [])
