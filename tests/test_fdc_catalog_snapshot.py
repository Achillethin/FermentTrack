"""Sanity checks on the committed, frozen FDC catalog snapshot."""

from __future__ import annotations

from collections import Counter

from fermenttrack.fdc_catalog import COLUMNS, load_catalog
from fermenttrack.nutrients import NUTRIENTS, load_snapshot

ROWS = load_catalog()
BY_DESC = {(r["description"], r["data_type"]): r for r in ROWS}


def test_sizes_and_columns() -> None:
    counts = Counter(r["data_type"] for r in ROWS)
    assert counts["SR Legacy"] > 7000
    assert counts["Foundation"] > 150
    assert set(counts) == {"SR Legacy", "Foundation"}
    assert list(ROWS[0]) == COLUMNS
    assert len({r["fdc_id"] for r in ROWS}) == len(ROWS)


def test_amounts_are_plausible_grams_per_100g() -> None:
    for r in ROWS:
        for code in NUTRIENTS:
            if r[code] != "":
                assert 0.0 <= float(r[code]) <= 100.0, (r["fdc_id"], code, r[code])


def test_anchor_foods() -> None:
    salt = BY_DESC[("Salt, table", "SR Legacy")]
    assert 38.0 <= float(salt["sodium"]) <= 39.5
    sugar = BY_DESC[("Sugars, granulated", "SR Legacy")]
    assert max(float(sugar["sucrose"] or 0), float(sugar["sugars_total"] or 0)) >= 99.0


def test_every_curated_v1_food_is_in_the_catalog() -> None:
    catalog_ids = {r["fdc_id"] for r in ROWS}
    assert {r.fdc_id for r in load_snapshot()} <= catalog_ids
