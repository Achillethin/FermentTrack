"""Closed nutrient registry and the frozen USDA FoodData Central snapshot.

Design: docs/superpowers/specs/2026-09-23-ingredient-nutrients-design.md § 2.
Every amount is grams per 100 g. A nutrient FDC didn't report for a food has
no row — unknown, never zero.
"""

from __future__ import annotations

import csv
import uuid
from pathlib import Path
from typing import Any, NamedTuple

# nutrient code -> FDC nutrient ids; when several are listed, the first one the
# food reports wins (SR Legacy reports total sugars under 2000, Foundation under 1063).
# Same FDC ids as fermentation/ingest/usda_fdc.py so the two repos' data joins.
NUTRIENTS: dict[str, tuple[int, ...]] = {
    "water": (1051,),
    "protein": (1003,),
    "fat": (1004,),
    "carbohydrate": (1005,),
    "fiber": (1079,),
    "sugars_total": (2000, 1063),
    "sucrose": (1010,),
    "glucose": (1011,),
    "fructose": (1012,),
    "lactose": (1013,),
    "maltose": (1014,),
    "galactose": (1075,),
    "starch": (1009,),
    "alcohol": (1018,),
    "sodium": (1093,),
}

FDC_SNAPSHOT_V1 = Path(__file__).resolve().parent / "fdc_nutrients_v1.csv"

_GRAMS_PER_FDC_UNIT = {"g": 1.0, "mg": 1e-3, "ug": 1e-6, "µg": 1e-6}


class SnapshotRow(NamedTuple):
    ingredient_name: str
    fdc_id: str
    nutrient: str
    amount_per_100g: float


def fdc_amount_to_grams(amount: float, unit_name: str) -> float:
    factor = _GRAMS_PER_FDC_UNIT.get(unit_name.lower())
    if factor is None:
        raise ValueError(f"not a mass unit: {unit_name!r}")
    return amount * factor


def snapshot_rows(
    ingredient_name: str, description: str, foods: list[dict[str, Any]]
) -> list[SnapshotRow]:
    """Rows for the one FDC search hit whose description matches exactly."""
    matches = [f for f in foods if f["description"] == description]
    if len(matches) != 1:
        nearest = ", ".join(repr(f["description"]) for f in foods[:10])
        raise ValueError(
            f"{ingredient_name!r}: {len(matches)} exact matches for {description!r}. "
            f"Nearest: {nearest}"
        )
    food = matches[0]
    reported = {
        fn["nutrientId"]: fn for fn in food.get("foodNutrients", []) if fn.get("value") is not None
    }
    rows = []
    for code, ids in NUTRIENTS.items():
        fid = next((i for i in ids if i in reported), None)
        if fid is None:
            continue  # unreported = unknown, never written as 0
        fn = reported[fid]
        grams = round(fdc_amount_to_grams(fn["value"], fn["unitName"]), 6)
        rows.append(SnapshotRow(ingredient_name, str(food["fdcId"]), code, grams))
    return rows


def load_snapshot(path: Path = FDC_SNAPSHOT_V1) -> list[SnapshotRow]:
    with path.open(encoding="utf-8", newline="") as f:
        return [
            SnapshotRow(
                r["ingredient_name"], r["fdc_id"], r["nutrient"], float(r["amount_per_100g"])
            )
            for r in csv.DictReader(f)
        ]


def nutrient_seed_rows(
    snapshot: list[SnapshotRow], ids_by_name: dict[str, uuid.UUID]
) -> list[dict[str, Any]]:
    """Insert-ready ingredient_nutrients rows. Raises on seed/snapshot name drift."""
    missing = {r.ingredient_name for r in snapshot} - ids_by_name.keys()
    if missing:
        raise ValueError(f"snapshot names not in ingredients table: {sorted(missing)}")
    return [
        {
            "id": uuid.uuid4(),
            "ingredient_id": ids_by_name[r.ingredient_name],
            "nutrient": r.nutrient,
            "amount_per_100g": r.amount_per_100g,
            "source": "usda_fdc",
            "source_food_id": r.fdc_id,
            "source_version": "fdc_nutrients_v1",
        }
        for r in snapshot
    ]
