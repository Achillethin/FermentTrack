# Recipe curation (R0): the library behind the recommender's Proven section

**Date:** 2026-10-07
**Status:** DRAFT, for owner review. Owner decisions Q31–Q32 (2026-10-08) are applied.
- 17 recipes are curated in § 3; 13 are active.
- 10 sourdough catalogue mappings are in § 3a; 7 are active and hand off to the sourdough planner.
**Design:** `2026-10-07-fermentation-recommender-design.md` § 4.
**Research:** `docs/superpowers/research/recipes/` holds `BRIEF.md`, the `01-<group>.md` files with full citations, locators and derivations, and the `*_draft_v0.<group>.csv` files.

## 1. How to read this

The tables in § 3 are the input to `scripts/build_recipes.py`, which writes the frozen `src/fermenttrack/recommender/recipes_v1.csv` and `recipe_ingredients_v1.csv`. The drafts are evidence; **this file is the decision**.

Per recipe, the curation applies these rules, in order:

1. **Every value is sourced or derived with the derivation shown** (in the research file). Missing value → **draft**; draft recipes are never served.
2. **Ingredient names resolve to the catalogue.** A `new` ingredient keeps the recipe **draft** until it exists at tier T0 or above (`docs/ADDING_AN_INGREDIENT.md`).
3. **Composite ingredients are split into what the engine reads.** Rice koji, for example, becomes raw rice plus absorbed water, at the source's mass ratio, consistent with the engine's miso and koji defaults.
4. **Q25:** a single-value duration *d* or temperature *T* becomes [0.7 *d*, 1.3 *d*] and [*T* − 3, *T* + 3], with `envelope_basis = widened_single_value`. The temperature is clipped to the profile's `temp_range`, unless the source itself is outside it; then Q26 applies and the card keeps the source's widened range.
5. **Q26:** the build derives `model_scope` (`in_range`, `temp_outside_profile`, `beyond_horizon`). The card shows the source's numbers; the model only claims in range.
6. **Gate check (design § 7):** the served (median) recipe must pass at every temperature the card can show.

## 2. Summary

| group | recipes | after curation: active | draft |
|---|---|---|---|
| lacto_ferment | 4 | 2 | 2 |
| kombucha | 2 | 2 | 0 |
| koji | 2 | 1 | 1 |
| miso | 2 | 2 | 0 |
| garum | 2 | 1 | 1 |
| kefir | 2 | 2 | 0 |
| cheese | 1 | 1 | 0 |
| vinegar | 2 | 2 | 0 |
| sourdough | 10 catalogue mappings | 7 (planner hand-off, § 3a) | 3 excluded |

**Totals:** 20 servable recipes (13 curated + 7 sourdough). The curators marked 15 of the 17 non-sourdough recipes active. Curation demotes barley koji and budu (§ 4) and keeps sand lance active through the Q32 stand-in, leaving 13 active. The source tiers of the 13 are 5 `institutional_tested` (sauerkraut, shiro and red miso, both vinegars), 7 `peer_reviewed` (kimchi, both kombuchas, rice koji, both kefirs, sand-lance fish sauce) and 1 `traditional_documented` (lactic cheese). The 7 sourdough styles carry their catalogue's peer-reviewed sources. Kimchi's time window comes from institutional (extension) guidance.

## 3. Curated recipes

Abbreviations: T = temperature; d = duration in hours; salt = % w/w of the total batch; prov = provenance (`inst` = institutional_tested, `peer` = peer_reviewed); basis = envelope basis (`sourced` or `widened`).

| key | type | prov | T °C med (lo–hi) | d h med (lo–hi) | salt % med (lo–hi) | basis | model_scope | status | curation note |
|---|---|---|---|---|---|---|---|---|---|
| `sauerkraut_dry_salted` | lacto_ferment | inst | 22.5 (21.1–23.9) | 588 (504–672) | 2.11 (1.88–2.34) | sourced | in_range | **active** | NCHFP's ingredient list and procedure disagree on the salt; the range covers both. The served median of 2.11 % passes the gate. The lo edge of 1.88 % is never served. Cooler option (60–65 °F, 5–6 weeks) noted for a v2 row |
| `napa_kimchi_room_temp` | lacto_ferment | peer (formula) + inst (time) | 20.0 (20–20) | 36 (24–48) | 3.5 (2.0–5.0) | T widened → 17–23; d sourced | in_range | **active** | Formula from Jang 2024; the 1–2 day room-temperature window and pH ≤ 4.6 come from CSU/NCSU extension. **Fix before build:** "red pepper powder" is booked as `Chilies` (fresh). It should become the new T0 ingredient `Gochugaru` (dried), which the lacto-ingredients round already lists. Until then, keep `Chilies` and add the note "dried powder booked as fresh chili: dry matter understated several-fold", with mass unchanged. `Salted shrimp` and `Glutinous rice paste` are `new` and become `optional` (1.5 % and 0.8 % of the batch), so the recipe can stay active. The fridge stage after day 2 is not sourced in the draft, so `temp_schedule` stays empty (follow-up) |
| `dill_cucumber_pickles_brined` | lacto_ferment | inst | 22.5 (21.1–23.9) | 588 (504–672) | 3.67 (point) | sourced | in_range | draft | The dill mass is given only as volume or "heads". `Vinegar (5 %)` is `new`. Needs a dill mass source and the T0 vinegar row |
| `carrot_sticks_wet_brined` | lacto_ferment | inst | 21.1 (20.0–22.2) | 588 (504–672) | 3.65 (1.86–5.38), brine only | sourced | in_range | draft | The source gives brine strength but no carrot-to-brine mass. The lo brine salt of 1.86 % would fail the gate; once a mass ratio is sourced, the gate applies to the total batch |
| `black_tea_kombucha_1f` | kombucha | peer | 30 → 30 (27–33) | 336 → 336 (235–437) | — | widened | **temp_outside_profile** (profile 20–28) | **active** | Cohen 2023's starter-tea preparation (8 g/L tea, 100 g sugar per L, 10 % starter). The card shows 30 °C; the grid evaluates at 28 °C (nearest in range). Sugar is 82.8 g/kg against the profile's 70 |
| `green_tea_kombucha_variant` | kombucha | peer | 25 (22–28) | 240 (168–312) | — | widened | in_range | **active** | Dartora 2023, high-green treatment (79.8 : 20.2 green : black). Rename to `green_dominant_kombucha` |
| `rice_koji_steamed_rice` | koji | peer (incubation) + inst (envelope, ratio) | 30 (27–40) | 45 (42–48) | — | sourced | **temp_outside_profile** (profile 28–35) | **active** | The gate (KOJI-001) caps the served and slider temperature at 33 °C. The recipe includes `Koji spores (A. oryzae)` (the certified-strain exception), so 33–35 °C can show with "use certified tane-koji". 27 °C sits above the 25 °C minimum (KOJI-002). Water uptake of 2 kg per 15 kg rice is derived from Kagawa's 15 kg rice → 17 kg koji |
| `barley_koji_single_grain` | koji | inst | 30 (27–40) | 45 (42–48) | — | sourced | temp_outside_profile | **draft** (curator: active) | Every number is inherited from rice koji, and the spore dose is missing (empty in the draft). The engine soaks dry grain itself (`min_water_fraction`), but Start batch needs a spore dose. Needs a barley-specific source, or the owner accepting the rice spore dose as "est." |
| `shiro_miso_kagawa_sweet` | miso | inst | 27.5 (25–30) | 480 (240–720) | 6.1 (5.5–6.6) | sourced | in_range | **active** | **Fix before build:** the draft books rice koji (469.6 g/kg) as `White rice`. Split it at Kagawa's 15 : 17 rice-to-koji ratio into `White rice` 414.4 g/kg + `Water` 55.2 g/kg (water total becomes 110.4 g/kg), and change the role to `base`. This matches the profile's koji-ratio reference (`DEFAULT_INGREDIENTS["miso"]`) |
| `red_rice_miso_kagawa_long` | miso | inst | 27.5 (25–30) | 6540 (4320–8760) | 11.9 (10.7–13.0) | sourced | **beyond_horizon** (4320 h) | **active** | Same koji split: rice koji 311.9 → `White rice` 275.2 + `Water` 36.7 g/kg. The aroma estimate covers the first 180 days only; the window comes from the source |
| `budu_traditional_anchovy_fish_sauce` | garum | peer + Codex | — (room temperature, not stated) | 10950 (8760–13140) | 21.6 (20.0–23.1) | sourced | beyond_horizon | **draft** (curator: active) | Q26: a missing temperature means draft. Needs a numeric fermentation temperature from an opened source (for example a budu study that logs ambient) |
| `pacific_sand_lance_rice_koji_fish_sauce` | garum | peer | 18 (18–20) | 7200 (point → widened 5040–9360) | 12.0 (8.3–15.4) | d widened | temp_outside_profile (18 < 20); beyond_horizon | **active** (Q32) | **Q32:** the fish is booked as `Anchovies` (800 g/kg), with the card label "stand-in species: recipe uses Pacific sand lance". The garum route treats small whole fish alike. The rice koji (80 g/kg) gets the same raw-rice + water split as miso: `White rice` 70.6 + `Water` 9.4 g/kg. The 20 °C koji pretreatment for 24–72 h becomes `temp_schedule = 0:20;48:18`. The grid evaluates the main stage at 20 °C |
| `milk_kefir_grains_5pct_24h` | kefir | peer | 25 (22–25) | 24 (17–31) | — | widened (single values; T clipped to the profile's 25 °C top) | in_range | **active** | Youn 2022: 50 g grains per L milk. 4.8 % grains matches the profile's 5 % starter assumption |
| `milk_kefir_grains_10pct_extended` | kefir | peer | 25 (22–25) | 48 (24–72) | — | T widened; d sourced | **beyond_horizon** (48 h) | **active** | Kim 2016: 10 % grains, 24–72 h. Table 1 pH goes from 4.05 at 24 h to 3.64 at 72 h, a calibration point for R4. Peak and score are computed only to 48 h; the window comes from the source |
| `lactic_fresh_cheese_curd` | cheese | traditional_documented | 21.5 (21–22) | 15.5 (10–21) | — (salt 1.0–1.3 % added after draining; out of scope) | sourced | **temp_outside_profile** (profile 28–32) | **active** | Academy of Cheese lactic guide: starter 0.5–0.8 %, rennet 5–10 mL/100 L, ripen 2–3 h to pH 6.3–6.5, set to pH 4.60 in 8–18 h. The grid evaluates at 28 °C, which will predict a faster set than the source, so the card window comes from the source alone (Q26). Strongest engine-track item: lactic-set styles at 18–22 °C sit outside the cheese profile |
| `wine_orleans_surface` | vinegar | inst | 25 (20–30) | 588 (504–672) | — | sourced | temp_outside_profile (lo 20 < 24) | **active** | AWRI 2022: final mix 25 % live culture + 75 % wine and water at ~8 % v/v, about 6 % v/v alcohol, held at 20–30 °C. NC State: 3–4 weeks. The 25 % starter is above the profile's 0.15; it is kept, because the inoculum scales with it. `Red wine` stands for any base wine (`White wine` is the other T2 base). Card: "check ≥ 5 % acetic acid before using to pickle" (NC State, UC Davis) |
| `cider_vinegar_surface` | vinegar | inst | **21.1 (15.6–26.7)** (curator: 23.9 (15.6–35.6)) | 588 (504–672) | — | sourced | temp_outside_profile (below 24) | **active** | Penn State / Ohio State leaflet: 60–80 °F, 3–4 weeks. **Curation change:** the cider-specific range takes precedence over NC State's general 68–96 °F, so the envelope becomes 15.6–26.7 °C with median 21.1 °C. The grid evaluates at 24 °C. Card: "acidity varies; do not use for canning or room-temperature storage unless verified" (Penn State) |

**Ingredient masses:** as in the draft CSVs, except the fixes above, which `build_recipes.py` applies from this table's notes. Every recipe's ingredient medians sum to 1000 g/kg ± 5 %; the build asserts it.

## 3a. Sourdough: planner hand-off (Q31)

The sourdough rows are **mapped from the existing catalogue** (`prediction/sourdough.py` `STYLES`, with its cited sources), not newly researched. Two things set sourdough apart:
- The catalogue styles are **levain or preferment builds**, not breads. Dough, salt, bulk and proof are planner inputs.
- Sourdough already has its own planner and engine (`POST /sourdough/plan`, `bake.py`, `sourdough-v1`), which forecasts levain peak, bulk and proof.

**Q31: sourdough cards hand off to the planner.**
- **Ingredients and aromas:** a sourdough card is matched and scored like any other. The grid runs the levain build through the sourdough engine (`bake.py`), which already returns aroma series.
- **Start:** opens `/sourdough/plan` pre-filled with the style, and optionally the user's culture. It does not use `POST /batches/from-recommendation`. The planner creates the batch, and the recommendation link is written when the planner's batch is saved.
- **Window:** the planner's forecast (levain peak → bulk → proof), not § 6 of the design.
- **Experimental:** sourdough variants are limited to operators (ii) flour swap and (iii) temperature.

| key | sources | T °C | build h | status (curated) | note |
|---|---|---|---|---|---|
| `san_francisco` | Kline 1971; Gänzle 1998 | 27 | 8 | active | — |
| `rye_sour` | Brandt 2004 | 28 | 16 | active | — |
| `type_ii` | Gänzle & Vogel 2003 | 37 | 18 | active | temp_outside_profile (22–30): the card shows 37 °C, and the grid evaluates at 30 °C |
| `home_starter` | Landis 2021 | 24 | planner | active | timing from the planner |
| `levain_liquide`, `levain_dur` | Minervini 2014 | 26, 24 | planner | active | timing from the planner |
| `lievito_madre` | Carbonetto 2020 | 27 | planner | active | timing from the planner |
| `type_iii` | De Vuyst 2005 | 26 | — | **excluded** | dried powder, no dough formula; `Dried sourdough powder` is `new` |
| `poolish`, `biga` | none (catalogue has no source) | 20, 18 | 14, 18 | **excluded** | commercial-yeast preferments, not sourdough; `Instant yeast` is `new` |

## 4. Changes from the curators' status

| key | curator | curated | why |
|---|---|---|---|
| `barley_koji_single_grain` | active | draft | spore dose missing; envelope inherited, not barley-specific |
| `budu_traditional_anchovy_fish_sauce` | active | draft | temperature not stated (Q26) |
| `pacific_sand_lance_rice_koji_fish_sauce` | active | active, with `Anchovies` as stand-in (Q32) | `new` ingredient replaced by a labelled stand-in |
| `cider_vinegar_surface` | T 23.9 (15.6–35.6) | 21.1 (15.6–26.7) | the cider-specific source takes precedence over general vinegar guidance |
| `home_starter`, `levain_liquide`, `levain_dur`, `lievito_madre` | draft | active (Q31) | the planner sets the timing |
| `poolish`, `biga`, `type_iii` | draft | excluded | not sourdough recipes (commercial yeast), or no formula |

## 5. Envelope conflicts (input for the engine track, not fixed here)

- **kombucha:** sources use 30 °C; the profile tops out at 28 °C (Cohen 2023 also ran 20 and 30 °C).
- **koji:** sources span 27–40 °C (BCCDC); the profile is 28–35 °C.
- **garum:** sources run 10–18 months at 18 °C or tropical ambient; the profile horizon is 180 days and its range starts at 20 °C.
- **miso:** red miso runs to 12 months against a 180-day horizon.
- **cheese:** the lactic fresh curd sets at 21–22 °C over 10–21 h; the profile is 28–32 °C (*Lc. lactis*, rennet-assisted). A mesophilic lactic-set variant of the profile would bring this style into range.
- **kefir:** the high-grain (10 %) kefir runs 24–72 h against a 48 h horizon, and 25 °C is the profile's top edge.
- **lacto_ferment:** kimchi is 1–2 days; that's fine, the horizon only caps.

## 6. Ingredient gaps → plug-in queue (`ADDING_AN_INGREDIENT.md`)

Ranked by recipes they would unlock or improve.

| ingredient | needed tier | unlocks |
|---|---|---|
| `Gochugaru` (dried red pepper powder) | T0 + T1 + T2 | correct kimchi; aroma targets (pungent) |
| `Vinegar (5 %)` | T0 + T1 | dill pickles (also needs a dill mass) |
| `Salted shrimp` (saeujeot), `Glutinous rice paste` | T0 + T1 | kimchi optional rows become core |
| `Pacific sand lance` | T0 + T1 (optional) | removes the Q32 stand-in label |
| `Garlic`, `Onion`, `Radish`, `Chilies`, `Carrot` | T2 | kimchi aroma realism. All are in the lacto-ingredients research round (`feat/aroma-lacto-ingredients`) |
| `Salt`, `Water`, `Cane sugar`, `SCOBY / starter liquid`, `Koji spores (A. oryzae)`, `Kefir grains`, `Starter/cheese culture`, `Rennet` | none | no aroma entry needed: staples and starters work through engine pools and organisms |

## 7. Follow-up curation (open)

- Sourced ranges to replace the widened envelopes (Q25): black-tea and green-tea kombucha, kimchi temperature.
- Kimchi fridge stage (`temp_schedule`) from an opened source.
- Flavoured kombucha second ferment: no tested source yet (curator lead).
- Codex CXS 223-2001 (kimchi): the curator's fetches returned 403. Retry, since it would make kimchi institutional.
- Noma-style koji garum: only secondary culinary pages so far, so not used.
- Quark or cultured-milk curd, and a backslopped or mother-culture kefir: no single opened source stated dose, temperature and time together (dairy curator leads).
- Vinegar: the profile range (24–30 °C) excludes the cooler home-cider envelope. This goes to the engine track, like the cheese item in § 5.
