"""Frozen USDA FoodData Central catalog: SR Legacy + Foundation generic foods.

Design: docs/superpowers/specs/2026-09-23-usda-food-catalog-design.md § Data.
Wide format, one row per food; nutrient cells are g per 100 g and an empty
cell means FDC didn't report it — unknown, never zero.
"""

from __future__ import annotations

import csv
import gzip
import io
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from fermenttrack.nutrients import NUTRIENTS, fdc_amount_to_grams

FDC_CATALOG_V1 = Path(__file__).resolve().parent / "fdc_catalog_v1.csv.gz"

# FDC bulk-CSV data_type -> label stored in the catalog
DATA_TYPES = {"sr_legacy_food": "SR Legacy", "foundation_food": "Foundation"}

COLUMNS = ["fdc_id", "data_type", "description", "category", *NUTRIENTS]

# FDC nutrient id 1005: carbohydrate "by difference" (100 - protein - fat -
# water - ash). Derived, not measured, so summing measurement error in the
# other four can push it slightly negative for near-zero-carb foods.
_CARBOHYDRATE_BY_DIFFERENCE_ID = "1005"


def build_catalog_rows(
    foods: Iterable[dict[str, str]],
    food_nutrients: Iterable[dict[str, str]],
    nutrients: Iterable[dict[str, str]],
    categories: Iterable[dict[str, str]],
) -> list[dict[str, str]]:
    """FDC bulk-CSV rows (food, food_nutrient, nutrient, food_category) -> wide catalog rows.

    food_nutrients is consumed once, streaming — SR Legacy's file is ~650k rows.
    """
    units = {r["id"]: r["unit_name"] for r in nutrients}
    category = {r["id"]: r["description"] for r in categories}
    kept = {r["fdc_id"]: r for r in foods if r["data_type"] in DATA_TYPES}
    wanted = {str(fid) for ids in NUTRIENTS.values() for fid in ids}

    reported: dict[str, dict[int, float]] = {}
    for r in food_nutrients:
        if r["fdc_id"] in kept and r["nutrient_id"] in wanted and r["amount"] != "":
            grams = fdc_amount_to_grams(float(r["amount"]), units[r["nutrient_id"]])
            if grams < 0:
                if r["nutrient_id"] != _CARBOHYDRATE_BY_DIFFERENCE_ID:
                    raise ValueError(
                        f"negative amount for fdc_id={r['fdc_id']} "
                        f"nutrient_id={r['nutrient_id']}: {grams}"
                    )
                # A handful of Foundation raw-meat foods report a tiny negative
                # carbohydrate-by-difference (rounding artifact from summing
                # protein/fat/water/ash slightly over 100%). g/100g can't be
                # negative, so clamp this one derived nutrient to 0 rather
                # than propagate noise; any other negative is a real bug.
                grams = 0.0
            reported.setdefault(r["fdc_id"], {})[int(r["nutrient_id"])] = grams

    rows = []
    for fdc_id, food in sorted(kept.items(), key=lambda kv: int(kv[0])):
        got = reported.get(fdc_id, {})
        row = {
            "fdc_id": fdc_id,
            "data_type": DATA_TYPES[food["data_type"]],
            "description": food["description"],
            "category": category.get(food.get("food_category_id") or "", ""),
        }
        for code, ids in NUTRIENTS.items():
            fid = next((i for i in ids if i in got), None)
            row[code] = "" if fid is None else str(round(got[fid], 6))
        rows.append(row)
    return rows


def write_catalog(rows: list[dict[str, str]], path: Path = FDC_CATALOG_V1) -> None:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    with path.open("wb") as f, gzip.GzipFile(filename="", mode="wb", fileobj=f, mtime=0) as gz:
        gz.write(buf.getvalue().encode("utf-8"))


def load_catalog(path: Path = FDC_CATALOG_V1) -> list[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def catalog_seed_rows(
    rows: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Insert-ready (fdc_foods, fdc_food_nutrients) rows. Empty cells produce no row."""
    foods = [
        {
            "fdc_id": int(r["fdc_id"]),
            "data_type": r["data_type"],
            "description": r["description"],
            "category": r["category"] or None,
        }
        for r in rows
    ]
    nutrients = [
        {"fdc_id": int(r["fdc_id"]), "nutrient": code, "amount_per_100g": float(r[code])}
        for r in rows
        for code in NUTRIENTS
        if r[code] != ""
    ]
    return foods, nutrients
