# USDA Food Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user search the full USDA SR Legacy + Foundation catalog (~8k foods) and log any of them in a recipe. The first pick creates a nutrient-carrying `Ingredient`, and each pick tags that ingredient for the batch's ferment type.

**Architecture:**
- An offline script turns FDC's bulk CSVs into a frozen, gzipped, wide catalog snapshot.
- Migration 0007 loads it into `fdc_foods` / `fdc_food_nutrients` and adds `ingredients.fdc_id`, backfilled for the curated ingredients.
- `GET /foods?q=` searches the catalog.
- `POST /batches/{id}/ingredients` accepts `fdc_id` and promotes the food to an `Ingredient`, so composition, salt suggestion and preview stay unchanged.
- The frontend gets a search box and a role select.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Alembic, Pydantic v2, pytest + aiosqlite, React/Vite/Tailwind. No new dependencies; the snapshot builder uses only stdlib (`csv`, `gzip`, `zipfile`).

**Spec:** `docs/superpowers/specs/2026-09-23-usda-food-catalog-design.md`

## Global Constraints

- No new runtime, dev or npm dependencies.
- Every stored nutrient amount is **grams per 100 g**. **Missing ≠ zero**: an unreported nutrient is an empty cell in the snapshot and has no row in the DB, never 0.
- `fdc_catalog_v1.csv.gz` is **frozen** once committed. It is written with gzip `mtime=0` so the bytes are reproducible. Never edit `fdc_nutrients_v1.csv`.
- Catalog `data_type` values are exactly `"SR Legacy"` and `"Foundation"`. Only FDC `data_type` in `{"sr_legacy_food", "foundation_food"}` is kept.
- Nutrient codes and precedence come from `fermenttrack.nutrients.NUTRIENTS`. Convert units with `fermenttrack.nutrients.fdc_amount_to_grams`. Reuse both; don't duplicate them.
- **The `fdc_id` path: tag, don't gate.**
  - Picking by `fdc_id` finds or creates the `Ingredient` and adds `culture.type` to its `fermentation_systems`, reassigning the list rather than mutating it in place.
  - The `ingredient_id` path keeps its strict ferment-type check.
  - Retired ingredients return 400 on both paths.
- A new ingredient from the catalog gets `name = description`, `default_role = role or "base"`, and nutrients copied with `source="usda_fdc"`, `source_food_id=str(fdc_id)`, `source_version="fdc_catalog_v1"`.
- The only outbound call is the one-time download of FDC's public bulk zips from fdc.nal.usda.gov (already approved; no key). On this machine curl needs `--ssl-no-revoke` (corporate TLS revocation block).
- Never push or deploy. Commit locally on branch `feat/usda-food-catalog`. Merging and deploying are Achille's call.
- No **new** ruff/mypy errors vs the pre-task baseline. The repo already has some; the B008 on `Depends(...)` in route signatures is the accepted repo convention.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

---

### Task 1: Catalog builder + frozen snapshot

**Files:**
- Create: `src/fermenttrack/fdc_catalog.py`
- Create: `scripts/build_fdc_catalog.py`
- Create (generated): `src/fermenttrack/fdc_catalog_v1.csv.gz`
- Test: `tests/test_fdc_catalog.py` (pure), `tests/test_fdc_catalog_snapshot.py` (real snapshot)

**Interfaces:**
- Consumes: `NUTRIENTS`, `fdc_amount_to_grams`, `load_snapshot` from `fermenttrack.nutrients`
- Produces:
  - `FDC_CATALOG_V1: Path`
  - `DATA_TYPES: dict[str, str]`
  - `COLUMNS: list[str]`
  - `build_catalog_rows(foods, food_nutrients, nutrients, categories) -> list[dict[str, str]]`
  - `write_catalog(rows, path=FDC_CATALOG_V1) -> None`
  - `load_catalog(path=FDC_CATALOG_V1) -> list[dict[str, str]]`
  - `catalog_seed_rows(rows) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]`, returning `(foods, nutrients)` insert-ready rows

- [ ] **Step 1: Write the failing pure tests**

`tests/test_fdc_catalog.py`:

```python
"""Pure checks on the FDC bulk-CSV → wide catalog conversion. No network, no DB."""

from __future__ import annotations

from pathlib import Path

from fermenttrack.fdc_catalog import (
    COLUMNS,
    build_catalog_rows,
    catalog_seed_rows,
    load_catalog,
    write_catalog,
)

FOODS = [
    {"fdc_id": "1", "data_type": "sr_legacy_food", "description": "Cabbage, raw", "food_category_id": "11"},
    {"fdc_id": "2", "data_type": "foundation_food", "description": "Salt, table", "food_category_id": "2"},
    {"fdc_id": "3", "data_type": "sub_sample_food", "description": "Cabbage sample", "food_category_id": "11"},
    {"fdc_id": "4", "data_type": "branded_food", "description": "Brand X", "food_category_id": ""},
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_fdc_catalog.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'fermenttrack.fdc_catalog'`

- [ ] **Step 3: Implement `src/fermenttrack/fdc_catalog.py`**

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_fdc_catalog.py -v`
Expected: 4 passed

- [ ] **Step 5: Write `scripts/build_fdc_catalog.py`**

```python
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
```

- [ ] **Step 6: Download the two zips and build the snapshot**

1. Get the current CSV zip URLs from https://fdc.nal.usda.gov/download-datasets. SR Legacy is the April 2018 release. Foundation is the latest dated release; note its date.
2. Download the zips into a scratch dir outside the repo: `curl --ssl-no-revoke -L -o <scratch>/sr.zip <URL>`, and the same for Foundation.
3. Run: `.venv/Scripts/python scripts/build_fdc_catalog.py <scratch>/sr.zip <scratch>/foundation.zip`
4. Expected: `wrote N foods ...` with N between 7,500 and 9,000.
5. If a CSV header differs from what `build_catalog_rows` expects (`fdc_id`, `data_type`, `description`, `food_category_id`, `nutrient_id`, `amount`, `id`, `unit_name`), stop and report the actual headers. Do not guess.

- [ ] **Step 7: Write the sanity tests on the frozen snapshot**

`tests/test_fdc_catalog_snapshot.py`:

```python
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
```

- [ ] **Step 8: Run all of Task 1's tests, plus the full suite**

Run: `.venv/Scripts/python -m pytest tests/test_fdc_catalog.py tests/test_fdc_catalog_snapshot.py -v`, then `.venv/Scripts/python -m pytest -q`
Expected: all pass (baseline 97 + 8 new = 105). If an anchor fails, the build is wrong. Fix the builder, not the test.

- [ ] **Step 9: Commit**

```bash
git add src/fermenttrack/fdc_catalog.py scripts/build_fdc_catalog.py src/fermenttrack/fdc_catalog_v1.csv.gz tests/test_fdc_catalog.py tests/test_fdc_catalog_snapshot.py
git commit -m "feat: add frozen USDA FDC catalog snapshot (SR Legacy + Foundation <date>)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Replace `<date>` with the Foundation release date you used.

---

### Task 2: Catalog tables, `Ingredient.fdc_id`, migration 0007

**Files:**
- Modify: `src/fermenttrack/models.py` (imports; `Ingredient.fdc_id`; new `FdcFood`, `FdcFoodNutrient`)
- Create: `alembic/versions/0007_fdc_catalog.py`
- Test: `tests/test_ingredients_model.py` (append; merge imports into its header)

**Interfaces:**
- Consumes: `FDC_CATALOG_V1`, `load_catalog`, `catalog_seed_rows` (Task 1)
- Produces:
  - `FdcFood(fdc_id: int PK, data_type: str, description: str, category: str | None, nutrients: list[FdcFoodNutrient])`
  - `FdcFoodNutrient(fdc_id: int, nutrient: str, amount_per_100g: float)`, with PK `(fdc_id, nutrient)`
  - `Ingredient.fdc_id: int | None`, backed by the unique index `ix_ingredients_fdc_id`

- [ ] **Step 1: Write the failing model test** (append to `tests/test_ingredients_model.py`; the new imports are `FdcFood`, `FdcFoodNutrient`)

```python
@pytest.mark.asyncio
async def test_fdc_food_roundtrip_and_ingredient_fdc_id_unique(db_session: AsyncSession) -> None:
    db_session.add(
        FdcFood(
            fdc_id=169975, data_type="SR Legacy", description="Cabbage, raw",
            category="Vegetables and Vegetable Products",
            nutrients=[FdcFoodNutrient(nutrient="water", amount_per_100g=92.18)],
        )
    )
    db_session.add(
        Ingredient(name="Cabbage", default_role="base", fermentation_systems=["lacto_ferment"], fdc_id=169975)
    )
    await db_session.commit()

    food = (
        await db_session.execute(
            select(FdcFood).where(FdcFood.fdc_id == 169975).options(selectinload(FdcFood.nutrients))
        )
    ).scalar_one()
    assert {n.nutrient: n.amount_per_100g for n in food.nutrients} == {"water": 92.18}

    db_session.add(Ingredient(name="Cabbage 2", default_role="base", fermentation_systems=[], fdc_id=169975))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_ingredients_model.py -v -k fdc_food`
Expected: FAIL with `ImportError: cannot import name 'FdcFood'`

- [ ] **Step 3: Implement the models in `src/fermenttrack/models.py`**

Add `Integer` to the `sqlalchemy` import. In `class Ingredient`, add this after `is_active`:

```python
    fdc_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True, index=True)
```

`unique=True, index=True` gives a unique index named `ix_ingredients_fdc_id`, the same name migration 0007 creates.

Append at the end of the file:

```python
class FdcFood(Base):
    """USDA FDC catalog food (SR Legacy / Foundation), loaded from fdc_catalog_v1.csv.gz."""

    __tablename__ = "fdc_foods"

    fdc_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    data_type: Mapped[str] = mapped_column(Text, nullable=False)  # "SR Legacy" | "Foundation"
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    nutrients: Mapped[list[FdcFoodNutrient]] = relationship()


class FdcFoodNutrient(Base):
    """Catalog nutrient per 100 g (grams). No row = not reported = unknown, never 0."""

    __tablename__ = "fdc_food_nutrients"

    fdc_id: Mapped[int] = mapped_column(Integer, ForeignKey("fdc_foods.fdc_id"), primary_key=True)
    nutrient: Mapped[str] = mapped_column(Text, primary_key=True)  # key of nutrients.NUTRIENTS
    amount_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
```

- [ ] **Step 4: Run the model test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_ingredients_model.py -v`
Expected: all pass

- [ ] **Step 5: Write `alembic/versions/0007_fdc_catalog.py`**

```python
"""fdc_foods / fdc_food_nutrients catalog + ingredients.fdc_id (backfilled for curated rows)

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-23

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from fermenttrack.fdc_catalog import FDC_CATALOG_V1, catalog_seed_rows, load_catalog

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CHUNK = 5000


def upgrade() -> None:
    foods_t = op.create_table(
        "fdc_foods",
        sa.Column("fdc_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("data_type", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=True),
    )
    nutrients_t = op.create_table(
        "fdc_food_nutrients",
        sa.Column("fdc_id", sa.Integer(), sa.ForeignKey("fdc_foods.fdc_id"), primary_key=True),
        sa.Column("nutrient", sa.Text(), primary_key=True),
        sa.Column("amount_per_100g", sa.Float(), nullable=False),
    )
    op.add_column("ingredients", sa.Column("fdc_id", sa.Integer(), nullable=True))
    op.create_index("ix_ingredients_fdc_id", "ingredients", ["fdc_id"], unique=True)

    # FDC_CATALOG_V1 is frozen, so this migration stays a faithful record of what it inserted.
    foods, nutrients = catalog_seed_rows(load_catalog(FDC_CATALOG_V1))
    for i in range(0, len(foods), _CHUNK):
        op.bulk_insert(foods_t, foods[i : i + _CHUNK])
    for i in range(0, len(nutrients), _CHUNK):
        op.bulk_insert(nutrients_t, nutrients[i : i + _CHUNK])

    # Curated ingredients already carry FDC provenance on their v1 nutrient rows.
    op.execute(
        sa.text(
            "UPDATE ingredients SET fdc_id = ("
            " SELECT CAST(MIN(n.source_food_id) AS INTEGER) FROM ingredient_nutrients n"
            " WHERE n.ingredient_id = ingredients.id AND n.source = 'usda_fdc')"
            " WHERE EXISTS (SELECT 1 FROM ingredient_nutrients n"
            " WHERE n.ingredient_id = ingredients.id AND n.source = 'usda_fdc')"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_ingredients_fdc_id", table_name="ingredients")
    op.drop_column("ingredients", "fdc_id")
    op.drop_table("fdc_food_nutrients")
    op.drop_table("fdc_foods")
```

- [ ] **Step 6: Round-trip the migration chain on SQLite**

1. In a scratch dir outside the repo, set `FERMENTTRACK_DATABASE_URL=sqlite+aiosqlite:///<scratch>/m.db`.
2. Run `.venv/Scripts/python -m alembic upgrade head`, then `downgrade 0006`, then `upgrade head`.
3. After each upgrade, check with `sqlite3`, or a few lines of Python using the stdlib `sqlite3` module:
   - `fdc_foods` row count equals N from Task 1;
   - `fdc_food_nutrients` count is greater than 0;
   - `SELECT count(*) FROM ingredients WHERE fdc_id IS NOT NULL` is **26**;
   - `SELECT fdc_id FROM ingredients WHERE name='Cabbage'` exists in `fdc_foods`.
4. Report the numbers. There's no Postgres available locally (Docker is down); the first Postgres run is the Render deploy, which Achille will trigger.

- [ ] **Step 7: Full suite, then commit**

Run: `.venv/Scripts/python -m pytest -q`
Expected: all pass (106)

```bash
git add src/fermenttrack/models.py alembic/versions/0007_fdc_catalog.py tests/test_ingredients_model.py
git commit -m "feat: add fdc_foods catalog tables and ingredients.fdc_id (migration 0007)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `GET /foods` search

**Files:**
- Create: `src/fermenttrack/routers/foods.py`
- Modify: `src/fermenttrack/schemas.py` (add `FdcFoodOut`), `src/fermenttrack/main.py` (register the router), `docs/ARCHITECTURE.md` (one route line)
- Test: `tests/test_foods_search.py`

**Interfaces:**
- Consumes: `FdcFood` (Task 2)
- Produces:
  - `FdcFoodOut(fdc_id: int, description: str, data_type: str, category: str | None)`
  - `GET /foods?q=&limit=`

- [ ] **Step 1: Write the failing tests**

`tests/test_foods_search.py`:

```python
"""GET /foods — search the USDA catalog."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.models import FdcFood


@pytest.fixture
async def catalog(db_session: AsyncSession) -> None:
    db_session.add_all(
        [
            FdcFood(fdc_id=1, data_type="SR Legacy", description="Cabbage, raw", category="Vegetables"),
            FdcFood(fdc_id=2, data_type="SR Legacy", description="Cabbage, red, raw", category="Vegetables"),
            FdcFood(fdc_id=3, data_type="Foundation", description="Cabbage, savoy, cooked, boiled", category=None),
            FdcFood(fdc_id=4, data_type="SR Legacy", description="Mangos, raw", category="Fruits"),
            FdcFood(fdc_id=5, data_type="SR Legacy", description="Milk, 100% whole", category="Dairy"),
        ]
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_all_tokens_must_match_case_insensitive(client: AsyncClient, catalog: None) -> None:
    body = (await client.get("/foods", params={"q": "RAW cabbage"})).json()
    assert [f["description"] for f in body] == ["Cabbage, raw", "Cabbage, red, raw"]
    assert body[0] == {"fdc_id": 1, "description": "Cabbage, raw", "data_type": "SR Legacy", "category": "Vegetables"}


@pytest.mark.asyncio
async def test_shorter_names_first_and_limit(client: AsyncClient, catalog: None) -> None:
    body = (await client.get("/foods", params={"q": "cabbage", "limit": 2})).json()
    assert [f["fdc_id"] for f in body] == [1, 2]


@pytest.mark.asyncio
async def test_like_wildcards_are_literal(client: AsyncClient, catalog: None) -> None:
    assert [f["fdc_id"] for f in (await client.get("/foods", params={"q": "100%"})).json()] == [5]
    assert (await client.get("/foods", params={"q": "c_bbage"})).json() == []


@pytest.mark.asyncio
async def test_query_validation(client: AsyncClient, catalog: None) -> None:
    assert (await client.get("/foods", params={"q": "c"})).status_code == 422
    assert (await client.get("/foods", params={"q": "cabbage", "limit": 51})).status_code == 422
    assert (await client.get("/foods", params={"q": "   "})).json() == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_foods_search.py -v`
Expected: FAIL (404 on `/foods`)

- [ ] **Step 3: Implement**

`src/fermenttrack/schemas.py`: add this after the Ingredient section:

```python
# ── USDA catalog ─────────────────────────────────────────────────────────

class FdcFoodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fdc_id: int
    description: str
    data_type: str  # "SR Legacy" | "Foundation"
    category: str | None
```

`src/fermenttrack/routers/foods.py`:

```python
"""Search the frozen USDA FDC catalog (docs/superpowers/specs/2026-09-23-usda-food-catalog-design.md)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.database import get_db
from fermenttrack.models import FdcFood
from fermenttrack.schemas import FdcFoodOut

router = APIRouter(prefix="/foods", tags=["foods"])


@router.get("", response_model=list[FdcFoodOut])
async def search_foods(
    q: str = Query(min_length=2, description="Every whitespace-separated word must appear"),
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> list[FdcFood]:
    tokens = q.lower().split()
    if not tokens:
        return []
    stmt = select(FdcFood)
    for token in tokens:
        stmt = stmt.where(func.lower(FdcFood.description).contains(token, autoescape=True))
    stmt = stmt.order_by(func.length(FdcFood.description), FdcFood.description).limit(limit)
    return list((await db.execute(stmt)).scalars().all())
```

`src/fermenttrack/main.py`: add `foods` to the routers import, and `app.include_router(foods.router)` after `ingredients`.

`docs/ARCHITECTURE.md`: add `GET    /foods?q=...                Search the USDA catalog (SR Legacy + Foundation)` to the API listing, next to the ingredients routes, matching that listing's alignment.

- [ ] **Step 4: Run to verify it passes, then run the full suite**

Run: `.venv/Scripts/python -m pytest tests/test_foods_search.py -v`, then `.venv/Scripts/python -m pytest -q`
Expected: 4 passed; the full suite shows 110 passed.

- [ ] **Step 5: Commit**

```bash
git add src/fermenttrack/routers/foods.py src/fermenttrack/schemas.py src/fermenttrack/main.py docs/ARCHITECTURE.md tests/test_foods_search.py
git commit -m "feat: add GET /foods search over the USDA catalog

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Pick a catalog food by `fdc_id`

**Files:**
- Modify: `src/fermenttrack/schemas.py` (`BatchIngredientCreate`), `src/fermenttrack/routers/batches.py` (`add_batch_ingredient` + a new helper)
- Test: `tests/test_batch_fdc_pick.py`

**Interfaces:**
- Consumes: `FdcFood`, `FdcFoodNutrient`, `Ingredient.fdc_id` (Task 2); `IngredientNutrient`
- Produces: `POST /batches/{id}/ingredients` accepting exactly one of `ingredient_id: UUID` or `fdc_id: int`

- [ ] **Step 1: Write the failing tests**

`tests/test_batch_fdc_pick.py`:

```python
"""POST /batches/{id}/ingredients with fdc_id — promote a USDA catalog food to an Ingredient."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.models import FdcFood, FdcFoodNutrient, Ingredient

MANGO = 9001


async def _batch(client: AsyncClient, ferment: str) -> str:
    culture = (await client.post("/cultures", json={"name": f"{ferment} c", "type": ferment})).json()
    return (await client.post("/batches", json={"culture_id": culture["id"]})).json()["id"]


@pytest.fixture
async def mango(db_session: AsyncSession) -> None:
    db_session.add(
        FdcFood(
            fdc_id=MANGO, data_type="SR Legacy", description="Mangos, raw", category="Fruits",
            nutrients=[
                FdcFoodNutrient(nutrient="sugars_total", amount_per_100g=13.66),
                FdcFoodNutrient(nutrient="water", amount_per_100g=83.46),
            ],
        )
    )
    await db_session.commit()


async def _mango_ingredients(db: AsyncSession) -> list[Ingredient]:
    db.expire_all()
    return list((await db.execute(select(Ingredient).where(Ingredient.fdc_id == MANGO))).scalars())


@pytest.mark.asyncio
async def test_first_pick_creates_tagged_ingredient_with_nutrients(
    client: AsyncClient, db_session: AsyncSession, mango: None
) -> None:
    batch_id = await _batch(client, "kombucha")
    resp = await client.post(
        f"/batches/{batch_id}/ingredients",
        json={"fdc_id": MANGO, "quantity": 200, "unit": "g", "role": "flavoring"},
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "flavoring"

    [ing] = await _mango_ingredients(db_session)
    assert (ing.name, ing.default_role, ing.fermentation_systems) == ("Mangos, raw", "flavoring", ["kombucha"])

    quick_picks = (await client.get("/ingredients", params={"substrate": "kombucha"})).json()
    assert "Mangos, raw" in {i["name"] for i in quick_picks}

    comp = (await client.get(f"/batches/{batch_id}/composition")).json()
    sugars = next(n for n in comp["nutrients"] if n["nutrient"] == "sugars_total")
    assert sugars["grams"] == pytest.approx(27.32)


@pytest.mark.asyncio
async def test_second_pick_reuses_and_tags_new_ferment(
    client: AsyncClient, db_session: AsyncSession, mango: None
) -> None:
    await client.post(f"/batches/{await _batch(client, 'kombucha')}/ingredients", json={"fdc_id": MANGO})
    resp = await client.post(f"/batches/{await _batch(client, 'kefir')}/ingredients", json={"fdc_id": MANGO})
    assert resp.status_code == 201
    assert resp.json()["role"] == "base"  # default when no role given

    [ing] = await _mango_ingredients(db_session)
    assert ing.fermentation_systems == ["kombucha", "kefir"]


@pytest.mark.asyncio
async def test_pick_reuses_backfilled_curated_ingredient(client: AsyncClient, db_session: AsyncSession) -> None:
    cabbage = Ingredient(name="Cabbage", default_role="base", fermentation_systems=["lacto_ferment"], fdc_id=169975)
    db_session.add_all([cabbage, FdcFood(fdc_id=169975, data_type="SR Legacy", description="Cabbage, raw")])
    await db_session.commit()

    batch_id = await _batch(client, "lacto_ferment")
    resp = await client.post(f"/batches/{batch_id}/ingredients", json={"fdc_id": 169975, "quantity": 1, "unit": "kg"})
    assert resp.status_code == 201
    assert resp.json()["ingredient_id"] == str(cabbage.id)


@pytest.mark.asyncio
async def test_unknown_fdc_id_404_and_id_validation(client: AsyncClient, mango: None) -> None:
    batch_id = await _batch(client, "kombucha")
    url = f"/batches/{batch_id}/ingredients"
    assert (await client.post(url, json={"fdc_id": 424242})).status_code == 404
    assert (await client.post(url, json={})).status_code == 422
    both = {"fdc_id": MANGO, "ingredient_id": "00000000-0000-0000-0000-000000000000"}
    assert (await client.post(url, json=both)).status_code == 422
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_batch_fdc_pick.py -v`
Expected: FAIL (422 for `{"fdc_id": ...}`, because `ingredient_id` is required)

- [ ] **Step 3: Update `BatchIngredientCreate` in `src/fermenttrack/schemas.py`**

Add `model_validator` to the pydantic import, then replace the class with:

```python
class BatchIngredientCreate(BaseModel):
    """Exactly one of ingredient_id (curated, strict ferment check) or fdc_id (USDA catalog)."""

    ingredient_id: uuid.UUID | None = None
    fdc_id: int | None = None
    quantity: float | None = None
    unit: Unit | None = None
    role: str | None = None  # if omitted, copied from Ingredient.default_role

    @model_validator(mode="after")
    def _exactly_one_source(self) -> BatchIngredientCreate:
        if (self.ingredient_id is None) == (self.fdc_id is None):
            raise ValueError("give exactly one of ingredient_id or fdc_id")
        return self
```

- [ ] **Step 4: Update `routers/batches.py`**

Add `FdcFood` and `IngredientNutrient` to the `fermenttrack.models` import. Add this helper directly above `add_batch_ingredient`:

```python
async def _ingredient_for_fdc_food(
    db: AsyncSession, fdc_id: int, ferment_type: str, role: str | None
) -> Ingredient:
    """Find-or-create the Ingredient for a USDA catalog food and tag it for this ferment.

    Spec: docs/superpowers/specs/2026-09-23-usda-food-catalog-design.md § Pick.
    ponytail: check-then-create isn't race-safe (unique index -> 500 on a simultaneous
    first pick); fine single-user, catch IntegrityError + re-select if that changes.
    """
    food = await db.get(FdcFood, fdc_id, options=[selectinload(FdcFood.nutrients)])
    if food is None:
        raise HTTPException(status_code=404, detail="USDA food not found")
    result = await db.execute(select(Ingredient).where(Ingredient.fdc_id == fdc_id))
    ingredient = result.scalar_one_or_none()
    if ingredient is None:
        ingredient = Ingredient(
            name=food.description,
            default_role=role or "base",
            fermentation_systems=[ferment_type],
            fdc_id=fdc_id,
            nutrients=[
                IngredientNutrient(
                    nutrient=n.nutrient,
                    amount_per_100g=n.amount_per_100g,
                    source="usda_fdc",
                    source_food_id=str(fdc_id),
                    source_version="fdc_catalog_v1",
                )
                for n in food.nutrients
            ],
        )
        db.add(ingredient)
        await db.flush()
    elif ingredient.is_active and ferment_type not in ingredient.fermentation_systems:
        # Reassign: the JSON column doesn't track in-place mutation.
        ingredient.fermentation_systems = [*ingredient.fermentation_systems, ferment_type]
    return ingredient
```

In `add_batch_ingredient`, replace these lines:

```python
    ingredient = await db.get(Ingredient, payload.ingredient_id)
    if ingredient is None:
        raise HTTPException(status_code=404, detail="Ingredient not found")
```

with:

```python
    if payload.fdc_id is not None:
        ingredient = await _ingredient_for_fdc_food(
            db, payload.fdc_id, batch.culture.type, payload.role
        )
    else:
        found = await db.get(Ingredient, payload.ingredient_id)
        if found is None:
            raise HTTPException(status_code=404, detail="Ingredient not found")
        ingredient = found
```

Leave the rest of the function unchanged: the retired check, the ferment-type check (which a tagged catalog ingredient passes) and the insert.

- [ ] **Step 5: Run to verify it passes, then run the full suite**

Run: `.venv/Scripts/python -m pytest tests/test_batch_fdc_pick.py tests/test_batch_ingredients.py -v`, then `.venv/Scripts/python -m pytest -q`
Expected: all pass (114). The existing strict-check tests in `test_batch_ingredients.py` stay green.

- [ ] **Step 6: Commit**

```bash
git add src/fermenttrack/schemas.py src/fermenttrack/routers/batches.py tests/test_batch_fdc_pick.py
git commit -m "feat: log any USDA catalog food by fdc_id, promoting it to a tagged ingredient

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Frontend: USDA search box + role select

**Files:**
- Modify: `frontend/src/App.jsx` (the `Recipe` component only)

**Interfaces:**
- Consumes: `GET /foods?q=` (Task 3) → `[{fdc_id, description, data_type, category}]`, and `POST /batches/{id}/ingredients` with `{fdc_id, role, quantity, unit}` (Task 4)

- [ ] **Step 1: Add state and the debounced search** (in `Recipe`, after the existing `useState` lines)

```jsx
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [food, setFood] = useState(null);
  const [role, setRole] = useState("base");

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      setResults([]);
      return;
    }
    const t = setTimeout(() => {
      fetch(`${API_URL}/foods?q=${encodeURIComponent(q)}`)
        .then((r) => (r.ok ? r.json() : []))
        .then(setResults)
        .catch(() => {});
    }, 250);
    return () => clearTimeout(t);
  }, [query]);
```

Change the options `useEffect` dependency array from `[substrate]` to `[substrate, recipe.length]`. That way a food created on the first pick joins the quick picks, and its name resolves in the recipe list.

- [ ] **Step 2: Submit either source**

In `submit`:
- Replace `if (!ingredientId) return;` with `if (!ingredientId && !food) return;`.
- Replace `ingredient_id: ingredientId,` in the JSON body with `...(food ? { fdc_id: food.fdc_id, role } : { ingredient_id: ingredientId }),`.
- After `setUnit("");` on success, add `setFood(null); setQuery(""); setResults([]); setRole("base");`.

In the quick-pick `<select>`'s `onChange`, add `setFood(null);` right after `setIngredientId(id);`. Change the Add button's `disabled={busy || !ingredientId}` to `disabled={busy || (!ingredientId && !food)}`.

- [ ] **Step 3: Render the search row** as the **first child** of the `<form className="flex flex-wrap gap-2" ...>`, so it spans its own row above the quick-pick, quantity, unit and Add controls:

```jsx
        <div className="w-full">
          {food ? (
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="text-slate-200">USDA: {food.description}</span>
              <select
                className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-1 text-sm"
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                {["base", "flavoring", "additive", "starter"].map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="text-xs text-slate-400 hover:text-slate-200"
                onClick={() => setFood(null)}
              >
                clear
              </button>
            </div>
          ) : (
            <>
              <input
                className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                placeholder="Search all USDA foods…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              {results.length > 0 && (
                <ul className="mt-1 max-h-60 divide-y divide-slate-800 overflow-y-auto rounded-lg border border-slate-800">
                  {results.map((f) => (
                    <li key={f.fdc_id}>
                      <button
                        type="button"
                        className="flex w-full justify-between px-3 py-2 text-left text-sm hover:bg-slate-800"
                        onClick={() => {
                          setFood(f);
                          setIngredientId("");
                          setResults([]);
                        }}
                      >
                        <span>{f.description}</span>
                        <span className="ml-2 shrink-0 text-xs text-slate-500">{f.data_type}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
```

- [ ] **Step 4: Build and check in the running app**

Run: `cd frontend && npm run build`. Expected: success, with no warnings added.

Then run the app locally against a scratch SQLite DB built by the **real migrations**:
1. `FERMENTTRACK_DATABASE_URL=sqlite+aiosqlite:///<scratch>/app.db .venv/Scripts/python -m alembic upgrade head`
2. Start `uvicorn fermenttrack.main:app --port 8010` with the same env var, in the background.
3. Start `npm run dev` with `VITE_API_URL=http://127.0.0.1:8010`, in the background.

Drive the app with the Playwright MCP tools if available, otherwise say plainly that the UI wasn't clicked. Check and report what you observed:
1. On a kombucha batch, typing "mango" lists "Mangos, raw" (SR Legacy).
2. Picking it shows "USDA: Mangos, raw" plus a role select. Set flavoring, 200 g, then Add. The recipe line reads "Mangos, raw 200 g flavoring", and the composition card shows sugars about 27 g.
3. The quick-pick dropdown for kombucha now lists "Mangos, raw".
4. On a lacto_ferment batch, searching "cabbage raw" and picking "Cabbage, raw" logs it under the name **Cabbage** (the curated one is reused).
5. The salt pre-fill still works when Salt is picked from the quick picks.

**Stop both servers afterwards.** Nothing from the scratch run goes into the repo.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat: search and log any USDA food from the recipe form

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Not in this plan (by design; see spec)

- Branded foods, CIQUAL / French names, fuzzy search, custom non-USDA foods, and ingredient editing or merging.
- Pushing and deploying: after the final review, Achille decides. The Postgres check of migration 0007 then happens through the deployed API.
