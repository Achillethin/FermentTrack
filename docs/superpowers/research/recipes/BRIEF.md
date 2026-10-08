# Recipe library curation — brief for the research agent

**Project:** FermentTrack, a fermentation tracker. Its forecast is a Bayesian ensemble of mechanistic kinetic models covering pH, sugars, acids, organisms, four tastes and 16 aroma series (`src/fermenttrack/prediction/`). The forecast only runs forwards: recipe + conditions + time → prediction.

**What this library is for:** a fermentation recommender. The user gives a few ingredients and/or a few target aromas. The recommender returns structured recipes with a fermentation-time window in two modes:

- **Proven:** a recipe from this library, kept inside its documented envelope (temperature, salt, time).
- **Experimental:** a documented departure from a library recipe.

The library is the "proven" half. Every row must be traceable to a source that someone actually opened.

**The model follows the aroma compound catalogue:**

| aroma catalogue | recipe library |
|---|---|
| `docs/superpowers/research/aroma/BRIEF.md` (shared rules) | this file |
| research tables `research/aroma/01..05-*.md` | `research/recipes/01-recipes.md` |
| curation spec `specs/2026-10-05-aroma-curation.md` | `specs/<date>-recipe-curation.md` (written after this round) |
| frozen `src/fermenttrack/prediction/aroma_compounds_v1.csv`, built by `scripts/build_aroma_compounds.py` | frozen `recipes_v1.csv` and `recipe_ingredients_v1.csv`, built by a script from the curation spec |
| `Prior(median, lo, hi)` per value | `*_median`, `*_lo`, `*_hi` columns per value |
| evidence tiers: calibrated / reported / plausible / drop | provenance tiers (below) |
| `status`: active / inactive / drop | `status`: active / draft / drop |

This round produces **drafts only**: the research file and two draft CSVs in this folder. Do not write to `src/`. Do not create migrations. Do not commit.

## Read first (repository, read-only)

- `src/fermenttrack/prediction/profiles.py`: the 10 profile keys (`kombucha`, `sourdough`, `koji`, `cheese`, `kefir`, `lacto_ferment`, `miso`, `garum`, `vinegar`, `generic`). Read each profile's typical temperature, range, horizon and typical recipe, because every recipe's `fermentation_type` must be one of these keys. Note that `cheese` is the curd/acidification stage only, with no ripening, and that `kefir` is milk kefir.
- `src/fermenttrack/seed_data.py`: the ingredient catalogue names. **Reuse these names exactly** (for example `Napa cabbage`, `Cabbage`, `Garlic`, `Black tea leaves`, `Cane sugar`, `SCOBY / starter liquid`, `White wine`, `Kefir grains`, `Salt`, `Water`). Use a plain catalogue-style name for an ingredient that isn't there, and mark it `new`.
- `src/fermenttrack/prediction/aroma_data.py` → `AROMA_INGREDIENTS` and `DEFAULT_INGREDIENTS`: which ingredients the aroma model already knows.
- `src/fermenttrack/routers/sourdough.py` (catalogue styles, which already carry `sources`): **reuse those styles as the sourdough rows** (cite their existing sources) instead of researching new sourdough recipes. Add at most two.
- `src/fermenttrack/safety/risk_rules.yaml`: the rules a recipe will be checked against (salt 2–10 % for vegetables, pH 4.6, temperature limits, koji conditions).

## Rules (non-negotiable)

1. **Every number must come from a source you actually opened**, either the full text or a page that states the number. Record the full citation (authors or organisation, year, title, publisher or journal, URL or DOI) and *where* in the source it appears (table, section, page, recipe step).
2. **Never fabricate a citation or reconstruct one from memory.** If you remember a recipe but can't open a source for it, put it under "Unverified leads".
3. **Prefer tested sources, in this order:**
   - **institutional_tested:** USDA National Center for Home Food Preservation, university extension services, FAO, Codex standards, national food-safety agencies;
   - **peer_reviewed:** papers that state the recipe and conditions they fermented under;
   - **traditional_documented:** a reputable published description of a traditional recipe, such as a producer association or an encyclopaedic source with references.

   Blogs and forums are only leads, never data.
4. **Copy facts, not prose.** Ingredients, quantities, temperatures, times, salt and pH targets are facts; method text is someone's expression. Summarise each method in one line of your own words. Never paste recipe instructions verbatim.
5. **Normalise units:**
   - ingredient amounts in **g per kg of total starting batch** (including water or brine, excluding a starter culture only when the source scales it separately; say which);
   - salt as **% w/w of the total batch** (convert brine % as well, and show the derivation);
   - temperatures in °C;
   - duration in **hours** (also give days in notes where natural).

   Show every derivation in the research file.
6. **Report the spread, not one value.** If the source gives a range, use it as lo–hi with a midpoint median. If several sources disagree, take the median across them and the range covering them. A single point value gets lo = hi = median, flagged `point` in notes.
7. **Public sources only.** Search only on food, ingredient and organism names. **Never put any personal identifier (email address, name, account id) into a web request**, and skip services that ask for one. Never paste repository code into any web request.
8. Write only to the three output files named below. The work is split across parallel agents by group (`<group>` = `lacto-kombucha`, `dairy-vinegar-sourdough` or `koji-miso-garum`). Each agent writes `01-<group>.md`, `recipes_draft_v0.<group>.csv` and `recipe_ingredients_draft_v0.<group>.csv`, and the orchestrator merges them.
9. **Write as you go.** As soon as a recipe is finished, append it to all three of your files. Never hold everything until the end. If a recipe still isn't sourced after about 15 opened pages, record it under "Unverified leads" and move on.

## Scope (about 25–30 recipes)

Aim for 2–4 recipes per type, choosing classic, widely made ones over exotic ones:

- **lacto_ferment:** dry-salted sauerkraut; napa-cabbage kimchi; brined dill cucumber pickles; one of brined carrots, radish or a fermented chili mash (hot sauce).
- **kombucha:** black-tea kombucha (first ferment); a green-tea variant; a flavoured second ferment (for example ginger or fruit), if a tested source exists.
- **kefir:** milk kefir from grains (and a backslopped or cultured variant only if a source differs materially).
- **vinegar:** wine vinegar (surface or Orléans method); cider vinegar.
- **cheese** (acidification or curd stage only): a lactic fresh cheese (fromage-blanc or chèvre-style curd) or a cultured-milk curd. Ripening is out of scope.
- **koji:** rice koji; barley koji (if sourced).
- **miso:** a short white (shiro) miso; a long red or barley miso.
- **garum:** traditional fish and salt; a koji-based garum or fish sauce (if a source states the ratios).
- **sourdough:** the existing catalogue styles, mapped (see "Read first").

## Outputs (in this folder)

### 1. `01-recipes.md`

Contents:
- one section per recipe: the source citations with locators, every derivation, a one-line method in your own words, and anything the CSV can't hold;
- **D. Envelope check:** for each recipe, its temperature, duration and salt next to the profile's typical values and range from `profiles.py`, flagging anything outside the profile's range;
- **E. Unverified leads;**
- **F. Ingredient gaps:** every ingredient used by a recipe that is (a) not in the catalogue, or (b) in the catalogue but not in `AROMA_INGREDIENTS`, ranked by how many recipes use it. This list feeds the ingredient-expansion work (`feat/aroma-lacto-ingredients`).

### 2. `recipes_draft_v0.csv` (one row per recipe)

```
key,name,fermentation_type,style_region,provenance,temp_c_median,temp_c_lo,temp_c_hi,duration_h_median,duration_h_lo,duration_h_hi,salt_pct_median,salt_pct_lo,salt_pct_hi,sugar_g_per_kg_median,sugar_g_per_kg_lo,sugar_g_per_kg_hi,aerobic,method,stages,safety_targets,reported_aromas,sources,status,notes
```

- `key`: snake_case and unique, for example `sauerkraut_dry_salted`.
- `provenance`: one of `institutional_tested`, `peer_reviewed`, `traditional_documented`.
- `aerobic`: `yes` or `no`.
- `method`: a short tag, for example `dry_salted`, `brine`, `surface_culture`, `solid_state`.
- `stages`: for example `1F 168-240 h; 2F 48-96 h`, or empty.
- `safety_targets`: the source's own targets, for example `pH<=4.6 by 72 h; salt>=2%`, or empty.
- `reported_aromas`: only aromas the source itself states, mapped to the 16 series (fruity, floral, green, buttery, malty, sulfurous, pungent, vinegary, cheesy, solvent, mushroom, caramel, roasty, fishy, phenolic, herbal) and the four tastes (sour, sweet, umami, alcohol), semicolon-separated, or empty.
- `sources`: citation keys defined in `01-recipes.md`, for example `NCHFP-sauerkraut`.
- `status`: `active` if every number is sourced, otherwise `draft`.
- Leave a numeric triple empty when it doesn't apply (for example sugar for sauerkraut).

### 3. `recipe_ingredients_draft_v0.csv` (one row per recipe × ingredient)

```
recipe_key,ingredient,catalogue_status,role,g_per_kg_median,g_per_kg_lo,g_per_kg_hi,required,source,notes
```

- `catalogue_status`: `existing`, `existing_no_aroma`, or `new`.
- `role`: one of `base`, `starter`, `flavoring`, `additive`, `liquid`.
- `required`: `core` or `optional`.
- `source`: citation key plus locator.
- For each recipe, the `g_per_kg_median` values should sum to about 1000 (± 5 %). If they don't, explain why in notes.

## Final reply

A summary of at most 250 words covering:
- counts by type and by provenance tier;
- how many rows are `active` and how many `draft`;
- the strongest sources;
- envelope conflicts with `profiles.py`;
- the top five ingredient gaps.
