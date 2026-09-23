# Ingredient Nutrients — Increment 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:**
- Replace the vague seed ingredients with specific ones.
- Attach USDA FoodData Central nutrient values to them.
- Compute a batch's starting nutrient composition (total grams, g/100 g, brine salt %) from its recipe, with honest coverage reporting.
- Pre-fill a per-ferment-type default salt amount.

**Architecture:**
- Migration 0005 retires the generic seed rows (soft-deactivation) and inserts specific replacements.
- An offline script resolves each mapped ingredient to one FDC SR Legacy food by exact description. It writes a frozen CSV snapshot, which is committed.
- Migration 0006 creates `ingredient_nutrients` and seeds it from that CSV.
- A pure `compose()` function turns recipe rows plus per-100 g nutrients into a `Composition`. A pure `suggest_salt()` turns them into a default salt amount.
- `GET /batches/{id}/composition` serves both.
- The frontend unit field becomes a closed `<select>`. Salt is pre-filled when picked, and a "Starting composition" card renders the endpoint.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, Pydantic v2, pytest + aiosqlite, React/Vite/Tailwind. There are no new dependencies. The fetch script uses stdlib `urllib`.

**Spec:** `docs/superpowers/specs/2026-09-23-ingredient-nutrients-design.md` (§1–3 are this increment; §4 is Increment 2, out of scope here)

## Global Constraints

- No new runtime or dev dependencies.
- Every stored nutrient amount is **grams per 100 g**. Convert mg and µg at snapshot time.
- **Missing ≠ zero.** Never write or treat an unreported nutrient as 0. Composition reports it in `missing_from`.
- `fdc_nutrients_v1.csv` is **frozen** once committed. A future snapshot means `_v2` plus a new migration. Never edit v1.
- `Ingredient.canonical_id` is reserved for the fermentgraph export. Don't touch it.
- Recipe-derived `salt_pct` must **not** feed `safety/service.py` in this increment (spec §3, open decision 1).
- The salt default is a **form pre-fill only**. Never auto-insert a `BatchIngredient` row (spec §3.1). A logged `0 g` is a known zero.
- Seed ingredients are never deleted. Retire them with `is_active = False` (the experiment-logging spec's soft-deprecation rule).
- The closed unit set is `g, kg, mg, ml, L`. ml and L assume a density of 1.0. Mark that with a `ponytail:` comment.
- The only outbound network call is `scripts/fetch_fdc_snapshot.py` → `api.nal.usda.gov`, sending public food descriptions only. **Confirm with Achille before running it** (global CLAUDE.md confidentiality rule).
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Never push or deploy Task 5 without Task 6.** Task 5 makes the API reject free-text units with a 422, and the current frontend would show that error as "[object Object]". Commit locally per task. Pushing is Achille's call, after Task 6.
- Lint baseline: the repo already has ruff errors. New or changed code must add **no new** ruff or mypy errors. Compare against `ruff check` / `mypy src` output from before the task.

---

### Task 1: Split vague seed ingredients (migration 0005)

**Files:**
- Modify: `src/fermenttrack/seed_data.py` (append `INGREDIENT_SEED_DATA_V3`, `RETIRED_V3`, `WATER_SYSTEMS_V3`)
- Create: `alembic/versions/0005_split_vague_ingredients.py`
- Modify: `src/fermenttrack/routers/batches.py` (`add_batch_ingredient`: reject retired ingredients)
- Modify: `src/fermenttrack/routers/ingredients.py` (`include_retired` query flag, so historical recipes still resolve names)
- Test: `tests/test_seed_data.py`, `tests/test_batch_ingredients.py`, `tests/test_ingredients.py` (append to each)

**Interfaces:**
- Produces:
  - `INGREDIENT_SEED_DATA_V3: list[tuple[str, str, list[str]]]`
  - `RETIRED_V3: list[str]`
  - `WATER_SYSTEMS_V3: list[str]`
  - `FLOURS: frozenset[str]`, which Task 4 uses as the sourdough salt basis
  - `POST /batches/{id}/ingredients` now returns 400 for an inactive ingredient

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_seed_data.py`, and change its import to a wrapped form (so it stays under 100 characters):

```python
from fermenttrack.seed_data import (
    FLOURS,
    INGREDIENT_SEED_DATA,
    INGREDIENT_SEED_DATA_V2,
    INGREDIENT_SEED_DATA_V3,
    RETIRED_V3,
)
```

```python
def test_v3_names_unique_and_new() -> None:
    old = {n for n, _r, _s in INGREDIENT_SEED_DATA + INGREDIENT_SEED_DATA_V2}
    new = [n for n, _r, _s in INGREDIENT_SEED_DATA_V3]
    assert len(new) == len(set(new))
    assert not (set(new) & old)


def test_v3_roles_and_systems_valid() -> None:
    for name, role, systems in INGREDIENT_SEED_DATA_V3:
        assert role in VALID_ROLES, name
        assert systems, name


def test_retired_names_exist_and_each_system_keeps_a_replacement() -> None:
    old = {n: s for n, _r, s in INGREDIENT_SEED_DATA + INGREDIENT_SEED_DATA_V2}
    v3_systems = {s for _n, _r, systems in INGREDIENT_SEED_DATA_V3 for s in systems}
    for name in RETIRED_V3:
        assert name in old, name
        assert set(old[name]) <= v3_systems, name  # no substrate loses its option


def test_rice_grain_soybean_is_retired() -> None:
    assert "Rice/grain/soybean" in RETIRED_V3


def test_flours_are_v3_sourdough_ingredients() -> None:
    v3 = {n: s for n, _r, s in INGREDIENT_SEED_DATA_V3}
    assert FLOURS and all("sourdough" in v3[f] for f in FLOURS)
```

Append to `tests/test_batch_ingredients.py`:

```python
@pytest.mark.asyncio
async def test_add_retired_ingredient_rejected(client: AsyncClient, db_session: AsyncSession) -> None:
    retired = Ingredient(
        name="Fruit", default_role="flavoring", fermentation_systems=["kombucha"], is_active=False
    )
    db_session.add(retired)
    await db_session.commit()
    _culture_id, batch_id = await _create_culture_and_batch(client)

    resp = await client.post(f"/batches/{batch_id}/ingredients", json={"ingredient_id": str(retired.id)})
    assert resp.status_code == 400
    assert "retired" in resp.json()["detail"]
```

Append to `tests/test_ingredients.py`, reusing its existing imports:

```python
@pytest.mark.asyncio
async def test_include_retired_flag(client: AsyncClient, db_session: AsyncSession) -> None:
    db_session.add_all(
        [
            Ingredient(name="Lemon", default_role="flavoring", fermentation_systems=["kombucha"]),
            Ingredient(
                name="Fruit", default_role="flavoring", fermentation_systems=["kombucha"], is_active=False
            ),
        ]
    )
    await db_session.commit()

    default = {i["name"] for i in (await client.get("/ingredients?substrate=kombucha")).json()}
    everything = {
        i["name"]
        for i in (await client.get("/ingredients?substrate=kombucha&include_retired=true")).json()
    }
    assert default == {"Lemon"}
    assert everything == {"Lemon", "Fruit"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_seed_data.py tests/test_batch_ingredients.py -v`
Expected: FAIL with `ImportError: cannot import name 'FLOURS'`

- [ ] **Step 3: Append to `src/fermenttrack/seed_data.py`**

```python
# Added 2026-09-23 (migration 0005): generic rows were too vague to attach
# reference nutrients to (docs/superpowers/specs/2026-09-23-ingredient-
# nutrients-design.md § 2). The generic rows are retired (is_active=False),
# never deleted — historical batch_ingredients keep pointing at them.
FLOURS = frozenset({"White wheat flour", "Whole wheat flour", "Rye flour"})

INGREDIENT_SEED_DATA_V3: list[tuple[str, str, list[str]]] = [
    ("White rice", "base", ["koji", "miso"]),
    ("Pearl barley", "base", ["koji", "miso"]),
    ("Soybeans", "base", ["koji", "miso"]),
    ("White wheat flour", "base", ["sourdough"]),
    ("Whole wheat flour", "base", ["sourdough"]),
    ("Rye flour", "base", ["sourdough"]),
    ("Lemon", "flavoring", ["kombucha", "kefir"]),
    ("Strawberries", "flavoring", ["kombucha", "kefir"]),
    ("Raspberries", "flavoring", ["kombucha", "kefir"]),
    ("Apple", "flavoring", ["kombucha", "kefir"]),
    ("Mint", "flavoring", ["kombucha", "kefir"]),
    ("Basil", "flavoring", ["kombucha", "kefir"]),
    ("Cinnamon", "flavoring", ["kombucha", "kefir"]),
    ("Turmeric", "flavoring", ["kombucha", "kefir"]),
    ("Cardamom", "flavoring", ["kombucha", "kefir"]),
    ("Red wine", "base", ["vinegar"]),
    ("White wine", "base", ["vinegar"]),
    ("Hard cider", "base", ["vinegar"]),
    ("Black tea leaves", "base", ["kombucha"]),
    ("Green tea leaves", "base", ["kombucha"]),
    ("Anchovies", "base", ["garum"]),
    ("Mackerel", "base", ["garum"]),
]

RETIRED_V3: list[str] = [
    "Rice/grain/soybean",
    "Flour",
    "Fruit",
    "Herbs",
    "Spices",
    "Wine/cider/base alcohol",
    "Black/green tea",
    "Fish",
]

# Brine ferments (e.g. chilies in brine) log water as a base ingredient.
WATER_SYSTEMS_V3: list[str] = ["kombucha", "sourdough", "lacto_ferment"]
```

- [ ] **Step 4: Add the retired-ingredient guard in `add_batch_ingredient`** (`routers/batches.py`)

Directly after the `if ingredient is None: raise HTTPException(404, ...)` block:

```python
    if not ingredient.is_active:
        raise HTTPException(
            status_code=400,
            detail=f"{ingredient.name!r} is retired; pick a specific ingredient instead",
        )
```

In `routers/ingredients.py`, add the flag and make the active filter conditional:

```python
@router.get("", response_model=list[IngredientOut])
async def list_ingredients(
    substrate: str | None = Query(default=None, description="Filter to a fermentation_systems entry, e.g. 'kombucha'"),
    include_retired: bool = Query(default=False, description="Also return retired rows (to label historical recipes)"),
    db: AsyncSession = Depends(get_db),
) -> list[Ingredient]:
    stmt = select(Ingredient)
    if not include_retired:
        stmt = stmt.where(Ingredient.is_active.is_(True))
    result = await db.execute(stmt)
```

Leave the rest of the function (the substrate filter and the return) unchanged.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_seed_data.py tests/test_batch_ingredients.py tests/test_ingredients.py -v`
Expected: all pass

- [ ] **Step 6: Write `alembic/versions/0005_split_vague_ingredients.py`**

```python
"""split vague seed ingredients into specific ones; Water gains lacto_ferment

Generic rows (Rice/grain/soybean, Flour, Fruit, ...) are retired with
is_active=False, never deleted, so historical batch_ingredients keep their FK.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-23

"""
from __future__ import annotations

import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from fermenttrack.seed_data import INGREDIENT_SEED_DATA_V3, RETIRED_V3, WATER_SYSTEMS_V3

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_WATER_SYSTEMS = ["kombucha", "sourdough"]


def _table() -> sa.Table:
    return sa.table(
        "ingredients",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("canonical_id", sa.Text()),
        sa.column("name", sa.Text()),
        sa.column("default_role", sa.Text()),
        sa.column("fermentation_systems", sa.JSON()),
        sa.column("is_active", sa.Boolean()),
    )


def upgrade() -> None:
    t = _table()
    op.bulk_insert(
        t,
        [
            {
                "id": uuid.uuid4(),
                "canonical_id": None,
                "name": name,
                "default_role": role,
                "fermentation_systems": systems,
                "is_active": True,
            }
            for name, role, systems in INGREDIENT_SEED_DATA_V3
        ],
    )
    op.execute(t.update().where(t.c.name.in_(RETIRED_V3)).values(is_active=False))
    op.execute(t.update().where(t.c.name == "Water").values(fermentation_systems=WATER_SYSTEMS_V3))


def downgrade() -> None:
    # Fails on FK if any batch already logged a V3 ingredient — intended: don't lose recipe data.
    t = _table()
    op.execute(t.update().where(t.c.name == "Water").values(fermentation_systems=_OLD_WATER_SYSTEMS))
    op.execute(t.update().where(t.c.name.in_(RETIRED_V3)).values(is_active=True))
    op.execute(t.delete().where(t.c.name.in_([n for n, _r, _s in INGREDIENT_SEED_DATA_V3])))
```

- [ ] **Step 7: Run the migration against Postgres, if one is available**

Run: `alembic upgrade head`, then `alembic downgrade -1`, then `alembic upgrade head`
Expected: no errors. `GET /ingredients?substrate=miso` lists White rice, Pearl barley, Soybeans, Salt and Koji spores, but not "Rice/grain/soybean".
If there's no local Postgres, say so in the task report instead of claiming it was verified.

- [ ] **Step 8: Run the full suite, then commit**

Run: `pytest -q`
Expected: all pass

```bash
git add src/fermenttrack/seed_data.py alembic/versions/0005_split_vague_ingredients.py src/fermenttrack/routers/batches.py src/fermenttrack/routers/ingredients.py tests/test_seed_data.py tests/test_batch_ingredients.py tests/test_ingredients.py
git commit -m "feat: split vague seed ingredients into specific ones, retire the generic rows

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Nutrient registry, FDC mapping, frozen snapshot

**Files:**
- Create: `src/fermenttrack/nutrients.py`
- Modify: `src/fermenttrack/seed_data.py` (append `INGREDIENT_FDC_MAP`)
- Create: `scripts/fetch_fdc_snapshot.py`
- Create (generated): `src/fermenttrack/fdc_nutrients_v1.csv`
- Test: `tests/test_nutrients.py`, `tests/test_fdc_snapshot.py`

**Interfaces:**
- Produces:
  - `NUTRIENTS: dict[str, tuple[int, ...]]`: nutrient code → FDC nutrient ids, where the first id reported wins.
  - `FDC_SNAPSHOT_V1: Path`
  - `SnapshotRow(ingredient_name: str, fdc_id: str, nutrient: str, amount_per_100g: float)`
  - `fdc_amount_to_grams(amount: float, unit_name: str) -> float`
  - `snapshot_rows(ingredient_name: str, description: str, foods: list[dict]) -> list[SnapshotRow]`
  - `load_snapshot(path: Path = FDC_SNAPSHOT_V1) -> list[SnapshotRow]`
  - `nutrient_seed_rows(snapshot: list[SnapshotRow], ids_by_name: dict[str, uuid.UUID]) -> list[dict]`
  - `INGREDIENT_FDC_MAP: dict[str, str]`: ingredient name → exact FDC SR Legacy description.

- [ ] **Step 1: Write the failing unit tests**

`tests/test_nutrients.py`:

```python
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
    rows = nutrient_seed_rows([SnapshotRow("Cabbage", "169975", "protein", 1.28)], {"Cabbage": cabbage_id})
    assert rows[0]["ingredient_id"] == cabbage_id
    assert rows[0]["source"] == "usda_fdc"
    assert rows[0]["source_food_id"] == "169975"
    assert rows[0]["source_version"] == "fdc_nutrients_v1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_nutrients.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'fermenttrack.nutrients'`

- [ ] **Step 3: Implement `src/fermenttrack/nutrients.py`**

```python
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
            SnapshotRow(r["ingredient_name"], r["fdc_id"], r["nutrient"], float(r["amount_per_100g"]))
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_nutrients.py -v`
Expected: 6 passed

- [ ] **Step 5: Add the mapping to `src/fermenttrack/seed_data.py`**

Append at the end of the file:

```python
# Ingredient name -> exact USDA FDC SR Legacy description (docs/superpowers/
# specs/2026-09-23-ingredient-nutrients-design.md § 2). Resolved to an fdcId
# by scripts/fetch_fdc_snapshot.py, which fails loudly unless exactly one
# search hit matches. Deliberately absent: retired generic rows (RETIRED_V3),
# starters/cultures (no FDC entry; levain etc. can be real mass, lowering coverage), tea leaves (FDC has brewed tea, not dry
# leaves), calcium chloride, and hard cider unless FDC SR Legacy has an exact
# entry. They show up as "unmapped" in composition.
INGREDIENT_FDC_MAP: dict[str, str] = {
    "Water": "Beverages, water, tap, drinking",
    "Cane sugar": "Sugars, granulated",
    "Fresh ginger": "Ginger root, raw",
    "Milk": "Milk, whole, 3.25% milkfat, with added vitamin D",
    "Salt": "Salt, table",
    "Cabbage": "Cabbage, raw",
    "Chilies": "Peppers, hot chili, red, raw",
    "White rice": "Rice, white, short-grain, raw",
    "Pearl barley": "Barley, pearled, raw",
    "Soybeans": "Soybeans, mature seeds, raw",
    "White wheat flour": "Wheat flour, white, bread, enriched",
    "Whole wheat flour": "Wheat flour, whole-grain",
    "Rye flour": "Rye flour, dark",
    "Lemon": "Lemons, raw, without peel",
    "Strawberries": "Strawberries, raw",
    "Raspberries": "Raspberries, raw",
    "Apple": "Apples, raw, with skin",
    "Mint": "Spearmint, fresh",
    "Basil": "Basil, fresh",
    "Cinnamon": "Spices, cinnamon, ground",
    "Turmeric": "Spices, turmeric, ground",
    "Cardamom": "Spices, cardamom",
    "Red wine": "Alcoholic beverage, wine, table, red",
    "White wine": "Alcoholic beverage, wine, table, white",
    "Anchovies": "Fish, anchovy, european, raw",
    "Mackerel": "Fish, mackerel, Atlantic, raw",
}
```

- [ ] **Step 6: Write `scripts/fetch_fdc_snapshot.py`**

```python
"""Fetch the frozen FDC nutrient snapshot for INGREDIENT_FDC_MAP.

    python scripts/fetch_fdc_snapshot.py [--api-key KEY]

Writes src/fermenttrack/fdc_nutrients_v1.csv. FROZEN once migration 0006 has
run anywhere — a new snapshot is fdc_nutrients_v2.csv + a new migration.
Only public FDC food descriptions leave the machine; no batch or user data.
"""

from __future__ import annotations

import argparse
import csv
import json
import urllib.parse
import urllib.request
from typing import Any

from fermenttrack.nutrients import FDC_SNAPSHOT_V1, SnapshotRow, snapshot_rows
from fermenttrack.seed_data import INGREDIENT_FDC_MAP

_SEARCH = "https://api.nal.usda.gov/fdc/v1/foods/search"


def _search(description: str, api_key: str) -> list[dict[str, Any]]:
    qs = urllib.parse.urlencode(
        {"query": description, "dataType": "SR Legacy", "pageSize": 200, "api_key": api_key}
    )
    with urllib.request.urlopen(f"{_SEARCH}?{qs}", timeout=30) as resp:
        foods: list[dict[str, Any]] = json.load(resp)["foods"]
    return foods


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", default="DEMO_KEY")
    args = parser.parse_args()

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
```

- [ ] **Step 7: Verify the licence, get approval, run the script**

1. Open https://fdc.nal.usda.gov/ and confirm that the "About / Data licensing" page still says CC0 / public domain. Note the date checked in the commit message.
2. **Ask Achille** before running the script. It makes an outbound call (see Global Constraints). Also ask for a free api.data.gov key: `DEMO_KEY` allows about 30 requests per hour, and one run makes 26 calls, so a re-run would be throttled.
3. Run `python scripts/fetch_fdc_snapshot.py --api-key <KEY>`.
4. **If the snapshot can't be fetched** (approval declined, network failure, throttling), **stop here and report.** Tasks 3–6 need the committed CSV: `test_fdc_snapshot.py` and migration 0006 both load it. Commit Steps 1–6 alone and don't write `test_fdc_snapshot.py` yet.
5. If search results come back without `foodNutrients`, fetch `/v1/food/{fdcId}` for the exact match instead. Keep `snapshot_rows` pure, and adapt only `_search` in the script.

Expected: `wrote N rows for 26 ingredients to ...fdc_nutrients_v1.csv`.

The descriptions above come from memory of SR Legacy naming. Some carry suffixes in FDC, for example `"(Includes foods for USDA's Food Distribution Program)"`. If the script exits with `0 exact matches for '...'. Nearest: ...`:
- If the "Nearest" list has the same food, copy its exact description into `INGREDIENT_FDC_MAP` and re-run.
- If no entry is the same food, **remove the entry** so the ingredient stays unmapped, and note it in the commit message.
- **Never loosen the match to substring matching, and never map to a different food.**

- [ ] **Step 8: Write the data sanity tests on the frozen CSV**

`tests/test_fdc_snapshot.py`:

```python
"""Sanity checks on the committed, frozen FDC snapshot — catches a wrong food match."""

from __future__ import annotations

from collections import defaultdict

from fermenttrack.nutrients import NUTRIENTS, load_snapshot
from fermenttrack.seed_data import (
    INGREDIENT_FDC_MAP,
    INGREDIENT_SEED_DATA,
    INGREDIENT_SEED_DATA_V2,
    INGREDIENT_SEED_DATA_V3,
    RETIRED_V3,
)

ROWS = load_snapshot()
BY_ING: dict[str, dict[str, float]] = defaultdict(dict)
for _r in ROWS:
    BY_ING[_r.ingredient_name][_r.nutrient] = _r.amount_per_100g


def test_every_mapped_ingredient_is_in_snapshot_and_active_seed() -> None:
    all_seed = INGREDIENT_SEED_DATA + INGREDIENT_SEED_DATA_V2 + INGREDIENT_SEED_DATA_V3
    active = {n for n, _r, _s in all_seed} - set(RETIRED_V3)
    assert set(BY_ING) == set(INGREDIENT_FDC_MAP)
    assert set(INGREDIENT_FDC_MAP) <= active


def test_codes_known_and_amounts_are_plausible_grams_per_100g() -> None:
    for r in ROWS:
        assert r.nutrient in NUTRIENTS
        assert 0.0 <= r.amount_per_100g <= 100.0, r


def test_proximates_do_not_exceed_100g() -> None:
    for name, n in BY_ING.items():
        proximate = sum(n.get(k, 0.0) for k in ("water", "protein", "fat", "carbohydrate"))
        assert proximate <= 102.0, (name, proximate)  # FDC rounding / ash slack


def test_anchor_foods_match_known_composition() -> None:
    sugar = BY_ING["Cane sugar"]
    assert max(sugar.get("sucrose", 0.0), sugar.get("sugars_total", 0.0)) >= 99.0
    assert 38.0 <= BY_ING["Salt"]["sodium"] <= 39.5  # NaCl is 39.3 % Na
    assert 4.0 <= BY_ING["Milk"]["sugars_total"] <= 6.0
    assert 65.0 <= BY_ING["White wheat flour"]["carbohydrate"] <= 80.0
    assert 30.0 <= BY_ING["Soybeans"]["protein"] <= 40.0
    assert 75.0 <= BY_ING["White rice"]["carbohydrate"] <= 82.0
    assert BY_ING["Water"]["water"] >= 99.0
```

- [ ] **Step 9: Run all of Task 2's tests**

Run: `pytest tests/test_nutrients.py tests/test_fdc_snapshot.py -v`
Expected: all pass. If an anchor test fails, the food match is wrong. Fix the description in Step 7 rather than the test.

- [ ] **Step 10: Commit**

```bash
git add src/fermenttrack/nutrients.py src/fermenttrack/seed_data.py scripts/fetch_fdc_snapshot.py src/fermenttrack/fdc_nutrients_v1.csv tests/test_nutrients.py tests/test_fdc_snapshot.py
git commit -m "feat: add USDA FDC nutrient registry and frozen v1 ingredient snapshot

FDC licence (CC0) re-checked <date>.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `IngredientNutrient` model + migration 0006

**Files:**
- Modify: `src/fermenttrack/models.py` (imports, `Ingredient.nutrients`, new class)
- Create: `alembic/versions/0006_ingredient_nutrients.py`
- Test: `tests/test_ingredients_model.py` (append)

**Interfaces:**
- Consumes: `nutrient_seed_rows`, `load_snapshot`, `FDC_SNAPSHOT_V1` (Task 2)
- Produces: `IngredientNutrient` ORM class. Its fields are `id`, `ingredient_id`, `nutrient`, `amount_per_100g`, `source`, `source_food_id`, `source_version`. Also produces the `Ingredient.nutrients: list[IngredientNutrient]` relationship.

- [ ] **Step 1: Write the failing test** (append to `tests/test_ingredients_model.py`)

Merge the imports into the file's existing header; don't paste the import block below as written. That file already imports `select`, `AsyncSession` and `Ingredient` (lines 5–7), so the only new imports are `IntegrityError`, `selectinload` and `IngredientNutrient`. Pasting it as-is causes E402/F811.

```python
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fermenttrack.models import Ingredient, IngredientNutrient


@pytest.mark.asyncio
async def test_ingredient_nutrients_roundtrip_and_unique_per_source(db_session: AsyncSession) -> None:
    salt = Ingredient(name="Salt", default_role="additive", fermentation_systems=["lacto_ferment"])
    salt.nutrients.append(
        IngredientNutrient(
            nutrient="sodium", amount_per_100g=38.758, source="usda_fdc",
            source_food_id="173468", source_version="fdc_nutrients_v1",
        )
    )
    db_session.add(salt)
    await db_session.commit()

    loaded = (
        await db_session.execute(
            select(Ingredient).where(Ingredient.id == salt.id).options(selectinload(Ingredient.nutrients))
        )
    ).scalar_one()
    assert {n.nutrient: n.amount_per_100g for n in loaded.nutrients} == {"sodium": 38.758}

    db_session.add(
        IngredientNutrient(
            ingredient_id=salt.id, nutrient="sodium", amount_per_100g=1.0, source="usda_fdc",
            source_food_id="x", source_version="fdc_nutrients_v1",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_ingredients_model.py -v -k nutrients`
Expected: FAIL with `ImportError: cannot import name 'IngredientNutrient'`

- [ ] **Step 3: Implement the model in `src/fermenttrack/models.py`**

Change the sqlalchemy import line to:

```python
from sqlalchemy import Boolean, Float, ForeignKey, Interval, JSON, Text, UniqueConstraint
```

Add to `class Ingredient`, after `is_active`:

```python
    nutrients: Mapped[list["IngredientNutrient"]] = relationship()
```

Append at the end of the file:

```python
class IngredientNutrient(Base):
    """Reference nutrient per 100 g (always grams). No row = not reported = unknown, never 0."""

    __tablename__ = "ingredient_nutrients"
    __table_args__ = (UniqueConstraint("ingredient_id", "nutrient", "source"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingredients.id"), nullable=False
    )
    nutrient: Mapped[str] = mapped_column(Text, nullable=False)  # key of nutrients.NUTRIENTS
    amount_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)  # "usda_fdc"
    source_food_id: Mapped[str] = mapped_column(Text, nullable=False)  # FDC fdcId
    source_version: Mapped[str] = mapped_column(Text, nullable=False)  # snapshot file stem
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_ingredients_model.py -v`
Expected: all pass

- [ ] **Step 5: Write `alembic/versions/0006_ingredient_nutrients.py`**

```python
"""ingredient_nutrients — USDA FDC reference composition, seeded from the frozen v1 snapshot

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-23

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from fermenttrack.nutrients import FDC_SNAPSHOT_V1, load_snapshot, nutrient_seed_rows

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    table = op.create_table(
        "ingredient_nutrients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ingredient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ingredients.id"),
            nullable=False,
        ),
        sa.Column("nutrient", sa.Text(), nullable=False),
        sa.Column("amount_per_100g", sa.Float(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_food_id", sa.Text(), nullable=False),
        sa.Column("source_version", sa.Text(), nullable=False),
        sa.UniqueConstraint("ingredient_id", "nutrient", "source"),
    )
    ids_by_name = {
        name: id_ for id_, name in op.get_bind().execute(sa.text("SELECT id, name FROM ingredients"))
    }
    # FDC_SNAPSHOT_V1 is frozen, so this migration stays a faithful record of what it inserted.
    op.bulk_insert(table, nutrient_seed_rows(load_snapshot(FDC_SNAPSHOT_V1), ids_by_name))


def downgrade() -> None:
    op.drop_table("ingredient_nutrients")
```

- [ ] **Step 6: Run the migration against a real Postgres, if one is available**

Run: `alembic upgrade head`, then `alembic downgrade -1`, then `alembic upgrade head`
Expected: no errors. `SELECT count(*) FROM ingredient_nutrients` equals the snapshot's row count.
If there is no local Postgres, say so in the task report. **Do not claim the migration was verified.** There's no backend CI; Render's `alembic upgrade head` at startup (`render.yaml`) is the first real run.

- [ ] **Step 7: Run the full suite, then commit**

Run: `pytest -q`
Expected: all pass

```bash
git add src/fermenttrack/models.py alembic/versions/0006_ingredient_nutrients.py tests/test_ingredients_model.py
git commit -m "feat: add ingredient_nutrients table seeded from the FDC v1 snapshot

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Pure `compose()`: batch composition at t = 0

**Files:**
- Create: `src/fermenttrack/composition.py`
- Test: `tests/test_composition.py`

**Interfaces:**
- Consumes: `FLOURS` (Task 1)
- Produces:
  - `RecipeItem(name: str, quantity: float | None, unit: str | None, per_100g: dict[str, float], role: str = "base")`
  - `SALT_DEFAULTS: dict[str, tuple[float, frozenset[str] | None]]`
  - `SaltSuggestion(pct: float, basis_g: float, grams: float)`
  - `suggest_salt(ferment_type: str, items: list[RecipeItem]) -> SaltSuggestion | None`
  - `to_grams(quantity: float | None, unit: str | None) -> float | None`
  - `NutrientTotal(grams: float, missing_from: list[str])`
  - `Composition(total_mass_g, mapped_mass_g, nutrients: dict[str, NutrientTotal], unmapped: list[str], unquantified: list[str], salt_g: float | None = None)`. It has the properties `.coverage -> float` and `.salt_pct -> float | None`, and the method `.per_100g(nutrient: str) -> float`.
  - `compose(items: list[RecipeItem]) -> Composition`

- [ ] **Step 1: Write the failing tests**

`tests/test_composition.py`:

```python
"""compose(): recipe × per-100 g nutrients → batch composition. Synthetic data, no DB."""

from __future__ import annotations

import pytest

from fermenttrack.composition import RecipeItem, compose, to_grams

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
```

Update the test file's import line to:

```python
from fermenttrack.composition import RecipeItem, SaltSuggestion, compose, suggest_salt, to_grams
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_composition.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'fermenttrack.composition'`

- [ ] **Step 3: Implement `src/fermenttrack/composition.py`**

```python
"""Batch nutrient composition at t=0: recipe quantities × reference nutrients per 100 g.

Pure, no DB. Figures are LOWER BOUNDS whenever coverage < 1 or a nutrient's
missing_from is non-empty — unmapped / unreported means unknown, never zero.
Design: docs/superpowers/specs/2026-09-23-ingredient-nutrients-design.md § 3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import NamedTuple

from fermenttrack.seed_data import FLOURS

# ponytail: ml/L assume density 1.0 — exact for water, ~3 % low for milk, ~40 % for
# honey. Add a per-ingredient density column when a recipe needs it.
_GRAMS_PER_UNIT = {"g": 1.0, "kg": 1000.0, "mg": 0.001, "ml": 1.0, "l": 1000.0}


class RecipeItem(NamedTuple):
    name: str
    quantity: float | None
    unit: str | None
    per_100g: dict[str, float]  # empty = ingredient has no reference data
    role: str = "base"


# ferment type -> (salt fraction, basis). Basis None = every logged base-role
# item (vegetables + brine water, soy + grain, fish); otherwise only those names.
# Spec § 3.1. lacto_ferment's 3 % sits in SALT-001's recommended 2-5 % band.
SALT_DEFAULTS: dict[str, tuple[float, frozenset[str] | None]] = {
    "lacto_ferment": (0.03, None),
    "miso": (0.21, None),  # of DRY soy + grain (~12 % of finished miso)
    "garum": (0.20, None),
    "sourdough": (0.02, FLOURS),
}


class SaltSuggestion(NamedTuple):
    pct: float
    basis_g: float
    grams: float


@dataclass
class NutrientTotal:
    grams: float = 0.0
    missing_from: list[str] = field(default_factory=list)


@dataclass
class Composition:
    total_mass_g: float
    mapped_mass_g: float
    nutrients: dict[str, NutrientTotal]
    unmapped: list[str]
    unquantified: list[str]

    @property
    def coverage(self) -> float:
        return self.mapped_mass_g / self.total_mass_g if self.total_mass_g else 0.0

    salt_g: float | None = None  # grams of logged Salt rows; None = no Salt row logged

    def per_100g(self, nutrient: str) -> float:
        if not self.total_mass_g:
            return 0.0
        return self.nutrients[nutrient].grams / self.total_mass_g * 100

    @property
    def salt_pct(self) -> float | None:
        """Added-salt share of batch mass. None = salt not logged (unknown); a logged
        0 g is a known 0. Intrinsic food sodium stays in nutrients["sodium"], not here -
        otherwise unsalted cabbage would read as ~0.05 % "salt". Not fed to safety."""
        if self.salt_g is None:
            return None
        return self.salt_g / self.total_mass_g * 100 if self.total_mass_g else 0.0


def to_grams(quantity: float | None, unit: str | None) -> float | None:
    if quantity is None or unit is None:
        return None
    factor = _GRAMS_PER_UNIT.get(unit.strip().lower())
    return None if factor is None else quantity * factor


def compose(items: list[RecipeItem]) -> Composition:
    total = mapped = 0.0
    salt_g: float | None = None
    unmapped: list[str] = []
    unquantified: list[str] = []
    weighed: list[tuple[RecipeItem, float]] = []
    for item in items:
        grams = to_grams(item.quantity, item.unit)
        if grams is None:
            unquantified.append(item.name)
            continue
        total += grams
        if item.name == "Salt":
            salt_g = (salt_g or 0.0) + grams
        if not item.per_100g:
            unmapped.append(item.name)
            continue
        mapped += grams
        weighed.append((item, grams))

    reported = sorted({n for item, _ in weighed for n in item.per_100g})
    nutrients = {n: NutrientTotal() for n in reported}
    for item, grams in weighed:
        for n, acc in nutrients.items():
            if n in item.per_100g:
                acc.grams += item.per_100g[n] * grams / 100
            else:
                acc.missing_from.append(item.name)
    return Composition(total, mapped, nutrients, unmapped, unquantified, salt_g)


def suggest_salt(ferment_type: str, items: list[RecipeItem]) -> SaltSuggestion | None:
    """Default salt to PRE-FILL in the recipe form — never auto-logged (spec § 3.1).

    None when the ferment takes no salt, any Salt row exists (even 0 g, an
    explicit choice), or no base mass is logged yet.
    """
    default = SALT_DEFAULTS.get(ferment_type)
    if default is None or any(i.name == "Salt" for i in items):
        return None
    fraction, basis_names = default
    basis = 0.0
    for i in items:
        grams = to_grams(i.quantity, i.unit)
        if grams is not None and i.role == "base" and (basis_names is None or i.name in basis_names):
            basis += grams
    if basis == 0.0:
        return None
    return SaltSuggestion(pct=round(fraction * 100, 2), basis_g=basis, grams=round(basis * fraction, 1))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_composition.py -v`
Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
git add src/fermenttrack/composition.py tests/test_composition.py
git commit -m "feat: add pure batch composition and per-ferment salt suggestion

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: `GET /batches/{id}/composition` + closed unit set on the API

**Files:**
- Modify: `src/fermenttrack/schemas.py` (the `Unit` literal, `BatchIngredientCreate.unit`, new output schemas)
- Modify: `src/fermenttrack/routers/batches.py` (new endpoint, imports)
- Modify: `docs/ARCHITECTURE.md` (add the endpoint line to the API list)
- Test: `tests/test_batch_composition.py`

**Interfaces:**
- Consumes: `compose`, `suggest_salt`, `RecipeItem`, `to_grams` (Task 4); `Ingredient.nutrients`, `IngredientNutrient` (Task 3)
- Produces:
  - `Unit = Literal["g", "kg", "mg", "ml", "L"]`
  - `NutrientTotalOut(nutrient, grams, per_100g, missing_from)`
  - `SaltSuggestionOut(pct, basis_g, grams)`
  - `BatchCompositionOut(total_mass_g, mapped_mass_g, coverage, salt_pct, salt_suggestion: SaltSuggestionOut | None, nutrients: list[NutrientTotalOut], unmapped, unquantified)`
  - The route `GET /batches/{batch_id}/composition`

- [ ] **Step 1: Write the failing tests**

`tests/test_batch_composition.py`:

```python
"""GET /batches/{id}/composition and the closed unit set on recipe logging."""

from __future__ import annotations

import typing
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.composition import to_grams
from fermenttrack.models import Ingredient, IngredientNutrient
from fermenttrack.schemas import Unit


def _nutrient(code: str, amount: float) -> IngredientNutrient:
    return IngredientNutrient(
        nutrient=code, amount_per_100g=amount, source="usda_fdc",
        source_food_id="0", source_version="fdc_nutrients_v1",
    )


async def _lacto_batch(client: AsyncClient) -> str:
    culture = (await client.post("/cultures", json={"name": "Kraut", "type": "lacto_ferment"})).json()
    return (await client.post("/batches", json={"culture_id": culture["id"]})).json()["id"]


async def _ingredient(db: AsyncSession, name: str, nutrients: dict[str, float]) -> str:
    ing = Ingredient(name=name, default_role="base", fermentation_systems=["lacto_ferment"])
    ing.nutrients = [_nutrient(k, v) for k, v in nutrients.items()]
    db.add(ing)
    await db.commit()
    return str(ing.id)


def test_every_api_unit_converts_to_grams() -> None:
    for unit in typing.get_args(Unit):
        assert to_grams(1.0, unit) is not None, unit


@pytest.mark.asyncio
async def test_composition_brine(client: AsyncClient, db_session: AsyncSession) -> None:
    cabbage = await _ingredient(db_session, "Cabbage", {"sugars_total": 3.2, "sodium": 0.018})
    salt = await _ingredient(db_session, "Salt", {"sodium": 38.758})
    chilies = await _ingredient(db_session, "Chilies", {})
    batch_id = await _lacto_batch(client)
    for ing, qty, unit in [(cabbage, 1.0, "kg"), (salt, 20.0, "g"), (chilies, 30.0, "g")]:
        resp = await client.post(
            f"/batches/{batch_id}/ingredients", json={"ingredient_id": ing, "quantity": qty, "unit": unit}
        )
        assert resp.status_code == 201

    body = (await client.get(f"/batches/{batch_id}/composition")).json()
    assert body["total_mass_g"] == 1050.0
    assert body["mapped_mass_g"] == 1020.0
    assert body["unmapped"] == ["Chilies"]
    assert body["salt_pct"] == pytest.approx(20 / 1050 * 100)  # added salt only
    sugars = next(n for n in body["nutrients"] if n["nutrient"] == "sugars_total")
    assert sugars["grams"] == pytest.approx(32.0)
    assert sugars["missing_from"] == ["Salt"]
    assert body["salt_suggestion"] is None  # salt already logged


@pytest.mark.asyncio
async def test_salt_suggestion_before_salt_is_logged(client: AsyncClient, db_session: AsyncSession) -> None:
    cabbage = await _ingredient(db_session, "Cabbage", {"sugars_total": 3.2})
    batch_id = await _lacto_batch(client)
    await client.post(
        f"/batches/{batch_id}/ingredients", json={"ingredient_id": cabbage, "quantity": 1, "unit": "kg"}
    )
    body = (await client.get(f"/batches/{batch_id}/composition")).json()
    assert body["salt_suggestion"] == {"pct": 3.0, "basis_g": 1000.0, "grams": 30.0}
    assert body["salt_pct"] is None  # suggestion is never counted as logged salt


@pytest.mark.asyncio
async def test_composition_empty_recipe(client: AsyncClient) -> None:
    batch_id = await _lacto_batch(client)
    body = (await client.get(f"/batches/{batch_id}/composition")).json()
    assert body == {
        "total_mass_g": 0.0, "mapped_mass_g": 0.0, "coverage": 0.0, "salt_pct": None,
        "salt_suggestion": None, "nutrients": [], "unmapped": [], "unquantified": [],
    }


@pytest.mark.asyncio
async def test_composition_404(client: AsyncClient) -> None:
    assert (await client.get(f"/batches/{uuid.uuid4()}/composition")).status_code == 404


@pytest.mark.asyncio
async def test_free_text_unit_rejected(client: AsyncClient, db_session: AsyncSession) -> None:
    salt = await _ingredient(db_session, "Salt", {"sodium": 38.758})
    batch_id = await _lacto_batch(client)
    resp = await client.post(
        f"/batches/{batch_id}/ingredients", json={"ingredient_id": salt, "quantity": 1, "unit": "tbsp"}
    )
    assert resp.status_code == 422
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_batch_composition.py -v`
Expected: FAIL with `ImportError: cannot import name 'Unit' from 'fermenttrack.schemas'`

- [ ] **Step 3: Update `src/fermenttrack/schemas.py`**

Add to the imports at the top:

```python
from typing import Literal
```

Replace the `BatchIngredientCreate` block with:

```python
# Closed set so composition can convert every new row to grams. Rows logged
# before this existed may hold free text; composition reports them as unquantified.
Unit = Literal["g", "kg", "mg", "ml", "L"]


class BatchIngredientCreate(BaseModel):
    ingredient_id: uuid.UUID
    quantity: float | None = None
    unit: Unit | None = None
    role: str | None = None  # if omitted, copied from Ingredient.default_role
```

Leave `BatchIngredientOut.unit` as `str | None`, because historical rows may hold free text.

Add after the `BatchIngredientOut` block:

```python
# ── Composition ─────────────────────────────────────────────────────────

class NutrientTotalOut(BaseModel):
    nutrient: str
    grams: float
    per_100g: float
    missing_from: list[str]  # mapped ingredients with no reported value: unknown, not 0


class SaltSuggestionOut(BaseModel):
    """Default salt to pre-fill in the recipe form; never logged automatically."""

    pct: float
    basis_g: float
    grams: float


class BatchCompositionOut(BaseModel):
    """Starting composition from the recipe × USDA FDC reference data.

    Every figure is a lower bound when coverage < 1 or a nutrient's
    missing_from is non-empty. salt_pct is added salt (Salt rows) / total mass;
    None = salt not logged, 0 = logged 0 g.
    """

    total_mass_g: float
    mapped_mass_g: float
    coverage: float
    salt_pct: float | None
    salt_suggestion: SaltSuggestionOut | None
    nutrients: list[NutrientTotalOut]
    unmapped: list[str]
    unquantified: list[str]
```

- [ ] **Step 4: Add the endpoint to `src/fermenttrack/routers/batches.py`**

Imports: add `from fermenttrack.composition import RecipeItem, compose, suggest_salt`, and add `BatchCompositionOut`, `NutrientTotalOut`, `SaltSuggestionOut` to the `fermenttrack.schemas` import list, keeping it alphabetical (`SafetyReportOut` sorts before `SaltSuggestionOut`).

Add after `list_batch_ingredients`:

```python
@router.get("/{batch_id}/composition", response_model=BatchCompositionOut)
async def get_batch_composition(
    batch_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> BatchCompositionOut:
    batch = await _get_batch(batch_id, db, with_culture=True)  # 404 if missing
    result = await db.execute(
        select(BatchIngredient)
        .where(BatchIngredient.batch_id == batch_id)
        .options(selectinload(BatchIngredient.ingredient).selectinload(Ingredient.nutrients))
    )
    items = [
        RecipeItem(
            bi.ingredient.name,
            bi.quantity,
            bi.unit,
            {n.nutrient: n.amount_per_100g for n in bi.ingredient.nutrients},
            bi.role,
        )
        for bi in result.scalars()
    ]
    c = compose(items)
    salt = suggest_salt(batch.culture.type, items)
    return BatchCompositionOut(
        total_mass_g=c.total_mass_g,
        mapped_mass_g=c.mapped_mass_g,
        coverage=c.coverage,
        salt_pct=c.salt_pct,
        salt_suggestion=SaltSuggestionOut(**salt._asdict()) if salt else None,
        nutrients=[
            NutrientTotalOut(
                nutrient=name, grams=t.grams, per_100g=c.per_100g(name), missing_from=t.missing_from
            )
            for name, t in c.nutrients.items()
        ],
        unmapped=c.unmapped,
        unquantified=c.unquantified,
    )
```

- [ ] **Step 5: Run the tests, and the full suite, to verify they pass**

Run: `pytest tests/test_batch_composition.py -v`, then `pytest -q`
Expected: all pass. The existing `test_batch_ingredients.py` uses `"g"` and no unit, so it stays green.

- [ ] **Step 6: Document the endpoint**

In `docs/ARCHITECTURE.md`, add this line at the end of the batch routes listing (after the `/compare` line, around line 94):

```
GET    /batches/{id}/composition   Starting nutrient composition (USDA FDC reference × recipe; lower bounds when coverage < 1)
```

- [ ] **Step 7: Commit**

```bash
git add src/fermenttrack/schemas.py src/fermenttrack/routers/batches.py tests/test_batch_composition.py docs/ARCHITECTURE.md
git commit -m "feat: add batch composition endpoint and a closed recipe unit set

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Frontend: unit select, salt pre-fill, "Starting composition" card

**Files:**
- Modify: `frontend/src/App.jsx`:
  - `App` fetches the composition alongside the preview.
  - `Recipe`: unit `<select>`, salt pre-fill, retired-name lookup.
  - New presentational `Composition` component.

**Interfaces:**
- Consumes: `GET /batches/{id}/composition` (Task 5), including `salt_suggestion`; `GET /ingredients?include_retired=true` (Task 1); the `Unit` values `g, kg, mg, ml, L`

- [ ] **Step 1: Fetch the composition in `App.loadPreview`**

Add state next to `preview`:

```jsx
  const [composition, setComposition] = useState(null);
```

In `loadPreview`, add `setComposition(null);` right after the existing `setPreview(null);`, so a previous batch's salt hint can't flash on screen. Then, directly after `setPreview(await res.json());`:

```jsx
      const comp = await fetch(`${API_URL}/batches/${id}/composition`);
      setComposition(comp.ok ? await comp.json() : null);
```

Every existing refresh (`onAdded`, `onLogged`, `onAdvanced`) already calls `loadPreview`, so the composition stays current with no extra wiring.

- [ ] **Step 2: Update `Recipe`: retired names, unit select, salt pre-fill**

Change the signature to take the suggestion:

```jsx
function Recipe({ batchId, substrate, recipe, saltSuggestion, onAdded }) {
```

Fetch retired rows too, so historical recipe lines keep their names. Offer only active ones in the dropdown. Replace the options `fetch` URL with:

```jsx
    fetch(`${API_URL}/ingredients?substrate=${encodeURIComponent(substrate)}&include_retired=true`)
```

In the dropdown's `{options.map(...)}`, change `options.map` to `options.filter((o) => o.is_active).map`. Leave the recipe-list `options.find(...)` lookup as it is: it now also resolves retired names.

Replace the ingredient `<select>`'s `onChange` with a pre-fill-aware handler:

```jsx
          onChange={(e) => {
            const id = e.target.value;
            setIngredientId(id);
            const picked = options.find((o) => o.id === id);
            if (picked?.name === "Salt" && saltSuggestion && quantity === "") {
              setQuantity(String(saltSuggestion.grams));
              setUnit("g");
            }
          }}
```

Replace the `<input ... placeholder="unit" ... />` element with:

```jsx
        <select
          className="w-20 rounded-lg border border-slate-700 bg-slate-900 px-2 py-2 text-sm"
          value={unit}
          onChange={(e) => setUnit(e.target.value)}
        >
          <option value="">unit</option>
          {["g", "kg", "mg", "ml", "L"].map((u) => (
            <option key={u} value={u}>
              {u}
            </option>
          ))}
        </select>
```

Directly after the closing `</form>` (before the `{error && ...}` line), add the hint:

```jsx
      {saltSuggestion && (
        <p className="mt-2 text-xs text-slate-500">
          Suggested salt: {saltSuggestion.grams} g ({saltSuggestion.pct}% of{" "}
          {Math.round(saltSuggestion.basis_g)} g base). Pick Salt to pre-fill it — edit the
          amount, or log 0 g for a deliberately unsalted batch.
        </p>
      )}
```

- [ ] **Step 3: Add the `Composition` component** (place it directly after the `Recipe` function)

```jsx
const NUTRIENT_LABELS = {
  sugars_total: "Sugars (total)",
  sucrose: "Sucrose",
  glucose: "Glucose",
  fructose: "Fructose",
  lactose: "Lactose",
  starch: "Starch",
  protein: "Protein",
  fat: "Fat",
  alcohol: "Alcohol",
};

function Composition({ data }) {
  if (!data || (data.total_mass_g === 0 && data.unquantified.length === 0)) return null;
  const rows = data.nutrients.filter((n) => NUTRIENT_LABELS[n.nutrient]);

  return (
    <Card title="Starting composition">
      <p className="mb-3 text-xs text-slate-500">
        {Math.round(data.total_mass_g)} g total · {Math.round(data.coverage * 100)}% of mass has
        reference data (USDA FoodData Central)
        {data.coverage < 1 && " — figures are lower bounds"}
      </p>
      <ul className="divide-y divide-slate-800 text-sm">
        {data.salt_pct != null && (
          <li className="flex justify-between py-1.5">
            <span>Added salt</span>
            <span>{data.salt_pct.toFixed(2)} %</span>
          </li>
        )}
        {rows.map((n) => (
          <li key={n.nutrient} className="flex justify-between py-1.5">
            <span>{NUTRIENT_LABELS[n.nutrient]}</span>
            <span>
              {n.missing_from.length > 0 && "≥ "}
              {n.grams.toFixed(1)} g · {n.per_100g.toFixed(2)} g/100 g
            </span>
          </li>
        ))}
      </ul>
      {data.unmapped.length > 0 && (
        <p className="mt-2 text-xs text-slate-500">No reference data: {data.unmapped.join(", ")}</p>
      )}
      {data.unquantified.length > 0 && (
        <p className="mt-1 text-xs text-slate-500">
          Not counted (no quantity or unit): {data.unquantified.join(", ")}
        </p>
      )}
    </Card>
  );
}
```

- [ ] **Step 4: Wire both into the batch view in `App`**

Add the prop to the existing `<Recipe ... />` element:

```jsx
            saltSuggestion={composition?.salt_suggestion}
```

Directly after `<Recipe ... />`, and before `<Timeline ... />`:

```jsx
          <Composition data={composition} />
```

- [ ] **Step 5: Build and check in the running app**

Run: `cd frontend && npm run build`
Expected: the build succeeds with no errors.

Then use the `run` skill (or `npm run dev` with the backend up) and check:
1. On a **lacto_ferment** batch, add 1 kg Cabbage. The hint reads "Suggested salt: 30 g (3% of 1000 g base)". Pick Salt, and the quantity pre-fills to 30 with unit g. Submit. The hint disappears and the card shows 2.91 % added salt.
2. On a new lacto_ferment batch, add Cabbage, then Salt with quantity `0`. The card shows 0.00 % added salt, and no suggestion comes back. With cabbage alone and no Salt row, the card shows no salt line at all, because salt is unknown.
3. A **kombucha** batch shows no salt hint.
4. The dropdown for **miso** offers White rice, Pearl barley and Soybeans. It does not offer "Rice/grain/soybean".
5. The unit dropdown offers only the 5 units.

Report what you actually observed. If the app couldn't be launched, say so.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat: add unit dropdown, salt pre-fill and starting-composition card

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Not in this plan (by design; see spec)

- **Transformation model** `n(t) = n₀ + A·ξ(t)`, with Monte Carlo bands and endpoint validation (spec §4). It gets its own plan after this one lands. Its first consumer is `compose()`'s sugars and `salt_pct` feeding the Monod twin's `S₀` and `salt_factor`.
- Recipe `salt_pct` feeding the safety rule engine (open decision 1).
- CIQUAL/French names and branded Open Food Facts items.
- Ingredients beyond the V3 list (for example mango or hibiscus). Each one is added by a new seed migration, never through a catch-all "Other" row.
- Per-ingredient density.
