# USDA Food Catalog — Search and Pick Any Food — Design

**Date:** 2026-09-23
**Status:** Approach A approved by Achille, 2026-09-23
**Builds on:** `2026-09-23-ingredient-nutrients-design.md` (the `ingredient_nutrients` table, the frozen FDC snapshot, `compose()` / `suggest_salt()`)

## Problem

The recipe form only offers the ~37 curated ingredients tagged for the batch's ferment type, and only 26 of them carry USDA nutrient data. Achille wants to pick **any** generic USDA food, and have its nutrients flow into the batch composition.

## Decisions (made with Achille)

| Question | Decision |
|---|---|
| Which foods | **SR Legacy + Foundation**: about 8k generic, lab-analysed foods. Branded foods are excluded (about 450k, label-level only, too big for the free DB tier). |
| Ferment-type rule | **Allow any USDA food, and tag it for next time.** Picking a food for a batch adds that batch's ferment type to the ingredient's `fermentation_systems`, so it shows up in that ferment's quick-pick list afterwards. |
| Role | **A role dropdown, defaulting to `base`**, shown when a USDA food is picked. The choice becomes the new ingredient's `default_role`. |
| Architecture | **A: local catalog, promote on pick.** Rejected: B (all 8k as `Ingredient` rows, which buries the curated list) and C (live FDC API at pick time, which means a runtime dependency, a key on Render, and rate limits). |

## Design

### Data

A new frozen snapshot, `src/fermenttrack/fdc_catalog_v1.csv.gz`, is built offline by `scripts/build_fdc_catalog.py` from FDC's public bulk CSV downloads (the SR Legacy and Foundation zips from https://fdc.nal.usda.gov/download-datasets; no API key needed).

- **Format:** a **wide** CSV, one row per food. Columns: `fdc_id, data_type, description, category`, then one column per `NUTRIENTS` code (the same 15 codes as `fermenttrack/nutrients.py`).
- **Units and missing values:** every nutrient value is in g per 100 g. An empty cell means FDC didn't report the value: unknown, never 0.
- **Which rows:** only `food.csv` rows whose `data_type` is `sr_legacy_food` or `foundation_food`. Foundation's sub-sample and market-acquisition rows are excluded.
- **Nutrient mapping:** from `food_nutrient.csv` (`nutrient_id`, `amount`) and `nutrient.csv` (`unit_name`). The rule is the same as `snapshot_rows`: take the first reported id from `NUTRIENTS[code]`, and convert units with `fdc_amount_to_grams`.
- **Frozen:** the file is frozen once migrated, like `fdc_nutrients_v1.csv`. It is gzip-written with `mtime=0` so rebuilds are byte-reproducible. Expected size is about 0.5 MB.

New tables (migration 0007):

```
fdc_foods             fdc_id INT PK, data_type TEXT, description TEXT, category TEXT NULL
fdc_food_nutrients    fdc_id INT FK→fdc_foods, nutrient TEXT, amount_per_100g FLOAT, PK(fdc_id, nutrient)
ingredients.fdc_id    INT NULL, unique index (created via op.create_index(unique=True), which works on SQLite and Postgres)
```

- `fdc_food_nutrients` is **long** format, with a row only where the snapshot cell is non-empty, so missing ≠ zero is preserved.
- Rows are loaded in chunks of 5,000 from the gz file.
- **Backfill:** the 26 curated ingredients get `fdc_id` from their existing `ingredient_nutrients.source_food_id`. Picking "Cabbage, raw" from the catalog then reuses curated "Cabbage" instead of creating a duplicate.

### Search: `GET /foods?q=<text>&limit=20`

- `q` has at least 2 characters and is split on whitespace.
- **Every** token must appear, case-insensitively, in `description`. For example, `raw cabbage` matches "Cabbage, raw".
- Results are ordered by description length, so shorter and more generic names come first, then alphabetically.
- `limit` defaults to 20, with a maximum of 50.
- Returns `[{fdc_id, description, data_type, category}]`.
- It uses portable `lower(description) LIKE` filters, which work on SQLite and Postgres. There is no pg_trgm.
- New module `routers/foods.py`.

### Pick: `POST /batches/{id}/ingredients` also accepts `fdc_id`

`BatchIngredientCreate` takes **exactly one** of `ingredient_id` or `fdc_id` (validated; 422 otherwise). The `fdc_id` path:

1. Load the `FdcFood`. Return 404 if it doesn't exist.
2. Find the `Ingredient` whose `fdc_id` matches:
   - **None:** create one with `name = description`, `default_role = payload.role or "base"`, `fermentation_systems = [culture.type]` and `is_active = True`. Copy the food's `fdc_food_nutrients` into `ingredient_nutrients` with `source="usda_fdc"`, `source_food_id=str(fdc_id)` and `source_version="fdc_catalog_v1"`.
   - **Exists but retired:** return 400, the same as the curated path.
   - **Exists and not tagged for `culture.type`:** append the tag. Reassign the list, because the JSON column doesn't track in-place mutation.
3. Continue exactly like the `ingredient_id` path: `role = payload.role or ingredient.default_role`, then insert the `BatchIngredient`.

Nothing downstream changes: composition, salt suggestion and preview all read `Ingredient` + `ingredient_nutrients` as before. The `ingredient_id` path keeps its strict ferment-type check. Curated quick picks stay tagged.

`# ponytail:` the check-then-create isn't race-safe. Two simultaneous first picks of the same food would hit the unique index, and the second request returns a 500. That's acceptable for a single-user app; catch `IntegrityError` and re-select if it's ever multi-user.

### Frontend (`Recipe` in `App.jsx`)

- The curated dropdown stays as the quick-pick list.
- Below it is a **"Search all USDA foods…"** input. It's debounced (about 250 ms, no dependency) and calls `/foods?q=`. Up to 20 results show as a clickable list, each with a small SR Legacy / Foundation label.
- Picking a result clears the dropdown selection and shows the chosen food plus a **role select** (base / flavoring / additive / starter, default `base`).
- Submitting sends `{fdc_id, role, quantity, unit}`.
- Units and the composition card are unchanged. The salt pre-fill still triggers only on curated **Salt**.
- After an add, the ingredient options are re-fetched so a newly created ingredient's name resolves in the recipe list and joins the quick picks.

### Testing

- **Snapshot sanity** (reading the real gz):
  - SR Legacy has more than 7,000 foods and Foundation more than 150.
  - Every `NUTRIENTS` column is present, and no amount is outside 0–100.
  - Anchor checks pass: "Salt, table" sodium is 38–39.5, and "Sugars, granulated" sucrose/sugars is ≥ 99.
  - Every curated `INGREDIENT_FDC_MAP` fdc_id exists in the catalog.
- **Pure build function:** a unit test on a synthetic tiny FDC CSV set covers data_type filtering, id precedence, mg→g conversion, and empty cells for unreported values.
- **Search endpoint:** multi-token match, the minimum-length 422, ordering, and the limit.
- **Pick by fdc_id:**
  - creates the ingredient with copied nutrients, the chosen role and the tag;
  - reuses the same food and tags a new ferment;
  - reuses the backfilled curated ingredient;
  - returns 404 for an unknown fdc_id and 422 for both or neither id.
  - The composition endpoint reflects the picked food's nutrients.
- **Migration 0007:** SQLite round-trip (upgrade, downgrade to 0006, upgrade), plus a Postgres check through the deployed API after the Render deploy. Docker is unavailable locally.
- **Browser:** search "mango", pick it for a kombucha batch as flavoring, and see it in the recipe, in the composition card, and in the kombucha quick picks.

### Out of scope

- Branded foods and CIQUAL / French names.
- Editing or merging ingredients.
- User-defined custom foods that aren't in USDA.
- Fuzzy or typo-tolerant search.
- Starch gaps (still Increment 2's problem).

### Outbound calls

The only one is a single download of the two public FDC bulk zips, from the same service Achille already approved. No key is needed, and no data is sent.
