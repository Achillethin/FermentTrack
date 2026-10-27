# Recipe curation (R0): the library behind the recommender's Proven section

**Date:** 2026-10-07
**Status:** IMPLEMENTED (2026-10-13). B1 of the recommender build (`8241879` on `feat/recommender-spec`) froze it into the v1 library; § 8 has the notes. Owner decisions Q31–Q32 (2026-10-08) are applied.
- 17 recipes are curated in § 3; 13 are active.
- 10 sourdough catalogue mappings are in § 3a; 7 are active and hand off to the sourdough planner.
**Design:** `2026-10-07-fermentation-recommender-design.md` § 4.
**Research:** `docs/superpowers/research/recipes/` holds `BRIEF.md`, the `01-<group>.md` files with full citations, locators and derivations, and the `*_draft_v0.<group>.csv` files.

## 1. How to read this

The tables in § 3 are the decisions that `scripts/build_recipes.py` applies to the research drafts to write the frozen `src/fermenttrack/recommender/recipes_v1.csv` and `recipe_ingredients_v1.csv`. The script encodes them as data, each citing its section here, and `tests/test_recommender_library.py` checks the result against these tables. The drafts are evidence; **this file is the decision**.

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
| `napa_kimchi_room_temp` | lacto_ferment | peer (formula) + inst (time) | 20.0 (20–20) | 36 (24–48) | 2.5 (2.0–5.0) | T widened → 17–23; d sourced | in_range | **active** | Formula from Jang 2024; the 1–2 day room-temperature window and pH ≤ 4.6 come from CSU/NCSU extension. **Fix before build:** "red pepper powder" is booked as `Chilies` (fresh). It should become the new T0 ingredient `Gochugaru` (dried), which the lacto-ingredients round already lists. Until then, keep `Chilies` and add the note "dried powder booked as fresh chili: dry matter understated several-fold", with mass unchanged. `Salted shrimp` and `Glutinous rice paste` are `new` and become `optional` (1.5 % and 0.8 % of the batch), so the recipe can stay active. The fridge stage after day 2 is not sourced in the draft, so `temp_schedule` stays empty (follow-up). **Revised 2026-10-24 (recommender v2 release 2):** the salt median is the typical 2.5 % (Patra 2016; Foods 2025 measured 2.3 %), not the midpoint of CSU's 2–5 %, which stays the range; Salt 25 g/kg, Napa cabbage 798.5 g/kg |
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

## 8. Implementation notes (2026-10-13)

**Build.**
- `scripts/build_recipes.py` reads `docs/superpowers/research/recipes/*_draft_v0.*.csv` and applies every decision in §§ 1, 3, 3a and 4. The decisions are encoded as data in the script, each with a comment citing its section here. A draft key without a decision fails the build.
- Q25 widening, `envelope_basis` and `model_scope` are derived from `prediction/profiles.py`.

```bash
python scripts/build_recipes.py           # rewrites both v1 files
python scripts/build_recipes.py --check   # exit 1 if the committed files differ from a fresh build
```

**Tests:** `tests/test_recommender_library.py` checks the files against this spec, among others with:
- `test_twenty_active_four_draft_and_no_excluded_styles`;
- `test_v1_matches_the_curated_recipe_table` and `test_v1_matches_the_sourdough_table`;
- `test_rice_koji_is_split_15_to_17`;
- `test_sand_lance_books_anchovies_as_a_labelled_stand_in`;
- `test_kimchi_keeps_chilies_labelled_and_new_seasonings_optional`;
- `test_rename_and_cider_temperature`;
- `test_q25_widens_single_values_and_clips_in_range_temperatures`;
- `test_ingredient_medians_sum_to_1000_g_per_kg`.

**v1 counts:** `recipes_v1.csv` has 24 rows.
- **20 active:**
  - the 13 curated recipes of § 3;
  - the 7 sourdough styles of § 3a.
- **4 draft:** dill pickles, carrot sticks, barley koji and budu. Draft recipes are library data (`GET /recipes?status=draft`) and are never served.
- **3 excluded:** poolish, biga and Type III are not in v1 (`GET /recipes/{key}` is a 404).

The per-type split is § 2's table.

**Q31 (sourdough → planner), as built:**
- Each of the 7 styles carries `handoff = planner` and its `planner_style`.
- **Matching and scoring:** like any recipe. The grid runs the levain build through `bake.py` with the style's own flour; the v1 rows book every wheat as `White wheat flour`.
- **No duration:** the four planner-timed styles (`home_starter`, `levain_liquide`, `levain_dur`, `lievito_madre`) run to the profile's horizon.
- **Start batch** answers 409 with a planner link (`#/levain?p=…`, the planner's share format), pre-filled with the style at the served temperature and scaled to the batch size.
- **Window and slider:** the window is the levain peak's P10 / P50 / P90 from the grid. Type II is source-only at 37 °C, so its window comes from the source. Sourdough cards have no temperature slider.
- **Variants:** (ii) flour swap and (iii) temperature only. Search deeper leaves sourdough parents out, your own sourdough batch can't be a parent (422), and community publishing refuses sourdough.
- **E1:** the sourdough styles have no ingredient query (their core is all staples), so they are listed as ineligible, not counted as misses.
- **Not built:** the planner doesn't carry the card's id, so a batch it creates gets no recommendation link (an open item in the design's § 17.12).

**Q32 (unmapped species), as built:**
- `pacific_sand_lance_rice_koji_fish_sauce` books `Anchovies` at 800 g/kg, labelled "stand-in species: recipe uses Pacific sand lance".
- Its rice koji is split into `White rice` 70.6 + `Water` 9.4 g/kg, and `temp_schedule` is `0:20;48:18`.
- At its 18 °C median it is source-only, below the garum profile's 20 °C, so its window comes from the source. It is also beyond the horizon.
- Its 12.0 % salt passes the garum salt minimum the gate added later (8.3 %, design § 7). That minimum is the low end of this recipe's own 8.3–15.4 %.

**Also as decided in § 3:**
- kimchi keeps `Chilies` with its label, and its two `new` seasonings are optional rows;
- both misos and the sand lance split rice koji 15 : 17;
- `green_tea_kombucha_variant` became `green_dominant_kombucha`;
- cider vinegar runs at 21.1 (15.6–26.7) °C.

All three salt-barrier recipes pass the minimums: shiro miso 6.1 %, red miso 11.9 %, sand lance 12.0 %.

**Use levels:** `ingredient_use_levels_v1.csv` (tier T3) has 16 rows. They were bootstrapped only from the tier-T2 ingredient rows of the active recipes above, each sourced to its recipe row.

**Evaluation on this library** (design § 13.1, on the committed grid):

| id | result |
|---|---|
| E1 | 11/11 eligible recipes in the top 3 for their own ingredients. The 9 ineligible ones are the 7 sourdough styles and the 2 kombuchas |
| E2 | 5/6 = 83.3 %. Kimchi is the miss (rank 17) |
| E3 | 15/16 = 93.8 %, and 8/9 = 88.9 % without the source-only and beyond-horizon recipes. Kimchi is the only miss |

The kimchi misses are an engine-calibration item, not a curation one. By 72 h the engine brings only 1–11 % of kimchi members to pH 4.6, so the window collapses at the safety milestone. It joins the engine-track items of § 5.

The follow-up curation list in § 7 is unchanged and still open.

## 9. Recipe round 2: Noma and Sandor Katz (2026-10-26)

Research: `docs/superpowers/research/recipes/02-noma-katz.md` (43 candidates, every number from an opened page; provenance `chef_published`, a fourth tier ranked after `traditional_documented`). The build applies §§ 1 and 3's rules plus the four owner decisions below.

**Owner decisions (2026-10-26).**
- **D1, no stated temperature.** A source that gives none ("room temperature", "a cool place") gets the profile's temperature and range (`PROFILE_TEMPERATURE` in the build). `envelope_basis` is `profile_temperature`, and the card says "temperature not stated by the source: assumed room temperature". Applied to the recipes marked "profile T" below. Budu (§ 4) is a candidate for the same rule; not re-curated here.
- **D2, salt basis.** SALT-001's 2 % minimum reads salt / (batch − salt), the convention of the Noma Guide ("2 % of the produce and water"), NCHFP ("2.25 % by weight of cabbage") and Katz. SALT-002's 10 % and the salt-barrier minimums still read the whole batch. Both compare at the 0.01 % shown, since masses are stored to 0.1 g/kg.
- **D3, hot garum.** Garum at or above 57 °C (the FDA Food Code 2022 hot-holding line, 3-501.16(A)(1)) is exempt from TEMP-001: koji enzymes at ~60 °C with 10–12 % salt, no lactic bacteria. 45–57 °C stays refused. Gate (`GARUM_HOT_MIN_C`) and batch banner alike.
- **D4, salted vegetables' pH rule.** BOT-002 ("≤ 4.6 within 48 h, or discard") is replaced for `lacto_ferment` by two steps: VEG-001, pH below 5.0 within 48 h at > 10 °C, or discard (Noma Guide, lacto chapter, read through a reader's verbatim Kindle highlights); VEG-002, not eaten until pH ≤ 4.6, checked every 1–2 days (UMN Extension, "pH 4.60 or lower when ready"). Normal sauerkraut sits at pH 5.3–5.5 at 48 h (Kristek 2004), so BOT-002 condemned it. Other acid-safety types keep BOT-002.

**Summary.** 17 active, 26 draft. Active by type: lacto_ferment 9, kombucha 3, miso 3, garum 2. Library: 37 active (20 before), 30 draft.

**Ingredients added** (`INGREDIENT_SEED_DATA_V5`, migration 0025): Blueberries, Plums, Blackberries, Mulberries, White currants, Mushrooms, Apple juice (unfiltered), Yellow split peas (cooked), Chicken wings (roasted), Chicken stock and Lamb tongue with their FDC nutrients (tier T1, § D's matches); Lemon verbena (dried), Coffee (ground) and Elderflower at T0 (no FDC row). None has aroma data yet: the cards say so.

**Build changes.** Stand-ins: ceps → `Mushrooms`, pearl-barley koji → rice koji (chicken garum), lamb → `Lamb tongue`. Rice koji split 15 : 17 as in § 3 for both Katz misos, the peaso and both garums. Unweighed optional rows are left out of the served recipe (`DROPPED_ROWS`). A `new` ingredient catalogued since the research becomes `existing_no_aroma`. The 1000 ± 5 % g/kg mass check applies to active recipes only. `ingredient_use_levels_v1.csv`'s bootstrap rows now include round 2's T2 rows (White rice in garum and miso, Soybeans, Cabbage, Napa cabbage).

Abbreviations as § 3; prov `chef` = chef_published; basis `profile T` = D1.

| key | type | prov | T °C med (lo–hi) | d h med (lo–hi) | salt % med (lo–hi) | basis | model_scope | status | curation note |
|---|---|---|---|---|---|---|---|---|---|
| `noma_lacto_blueberries` | lacto_ferment | chef | 28 (25–31) | 108 (96–120) | 1.96 (1.96–1.96) | widened | temp_outside_profile | **active** | Noma Guide via The Splendid Table: 2 % of the fruit, 28 °C, 4–5 days. 28 °C is above the lacto profile: source-only card |
| `noma_lacto_ceps` | lacto_ferment | chef | 28 (25–31) | 144 (120–168) | 1.96 (1.96–1.96) | widened | temp_outside_profile | **active** | Noma Guide via MR PORTER. Ceps booked as `Mushrooms` (white-mushroom nutrients), labelled |
| `noma_lacto_plums` | lacto_ferment | chef | 24.5 (21–28) | 144 (120–168) | 1.96 (1.96–1.96) | sourced | temp_outside_profile | **active** | Noma Guide's lacto template (read via a reader's verbatim highlights): 5 days at 28 °C, 6–7 at 21 °C |
| `bergo_lacto_mushrooms_3pct` | lacto_ferment | chef | 20 (16–24) | 228 (120–336) | 2.91 (2.91–2.91) | profile T | in_range | **active** | Forager Chef after Noma and Katz: 3 % of the mushrooms (vacuum version; the brine's water is unweighed and left out). D1 temperature |
| `katz_mixed_kraut_tastingtable` | lacto_ferment | chef | 20 (16–24) | 96 (67.2–124.8) | 2.07 (2.07–2.07) | profile T; widened | in_range | **active** | Katz via Tasting Table; 3 tsp kosher salt at Morton's 4.8 g/tsp. Unweighed coriander and chili flakes left out. D1 temperature |
| `noma_rule_lacto_raspberries` | lacto_ferment | chef | 28 (25–31) | 108 (96–120) | 1.96 (1.96–1.96) | widened | temp_outside_profile | **active** | Rule-derived: Noma lacto-ferments raspberries each September with its 2 % rule; time and temperature from the blueberry recipe |
| `noma_rule_lacto_blackberries` | lacto_ferment | chef | 28 (25–31) | 108 (96–120) | 1.96 (1.96–1.96) | widened | temp_outside_profile | **active** | Rule-derived, as raspberries |
| `noma_rule_lacto_mulberries` | lacto_ferment | chef | 28 (25–31) | 108 (96–120) | 1.96 (1.96–1.96) | widened | temp_outside_profile | **active** | Rule-derived, as raspberries |
| `noma_rule_lacto_white_currants` | lacto_ferment | chef | 28 (25–31) | 108 (96–120) | 1.96 (1.96–1.96) | widened | temp_outside_profile | **active** | Rule-derived, as raspberries |
| `noma_lemon_verbena_kombucha` | kombucha | chef | 28 (25–28) | 192 (168–216) | — | widened | in_range | **active** | Noma Guide via KCRW: herbal infusion, 28 °C lab, 7–9 days. `Lemon verbena (dried)` has no FDC row (T0) |
| `noma_apple_kombucha` | kombucha | chef | 28 (25–28) | 204 (168–240) | — | widened | in_range | **active** | Noma Guide via Modern Farmer: juice only, no added sugar; bottled-juice FDC row as proxy |
| `noma_coffee_kombucha` | kombucha | chef | 28 (25–28) | 204 (168–240) | — | widened | in_range | **active** | Zilber via Munchies: 200 g fresh-ground coffee option. `Coffee (ground)` has no FDC row (T0) |
| `katz_miso_short_light` | miso | chef | 25 (15–30) | 1248 (336–2160) | 5.38 (4.76–6) | profile T | in_range | **active** | Katz's guideline (1 : 1 koji to beans, 6 % salt) via Koji Alchemy. Rice koji split 15 : 17. D1 temperature |
| `katz_miso_long_dark` | miso | chef | 25 (15–30) | 6540 (4320–8760) | 12.3 (11.6–13) | profile T | beyond_horizon | **active** | Katz's guideline (1 : 2, 13 % salt) via Koji Alchemy. Rice koji split 15 : 17. D1 temperature |
| `noma_elderflower_peaso` | miso | chef | 25 (15–30) | 2160 (1512–2808) | 5 (5–5) | profile T; widened | in_range | **active** | Noma Projects product declaration (peas 60 %, elderflower 5 %, salt 5 %, koji the rest). Rice koji split 15 : 17. D1 temperature |
| `noma_chicken_wing_garum` | garum | chef | 60 (57–60) | 672 (470.4–873.6) | 10.6 (10.6–10.6) | widened | in_range | **active** | Noma Guide via The Splendid Table: 60 °C, 4 weeks (D3). Pearl-barley koji booked as rice koji (the recipe allows commercial koji), split 15 : 17 |
| `bergo_meat_garum_noma_style` | garum | chef | 60 (57–60) | 1200 (720–1680) | 10.7 (10.7–10.7) | widened | in_range | **active** | Forager Chef after the Noma Guide's beef garum: lamb tongue, 60 °C, 30–70 days (D3). Rice koji split 15 : 17 |
| `katz_sauerkraut_basic` | lacto_ferment | chef | — | 1116 (72–2160) | 1.67 (1.67–1.67) | sourced | beyond_horizon | draft | Salt 1.67 % (1.70 % of the rest): under SALT-001's 2 % even after D2 |
| `katz_sour_pickles` | lacto_ferment | chef | — | 420 (168–672) | 2.65 (2.49–2.83) | sourced | in_range | draft | Dill and garlic unweighed |
| `katz_kombucha_basic` | kombucha | chef | 27 (24–30) | 246 (168–336) | — | sourced | temp_outside_profile | draft | Tea unweighed ("strong or weak as you like") |
| `katz_kimchi_brine_soaked` | lacto_ferment | chef | — | 48 (24–72) | — | sourced | in_range | draft | Only the cabbage is weighed; secondary adaptation |
| `katz_mexican_kimchi` | lacto_ferment | chef | — | 120 (72–168) | — | sourced | in_range | draft | Unweighed core rows; masa and pineapple not catalogued |
| `katz_milk_kefir` | kefir | chef | — | 36 (24–72) | — | sourced | beyond_horizon | draft | Only index pages opened: no grain dose, no temperature |
| `zilber_rice_koji` | koji | chef | 29 (28–30) | 48 (33.6–62.4) | — | widened | in_range | draft | Spore dose not stated |
| `koji_alchemy_long_grain_rice_koji` | koji | chef | 29 (26–32) | 36 (25.2–46.8) | — | widened | temp_outside_profile | draft | Spore dose not stated |
| `zilber_caviar_koji_garum` | garum | chef | — | 8760 (6132–11388) | 7.41 (7.41–7.41) | widened | beyond_horizon | draft | Salt 7.41 % < garum's 8.3 % barrier |
| `noma_mushroom_oat_garum` | garum | chef | — | 1344 (1008–1680) | 7 (7–7) | sourced | in_range | draft | Salt 7 % < garum's 8.3 % barrier; shares bounded by label order only |
| `bergo_ramp_leaf_koji_garum` | garum | chef | 62.8 (59.8–65.8) | 840 (588–1092) | 11.7 (11.7–11.7) | widened | temp_outside_profile | draft | Ramps have no FDC row (leek proxy only) |
| `noma_peaso_plain` | miso | chef | — | 2160 (1512–2808) | 4 (4–4) | widened | in_range | draft | Peas and koji unweighed |
| `noma_kyoto_peaso` | miso | chef | — | — | 5 (5–5) | sourced | in_range | draft | Duration not stated |
| `wf_sweet_garbanzo_miso` | miso | chef | — | 1440 (1008–1872) | 3.91 (3.91–3.91) | widened | in_range | draft | Salt 3.91 % < miso's 4 % barrier |
| `wf_black_bean_miso` | miso | chef | — | 10944 (10608–11280) | 8 (8–8) | sourced | beyond_horizon | draft | Garlic unweighed |
| `noma_perry_vinegar` | vinegar | chef | — | 288 (240–336) | — | sourced | in_range | draft | Sugar → ethanol → acetic acid needs a yeast stage the vinegar profile lacks; pears and yeast unweighed |
| `katz_persimmon_vinegar` | vinegar | chef | — | 1800 (1440–2160) | — | sourced | beyond_horizon | draft | Sugar → ethanol → acetic acid needs a yeast stage the vinegar profile lacks |
| `bergo_fruit_scrap_vinegar_classic` | vinegar | chef | — | 1224 (1008–1440) | — | sourced | in_range | draft | As persimmon vinegar; `Fruit scraps` is not a food |
| `bergo_fruit_scrap_vinegar_vodka` | vinegar | chef | — | 1416 (1056–1776) | — | sourced | beyond_horizon | draft | As persimmon vinegar |
| `noma_rule_lacto_gooseberries` | lacto_ferment | chef | 28 (25–31) | 108 (96–120) | 1.96 (1.96–1.96) | widened | temp_outside_profile | draft | The FDC row has no sugar data: the forecast would not acidify |
| `noma_rule_brined_beets` | lacto_ferment | chef | — | — | 1.96 (1.96–1.96) | sourced | in_range | draft | Rule-derived brine: vegetable-to-water ratio and time not stated |
| `noma_rule_brined_radishes` | lacto_ferment | chef | — | — | 1.96 (1.96–1.96) | sourced | in_range | draft | As beets |
| `noma_rule_brined_young_carrots` | lacto_ferment | chef | — | — | 1.96 (1.96–1.96) | sourced | in_range | draft | As beets |
| `noma_rule_brined_onions_turnips_herbs` | lacto_ferment | chef | — | — | 1.96 (1.96–1.96) | sourced | in_range | draft | As beets |
| `noma_rule_lacto_white_asparagus` | lacto_ferment | chef | — | — | 1.96 (1.96–1.96) | sourced | in_range | draft | As beets |
| `noma_rule_lacto_small_pumpkins` | lacto_ferment | chef | — | — | 1.96 (1.96–1.96) | sourced | in_range | draft | As beets |
