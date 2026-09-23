"""Build the frozen FDC catalog snapshot from FDC's bulk CSV zips.

    python scripts/build_fdc_catalog.py SR_LEGACY_ZIP FOUNDATION_ZIP [--force]

Download both "CSV" zips from https://fdc.nal.usda.gov/download-datasets
first (public, no key). Writes src/fermenttrack/fdc_catalog_v1.csv.gz —
FROZEN once migration 0007 has run anywhere: a new catalog is _v2 + a new
migration.
"""

from __future__ import annotations

import argparse
import csv
import io
import zipfile
from collections.abc import Iterator
from pathlib import Path

from fermenttrack.fdc_catalog import FDC_CATALOG_V1, build_catalog_rows, write_catalog


def _member(zf: zipfile.ZipFile, name: str) -> str:
    return next(m for m in zf.namelist() if m == name or m.endswith("/" + name))


def _rows(zf: zipfile.ZipFile, name: str) -> Iterator[dict[str, str]]:
    with zf.open(_member(zf, name)) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig", newline=""))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("zips", nargs=2, type=Path, help="SR Legacy zip, Foundation zip")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if FDC_CATALOG_V1.exists() and not args.force:
        raise SystemExit(
            "fdc_catalog_v1.csv.gz is frozen; a new catalog is _v2 + a new migration "
            "(use --force only to regenerate v1 before it has ever been migrated)"
        )

    rows: list[dict[str, str]] = []
    for path in args.zips:
        with zipfile.ZipFile(path) as zf:
            rows += build_catalog_rows(
                list(_rows(zf, "food.csv")),
                _rows(zf, "food_nutrient.csv"),
                list(_rows(zf, "nutrient.csv")),
                list(_rows(zf, "food_category.csv")),
            )
    rows.sort(key=lambda r: int(r["fdc_id"]))
    write_catalog(rows)
    print(f"wrote {len(rows)} foods to {FDC_CATALOG_V1}")


if __name__ == "__main__":
    main()
