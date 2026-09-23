"""Fetch the frozen FDC nutrient snapshot for INGREDIENT_FDC_MAP.

    python scripts/fetch_fdc_snapshot.py [--api-key KEY] [--force]

Writes src/fermenttrack/fdc_nutrients_v1.csv. FROZEN once migration 0006 has
run anywhere — a new snapshot is fdc_nutrients_v2.csv + a new migration.
Only public FDC food descriptions leave the machine; no batch or user data.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.parse
import urllib.request
from typing import Any

from fermenttrack.nutrients import FDC_SNAPSHOT_V1, SnapshotRow, snapshot_rows
from fermenttrack.seed_data import INGREDIENT_FDC_MAP

_SEARCH = "https://api.nal.usda.gov/fdc/v1/foods/search"


def _search(description: str, api_key: str) -> list[dict[str, Any]]:
    # safe="()" : FDC's search endpoint 400s on a percent-encoded '(' or ')'
    # (e.g. in "... (Includes foods for USDA's Food Distribution Program)");
    # leaving them literal in the query string avoids that.
    qs = urllib.parse.urlencode(
        {"query": description, "dataType": "SR Legacy", "pageSize": 200, "api_key": api_key},
        safe="()",
    )
    with urllib.request.urlopen(f"{_SEARCH}?{qs}", timeout=30) as resp:
        foods: list[dict[str, Any]] = json.load(resp)["foods"]
    return foods


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", default=os.environ.get("FDC_API_KEY"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if FDC_SNAPSHOT_V1.exists() and not args.force:
        sys.exit(
            "fdc_nutrients_v1.csv is frozen; a new snapshot is _v2 + a new migration "
            "(use --force only to regenerate v1 before it has ever been migrated)"
        )
    if not args.api_key:
        sys.exit("no API key: pass --api-key or set the FDC_API_KEY env var")

    rows: list[SnapshotRow] = []
    for name, description in INGREDIENT_FDC_MAP.items():
        rows += snapshot_rows(name, description, _search(description, args.api_key))

    with FDC_SNAPSHOT_V1.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(SnapshotRow._fields)
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows for {len(INGREDIENT_FDC_MAP)} ingredients to {FDC_SNAPSHOT_V1}")


if __name__ == "__main__":
    main()
