# Adding an ingredient

This is how an ingredient becomes usable by the forecast and the recommender. The recommender derives an ingredient's **tier** from what exists in the repository (`recommender.library.ingredient_tier(name, ferment_type)`); there is no list of tiers to keep up to date. A new versioned seed or FDC list does have to be registered in the recommender's code (T0 and T1 below). Each tier unlocks more. You can stop at any tier, and you can do the steps in separate PRs.

Design: [`specs/2026-10-07-fermentation-recommender-design.md`](superpowers/specs/2026-10-07-fermentation-recommender-design.md) § 12.

| tier | what you add | what it unlocks |
|---|---|---|
| **T0, catalogue** | an `Ingredient` row (seed data + migration) | can be logged on a batch. Recommender: Experimental operator (v) only, labelled "aroma effect unknown" (salted or acidified types; never a staple) |
| **T1, kinetics** | a USDA FDC food link (nutrients) | its sugars, protein and buffer move the pH, sugar and taste forecast, and so the time window |
| **T2, aroma** | an `AROMA_INGREDIENTS` entry with curated priors | its odorants and precursors enter the aroma forecast. Recommender: can serve aroma targets; can be swapped in by operator (ii) when its catalogue row has the same role and is tagged for the parent's type and for every type the replaced ingredient is tagged for |
| **T3, recommender-ready** | a row in `ingredient_use_levels_v1.csv` | Experimental operator (i) can add it to recipes at a typical use level (rows with role `flavoring` only) |

**How `library.ingredient_tier` decides:**

| returns | when |
|---|---|
| −1 | the name is not a live catalogue name: a `new` ingredient, a retired row such as `Fish`, or an aroma alias such as `Napa cabbage (salted)` |
| 0 | a live catalogue name (every `INGREDIENT_SEED_DATA*` list registered in `library._SEEDS`, minus `RETIRED_V3`) |
| 1 | also has an FDC link (`INGREDIENT_FDC_MAP` or `INGREDIENT_FDC_IDS_V4`, registered in `library._FDC_MAPPED`) |
| 2 | has an `AROMA_INGREDIENTS` entry. An FDC link is **not** required: `Black tea leaves` is T2 without one |
| 3 | has an `AROMA_INGREDIENTS` entry **and** a use-level row for that ferment type. A use-level row without aroma data leaves the ingredient at its lower tier |

Only T3 depends on the ferment type. These tests pin the rules, in `tests/test_recommender_library.py`:
- `test_ingredient_tier`;
- `test_t3_needs_a_use_level_row_for_that_type_and_aroma_data`;
- `test_ingredients_resolve_to_the_catalogue`: a library recipe's row is T0 or above exactly when it isn't marked `new`, and every core row of an active recipe is.

Users can also pick any USDA food directly from the batch recipe editor (`GET /foods?q=`). That creates an ingredient on the fly at T1, without a seed row. This guide is for **curated** ingredients that ship with the app.

---

## T0: catalogue row

1. **`src/fermenttrack/seed_data.py`:** add a new versioned list. Don't edit an existing list, because migrations have already read it.

   ```python
   INGREDIENT_SEED_DATA_V5: list[tuple[str, str, list[str]]] = [
       ("Daikon radish", "base", ["lacto_ferment"]),
       ("Gochugaru", "flavoring", ["lacto_ferment"]),
   ]
   ```

   - **Name:** a plain catalogue-style name ("Asian pear", not "pear, asian, raw"). It is the key used everywhere below, so pick it once.
   - **Role:** one of `base`, `starter`, `flavoring` or `additive`.
   - **Systems:** the profile keys in `prediction/profiles.py` (`kombucha`, `sourdough`, `koji`, `cheese`, `kefir`, `lacto_ferment`, `miso`, `garum`, `vinegar`).
2. **Migration:** add `alembic/versions/00NN_<topic>_ingredients.py` that bulk-inserts the list. Copy `0017_aroma_ingredients.py`; its downgrade deletes by name and intentionally fails if a batch already uses the row.
3. **Register the list with the recommender:** add it to `_SEEDS` in `src/fermenttrack/recommender/library.py`. `library.CATALOGUE_NAMES` (tier T0) and `library.CATALOGUE` (role and systems, which operator (ii) reads) are built from that tuple only. Until it is added, the ingredient is −1 to the recommender.
4. **Tests:**
   - copy `tests/test_migration_0017.py` (upgrade inserts, downgrade removes);
   - extend `tests/test_seed_data.py` (unique names, valid roles and systems).

## T1: nutrients (FDC link)

1. Find the food in the bundled USDA catalogue (`fdc_catalog_v1`, loaded by migration 0007). Prefer SR Legacy or Foundation, raw.
2. Add the food id to a versioned map in `seed_data.py`, with the FDC description as a comment:

   ```python
   INGREDIENT_FDC_IDS_V5: dict[str, int] = {
       "Daikon radish": 123456,  # placeholder id; the comment is the exact FDC description
   }
   ```

3. Add a migration that copies the nutrients exactly as a USDA-search pick does. Copy `0018_aroma_ingredient_nutrients.py`; it only sets `ingredients.fdc_id` when no other ingredient holds that food.
4. **Register the map with the recommender:**
   - add it to `_FDC_MAPPED` in `src/fermenttrack/recommender/library.py` (tier T1);
   - add it to `per_100g_table()` in `src/fermenttrack/recommender/run.py`, which today reads the `fdc_nutrients_v1` snapshot and then `INGREDIENT_FDC_IDS_V4`. Without that, the grid and the live recommender forecasts run the ingredient with no nutrients.
5. **Tests:** copy `tests/test_migration_0018.py`.

Ingredients with no FDC entry (starter cultures, dry tea leaves, calcium chloride) stay at T0 and show as "unmapped" in composition. That is intended.

## T2: aroma (`AROMA_INGREDIENTS`)

This is the expensive tier: it needs **sourced** data. Follow the aroma research rules in [`research/aroma/BRIEF.md`](superpowers/research/aroma/BRIEF.md) (every number from an opened source; no reconstructed citations; units in µg/kg; spreads as priors). The lacto-ferment round's brief, [`BRIEF-lacto-ingredients.md`](superpowers/research/aroma/BRIEF-lacto-ingredients.md) on branch `feat/aroma-lacto-ingredients`, is the template for an ingredient research round.

1. **Research table:** the round's file in `docs/superpowers/research/aroma/` lists, per ingredient, its character odorants (µg/kg fresh weight), precursors (glucosinolates, S-alk(en)yl-cysteine sulfoxides, free amino acids, hydroxycinnamic acids, glycosides), what happens to them during fermentation, and a typical use level.
2. **Curation:**
   - add the ingredient's row to the aroma curation spec § 6.2, and its precursors to § 6.1 if any;
   - mark every estimate `est. (<increment>)` with the reasoning, as § 10.8 does.
3. **Compounds:** reuse keys from `src/fermenttrack/prediction/aroma_compounds_v1.csv`. A new odorant needs a catalogue row, which means a `_v2` CSV rebuilt by `scripts/build_aroma_compounds.py`, plus evidence cells per ferment type. Never add a compound key only to `AROMA_INGREDIENTS`.
4. **`src/fermenttrack/prediction/aroma_data.py`:** add the entry under the **catalogue name**:

   ```python
   AROMA_INGREDIENTS["Daikon radish"] = {
       "hexanal": Prior(20.0, 5.0, 80.0),        # <research file>:<source> Table n
       "@gluconapin": Prior(0.1, 0.02, 0.5),     # precursor pools use "@" and PRECURSOR_LABEL
   }
   ```

   - Values are per kg of the logged ingredient.
   - Precursor keys start with `@` and need a `PRECURSOR_LABEL` entry.
   - If the ingredient is an alias of another (for example "Napa cabbage (salted)"), document the alias next to the entry, and add the key, with a comment, to `ALIASES` in `src/fermenttrack/recommender/library.py`.
5. **Tests:**
   - `tests/test_aroma_data.py::test_ingredient_entries_are_compounds_or_labelled_precursors`: every entry key is a compound or a labelled precursor (an existing test);
   - `tests/test_recommender_library.py::test_aroma_ingredient_keys_are_catalogue_names_or_aliases`: every `AROMA_INGREDIENTS` key is a catalogue name or is in `library.ALIASES`, and no alias is a catalogue name;
   - a behavioural test in `tests/test_aroma_<type>.py`: logging the ingredient at its typical share changes the expected series in the expected direction (for example carvone noticeable from day 0 with 0.5 % caraway).
6. **If the ingredient has no curated odorants yet**, leave it out of `AROMA_INGREDIENTS`. Don't add amino or hydroxycinnamic acids alone to make it look covered. Precedent: garlic, onion, radish, carrot and chilies stay "no aroma data yet" (`test_ingredient_pass_entries`).

## T3: recommender use level

1. Add a row to `src/fermenttrack/recommender/ingredient_use_levels_v1.csv` (frozen; changing it means `_v2`). Lines starting with `#` are comments.

   ```
   ingredient,fermentation_type,role,share_median,share_lo,share_hi,source,notes
   Gochugaru,lacto_ferment,flavoring,0.025,0.01,0.04,<research file>:<source> Table n,mass share of the whole batch
   ```

   - `share_*` is the mass share of the **whole batch** (0.025 = 2.5 %).
   - `source` must be an opened source, the same rule as T2.
   - One row per ferment type it is used in.
   - Operator (i) adds only rows whose role is `flavoring`, at `share_median`. A `base` row still makes the ingredient T3.
2. **Tests** (`tests/test_recommender_library.py`):
   - `test_every_use_level_row_resolves_to_t2_and_is_sourced` checks that each row:
     - is tier 3 for its type (aroma data and the row);
     - has a type that is a profile key;
     - has 0 < `share_lo` ≤ `share_median` ≤ `share_hi` < 1;
     - has the catalogue role and a non-empty `source`;
     - is the only row for its ingredient and type.
   - `test_use_levels_are_bootstrapped_from_active_recipe_rows_only` pins the 16 v1 rows to their bootstrap from the active library recipes. The first rows from a research round must change this test, or go into a `_v2` file, with `library.USE_LEVELS_CSV` and `grid.INPUTS` pointing at it.
   - `test_t3_needs_a_use_level_row_for_that_type_and_aroma_data` checks that a row without aroma data does not make an ingredient T3.

## After any tier: rebuild the recommender grid

These grid inputs are hashed in its manifest (`grid.INPUTS`):
- `prediction/profiles.py`;
- `prediction/aroma_compounds_v1.csv`;
- `prediction/aroma_data.py`;
- `recommender/recipes_v1.csv` and `recommender/recipe_ingredients_v1.csv`;
- `recommender/ingredient_use_levels_v1.csv`.

Changing any of them makes the grid stale, and `tests/test_recommender_grid.py::test_grid_is_current` fails with:

```
grid is stale (<what changed>): run `python scripts/build_recommender_grid.py --workers 4`
```

The same test also fails when the set of active recipes or the operator catalogue that the code derives no longer matches the grid's. That happens, for example, when a new T2 ingredient opens a new swap, or a new T3 row a new add.

**Not hashed:** `seed_data.py` and the engine's code. If your change alters the nutrients of an ingredient that a library recipe already uses (T1), rebuild anyway. `test_a_rebuilt_entry_matches_the_committed_one` re-solves one entry per ferment type and two operator entries, so it catches such a change only when it touches those entries.

```bash
python scripts/build_recommender_grid.py --workers 4
```

The full build took about 8.5 minutes on 4 workers (188 entries, 177,559 bytes; the budget, checked by `test_grid_size`, is 5 MB). Commit the rebuilt `recommender_grid_v1.npz` and its manifest **in the same PR** as the change. Approved community recipes are re-forecast automatically at the next startup, because the grid version (the npz's hash) changed.

## Checklist

- [ ] T0: `INGREDIENT_SEED_DATA_Vn`, migration, migration test, seed test, the list added to `library._SEEDS`
- [ ] T1: `INGREDIENT_FDC_IDS_Vn`, migration copying nutrients, migration test, the map added to `library._FDC_MAPPED` and `run.per_100g_table`
- [ ] T2: research table with opened sources, curation spec § 6 rows, `AROMA_INGREDIENTS` entry under the catalogue name (an alias also in `library.ALIASES`), behavioural test
- [ ] T3: `ingredient_use_levels` row(s) with a source; the bootstrap test adapted
- [ ] grid rebuilt and committed; `pytest` green
- [ ] README or spec updated if behaviour visible to users changed
