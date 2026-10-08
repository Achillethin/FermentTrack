# Adding an ingredient

This is how an ingredient becomes usable by the forecast and the recommender. The recommender derives an ingredient's **tier** from what exists in the repository (`recommender.library.ingredient_tier(name, ferment_type)`); there is no hand-kept list to update. Each tier unlocks more. You can stop at any tier, and you can do the steps in separate PRs.

Design: [`specs/2026-10-07-fermentation-recommender-design.md`](superpowers/specs/2026-10-07-fermentation-recommender-design.md) § 12.

| tier | what you add | what it unlocks |
|---|---|---|
| **T0, catalogue** | an `Ingredient` row (seed data + migration) | can be logged on a batch. Recommender: Experimental operator (v) only, labelled "aroma effect unknown" |
| **T1, kinetics** | a USDA FDC food link (nutrients) | its sugars, protein and buffer move the pH, sugar and taste forecast, and so the time window |
| **T2, aroma** | an `AROMA_INGREDIENTS` entry with curated priors | its odorants and precursors enter the aroma forecast. Recommender: can serve aroma targets; can be swapped in by operator (ii) |
| **T3, recommender-ready** | a row in `ingredient_use_levels_v1.csv` | Experimental operator (i) can add it to recipes at a typical use level |

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
3. **Tests:**
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
4. **Tests:** copy `tests/test_migration_0018.py`.

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
   - If the ingredient is an alias of another (for example "Napa cabbage (salted)"), document the alias next to the entry.
5. **Tests** (`tests/test_aroma_data.py`, `tests/test_aroma_<type>.py`):
   - every entry key is a compound or a labelled precursor (an existing test);
   - every `AROMA_INGREDIENTS` key is a catalogue name or a documented alias (recommender R2 test);
   - a behavioural test: logging the ingredient at its typical share changes the expected series in the expected direction (for example carvone noticeable from day 0 with 0.5 % caraway).
6. **If the ingredient has no curated odorants yet**, leave it out of `AROMA_INGREDIENTS`. Don't add amino or hydroxycinnamic acids alone to make it look covered. Precedent: garlic, onion, radish, carrot and chilies stay "no aroma data yet" (`test_ingredient_pass_entries`).

## T3: recommender use level

1. Add a row to `src/fermenttrack/recommender/ingredient_use_levels_v1.csv` (frozen; changing it means `_v2`):

   ```
   ingredient,fermentation_type,role,share_median,share_lo,share_hi,source,notes
   Gochugaru,lacto_ferment,flavoring,0.025,0.01,0.04,<research file>:<source> Table n,mass share of the whole batch
   ```

   - `share_*` is the mass share of the **whole batch** (0.025 = 2.5 %).
   - `source` must be an opened source, the same rule as T2.
   - One row per ferment type it is used in.
2. **Tests** (`tests/test_recommender_library.py`):
   - every use-level row resolves to T2 for that type;
   - `share_lo ≤ share_median ≤ share_hi`;
   - the role matches the catalogue role.

## After any tier: rebuild the recommender grid

Changing `aroma_data.py`, `aroma_compounds_v1.csv`, `profiles.py`, the recipe CSVs or the use levels makes the precomputed grid stale. `tests/test_recommender_grid.py::test_grid_is_current` fails with the command to run:

```bash
python scripts/build_recommender_grid.py --workers 4
```

Commit the rebuilt `recommender_grid_v1.npz` and its manifest **in the same PR** as the change. Approved community recipes are re-forecast automatically at the next startup.

## Checklist

- [ ] T0: `INGREDIENT_SEED_DATA_Vn`, migration, migration test, seed test
- [ ] T1: `INGREDIENT_FDC_IDS_Vn`, migration copying nutrients, migration test
- [ ] T2: research table with opened sources, curation spec § 6 rows, `AROMA_INGREDIENTS` entry under the catalogue name, behavioural test
- [ ] T3: `ingredient_use_levels` row(s) with a source
- [ ] grid rebuilt and committed; `pytest` green
- [ ] README or spec updated if behaviour visible to users changed
