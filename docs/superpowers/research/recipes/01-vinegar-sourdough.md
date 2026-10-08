# Vinegar-sourdough recipe research

Group: `vinegar-sourdough`

## A. Sources opened

### Repository sources opened for sourdough mapping

- **FT-sourdough-router** - Local repository source. `src/fermenttrack/routers/sourdough.py`. Locator: `catalog()` returns every `STYLES` entry with `defaults` (`hydration_pct`, `seed_ratio`, `temperature_c`, `flour`, `hours`) and `sources` at lines 44-59.
- **FT-sourdough-catalogue** - Local repository source. `src/fermenttrack/prediction/sourdough.py`. Locators: flour catalogue at lines 73-87; `LevainStyle` fields at lines 106-122; style entries at lines 136-213; build/dough/proof plan parsing at lines 263-323. This file is the source of all sourdough numbers in the CSV. The sourdough rows below are mapped from the catalogue, not newly researched recipes.
- **FT-sourdough-schema** - Local repository source. `src/fermenttrack/schemas.py`. Locator: `SourdoughBuildIn`, `SourdoughDoughIn`, `SourdoughProofIn`, and `SourdoughPlanIn` at lines 621-654. The schema confirms that full bread dough, salt, bulk, and proof values are user-entered plan fields rather than catalogue style defaults.
- **FT-profiles** - Local repository source. `src/fermenttrack/prediction/profiles.py`. Locators: `sourdough` profile at lines 261-280 (typical 26 deg C, range 22-30 deg C, horizon 24 h, starter fraction 0.20) and `vinegar` profile at lines 499-535 (typical 27 deg C, range 24-30 deg C, horizon 60 days, aerobic, starter fraction 0.15, acetic-acid milestone 40 g/kg).
- **FT-seed-data** - Local repository source. `src/fermenttrack/seed_data.py`. Locators: `Starter/levain`, `Water`, `Salt`, and `Mother of vinegar (Acetobacter)` at lines 10-28; flour and vinegar ingredient catalogue names at lines 52-70.
- **FT-aroma-data** - Local repository source. `src/fermenttrack/prediction/aroma_data.py`. Locators: `ALCOHOL_BASES` at line 342; `AROMA_INGREDIENTS` includes the three flours and alcohol bases at lines 370-399; defaults include sourdough and vinegar at lines 502-507.

### Sourdough catalogue provenance keys

These keys are not separately web-researched in this round. They are the existing `sources` entries carried by the repository catalogue in **FT-sourdough-catalogue**, as requested.

- **Landis2021** - Existing catalogue entry: `Landis et al. 2021 eLife 10:e61644`. Locator: `home_starter` source tuple at `src/fermenttrack/prediction/sourdough.py` line 145.
- **Minervini2014** - Existing catalogue entry: `Minervini et al. 2014 AEM 80:3161`. Locators: `levain_liquide` source tuple at line 152 and `levain_dur` source tuple at line 159.
- **Carbonetto2020** - Existing catalogue entry: `Carbonetto et al. 2020 Microorganisms 8:240`. Locator: `lievito_madre` source tuple at line 168.
- **Kline1971** - Existing catalogue entry: `Kline & Sugihara 1971 Appl Microbiol 21:459`. Locator: `san_francisco` source tuple at line 176.
- **Gaenzle1998** - Existing catalogue entry: `Gänzle et al. 1998 AEM 64:2616`. Locator: `san_francisco` source tuple at line 176.
- **Brandt2004** - Existing catalogue entry: `Brandt et al. 2004 Eur Food Res Technol 218:333`. Locator: `rye_sour` source tuple at line 184.
- **Gaenzle2003** - Existing catalogue entry: `Gänzle & Vogel 2003 Int J Food Microbiol 80:31`. Locator: `type_ii` source tuple at line 192.
- **DeVuyst2005** - Existing catalogue entry: `De Vuyst & Neysens 2005 Trends Food Sci Technol 16:43`. Locator: `type_iii` source tuple at line 199.

### Public vinegar sources opened

- **AWRI2022-wine-vinegar** - Australian Wine Research Institute. 2022. "Vinegar production - inoculation of a base wine with live acetic acid bacteria." Fact Sheet: Winemaking. URL: https://www.awri.com.au/wp-content/uploads/2022/04/Inoculation-of-wine-with-acetic-acid-bacteria-for-vinegar-production.pdf. Locators: base wine parameters on page 1 (8-10% v/v alcohol, pH above 3, free SO2 <=20 mg/L); starter preparation on page 1 (1 L at 5% v/v alcohol, 25-30 deg C until film, 1-2 weeks); scale-up on page 2 (10 L at 8% v/v alcohol, 25-30 deg C, 2-3 weeks, later scale-ups 20-25% culture); final addition on page 2 (25% culture plus 75% wine/water mixture at 8% v/v alcohol gives about 6% v/v final alcohol; hold 20-30 deg C; fill barrels no more than two thirds).
- **NCState-vinegar** - North Carolina State Extension Publications. "Vinegar Making." URL: https://content.ces.ncsu.edu/vinegar-making. Locators: "Wine Vinegar" section (wine 11-12% alcohol diluted to 5.5-7% alcohol; vinegar at least 5% acetic acid for preserving and pickling; dilute wine; fill sterilized containers about two thirds full; order pure cultures sometimes called mother of vinegar; 80-85 deg F ideal; full fermentation 3-4 weeks); "Orleans Process" section (wine or cider in barrels or covered vats; starter culture; draw off about 3/4 and replace; slow several weeks); "Rate of Acetic Acid Production" section (ethyl alcohol 6-8% optimal, 12% tolerated; 80 deg F optimal, 68-96 deg F range).
- **PennState-cider-vinegar** - Penn State Extension, hosting Ohio State University Extension HYG-5346-09. "Making Cider Vinegar at Home." URL: https://extension.psu.edu/making-cider-vinegar-at-home. Locators: opening section (oxygen supply and 60-80 deg F temperature; lower temperatures may not produce usable vinegar and higher temperatures interfere with mother); "Steps 2 and 3 - Making Alcohol and Acetic Acid" (containers about three-quarters capacity, stir daily, 60-80 deg F, full fermentation 3-4 weeks, vinegar-like smell); "Uses for Homemade Cider Vinegar" (acidity varies, do not use for foods canned or stored at room temperature).
- **UCDavis-vinegar** - UC Davis Food Safety. "VINEGAR MAKING." PDF. URL: https://ucfoodsafety.ucdavis.edu/sites/g/files/dgvnsk7366/files/inline-files/192136_0.pdf. Locators: slide/page 2 (US vinegars must contain minimum 4% acetic acid); slide/page 10 (wine 11-12% alcohol diluted to 5.5-7% alcohol; wine vinegar should contain at least 5% acetic acid for preserving and pickling); slide/page 26 (ethyl alcohol 6-8% optimal, 12% tolerated; 80 deg F optimal, 68-96 deg F range).
- **NIST-conversions** - National Institute of Standards and Technology. "Approximate Conversions from U.S. Customary Measures to Metric." URL: https://www.nist.gov/pml/owm/metric-si/unit-conversion/approximate-conversions-us-customary-measures-metric. Locator: Temperature table: deg F to deg C is "subtract 32, then divide by 1.8."
- **UCDavis-cider-vinegar** - UC Davis Food Safety mirror of Ohio State University Extension HYG-5346-09. "Making Cider Vinegar at Home." URL: https://ucfoodsafety.ucdavis.edu/sites/g/files/dgvnsk7366/files/inline-files/192135.pdf. Opened as a PDF mirror of the Penn State/Ohio State leaflet; no additional numbers beyond **PennState-cider-vinegar** were used.

## B. Recipes

### Sourdough catalogue mapping rule

The sourdough rows are catalogue mappings from **FT-sourdough-catalogue** and **FT-sourdough-router**. No web research was used for sourdough.

For starter or yeast build styles, the catalogue fields give `seed_ratio` = grams of flour per gram of seed and `hydration_pct` = grams water per 100 g fed flour. I normalised each style as:

`seed = 1 g`; `fed_flour = seed_ratio`; `fed_water = seed_ratio * hydration_pct / 100`; `total = seed + fed_flour + fed_water`; each ingredient `g_per_kg = 1000 * grams / total`.

Salt is 0 for these catalogue builds because the style defaults and `Build` contain only seed, flour, water, flour blend, temperature, and optional hours. Full dough salt, bulk, and proof values are `SourdoughDoughIn` and `SourdoughProofIn` user-plan fields, not catalogue defaults; where a style has no fixed `hours`, the CSV duration is blank and `status=draft`.

### home_starter - Home wheat starter

- Sources: FT-sourdough-catalogue lines 140-145; FT-sourdough-router lines 44-59; Landis2021 from the catalogue `sources`.
- Facts copied: hydration 100%; seed ratio 5; temperature 24 deg C; flour `t65`; `hours=None`; source `Landis et al. 2021 eLife 10:e61644`.
- Derivation: total = 1 + 5 + 5 = 11. Starter/levain = 1000/11 = 90.9 g/kg; White wheat flour = 5*1000/11 = 454.5 g/kg; Water = 454.5 g/kg. Duration blank because the catalogue has no fixed build time.
- One-line method: Feed ripe starter at 1:5:5 with white wheat flour and ferment to the modelled peak.
- Notes: Draft because duration is a model endpoint rather than a fixed sourced time.

### levain_liquide - Liquid levain

- Sources: FT-sourdough-catalogue lines 148-152; FT-sourdough-router lines 44-59; Minervini2014 from the catalogue `sources`.
- Facts copied: hydration 100%; seed ratio 3; temperature 26 deg C; flour `t65`; `hours=None`; source `Minervini et al. 2014 AEM 80:3161`.
- Derivation: total = 1 + 3 + 3 = 7. Starter/levain = 142.9 g/kg; White wheat flour = 428.6 g/kg; Water = 428.6 g/kg. Duration blank because the catalogue has no fixed build time.
- One-line method: Feed ripe starter at 1:3:3 as a liquid white-wheat levain and ferment to the modelled peak.
- Notes: Draft because duration is a model endpoint rather than a fixed sourced time.

### levain_dur - Stiff levain

- Sources: FT-sourdough-catalogue lines 155-159; FT-sourdough-router lines 44-59; Minervini2014 from the catalogue `sources`.
- Facts copied: hydration 55%; seed ratio 3; temperature 24 deg C; flour `t65`; `hours=None`; source `Minervini et al. 2014 AEM 80:3161`.
- Derivation: water = 3*0.55 = 1.65; total = 1 + 3 + 1.65 = 5.65. Starter/levain = 177.0 g/kg; White wheat flour = 531.0 g/kg; Water = 292.0 g/kg. Duration blank because the catalogue has no fixed build time.
- One-line method: Feed ripe starter at 1:3:1.65 as a stiff white-wheat levain and ferment to the modelled peak.
- Notes: Draft because duration is a model endpoint rather than a fixed sourced time.

### lievito_madre - Italian mother dough

- Sources: FT-sourdough-catalogue lines 162-167; FT-sourdough-router lines 44-59; Carbonetto2020 from the catalogue `sources`.
- Facts copied: hydration 45%; seed ratio 1; temperature 27 deg C; flour `t45`; `hours=None`; source `Carbonetto et al. 2020 Microorganisms 8:240`.
- Derivation: water = 1*0.45 = 0.45; total = 1 + 1 + 0.45 = 2.45. Starter/levain = 408.2 g/kg; White wheat flour = 408.2 g/kg; Water = 183.7 g/kg. Duration blank because the catalogue has no fixed build time.
- One-line method: Refresh stiff starter at 1:1:0.45 with white wheat flour and ferment to the modelled peak.
- Notes: Draft because duration is a model endpoint rather than a fixed sourced time.

### san_francisco - San Francisco sourdough

- Sources: FT-sourdough-catalogue lines 171-176; FT-sourdough-router lines 44-59; Kline1971 and Gaenzle1998 from the catalogue `sources`.
- Facts copied: hydration 55%; seed ratio 2.5; temperature 27 deg C; flour `t65`; fixed `hours=8.0`; sources `Kline & Sugihara 1971 Appl Microbiol 21:459` and `Gänzle et al. 1998 AEM 64:2616`.
- Derivation: water = 2.5*0.55 = 1.375; total = 1 + 2.5 + 1.375 = 4.875. Starter/levain = 205.1 g/kg; White wheat flour = 512.8 g/kg; Water = 282.1 g/kg. Duration = 8 h.
- One-line method: Build a stiff San Francisco-style sponge at 27 deg C for 8 h.
- Notes: Active for the catalogue build; the repository has no separate bread dough bulk or proof default.

### rye_sour - Rye sour

- Sources: FT-sourdough-catalogue lines 179-184; FT-sourdough-router lines 44-59; Brandt2004 from the catalogue `sources`.
- Facts copied: hydration 90%; seed ratio 10; temperature 28 deg C; flour `rye_t130`; fixed `hours=16.0`; source `Brandt et al. 2004 Eur Food Res Technol 218:333`.
- Derivation: water = 10*0.90 = 9; total = 1 + 10 + 9 = 20. Starter/levain = 50.0 g/kg; Rye flour = 500.0 g/kg; Water = 450.0 g/kg. Duration = 16 h.
- One-line method: Build a medium-rye sour at 1:10:9 and ferment warm for 16 h.
- Notes: Active for the catalogue build; the repository has no separate bread dough bulk or proof default.

### type_ii - Liquid sour Type II

- Sources: FT-sourdough-catalogue lines 187-192; FT-sourdough-router lines 44-59; Gaenzle2003 from the catalogue `sources`.
- Facts copied: hydration 200%; seed ratio 10; temperature 37 deg C; flour `t80`; fixed `hours=18.0`; source `Gänzle & Vogel 2003 Int J Food Microbiol 80:31`.
- Derivation: water = 10*2.00 = 20; total = 1 + 10 + 20 = 31. Starter/levain = 32.3 g/kg; White wheat flour = 322.6 g/kg; Water = 645.2 g/kg. Duration = 18 h.
- One-line method: Build a warm liquid Type II sour as an acidifying liquid culture for 18 h.
- Notes: Active for the catalogue build, but its 37 deg C temperature is outside the sourdough profile range.

### type_iii - Dried sourdough Type III

- Sources: FT-sourdough-catalogue lines 195-199; FT-sourdough-router lines 44-59; DeVuyst2005 from the catalogue `sources`.
- Facts copied: hydration 0%; seed ratio 0; temperature 26 deg C; flour `t65`; no fixed `hours`; source `De Vuyst & Neysens 2005 Trends Food Sci Technol 16:43`.
- Derivation: the catalogue describes dried sour powder added to yeasted dough but gives no dough formula. The ingredient row therefore records `Dried sourdough powder` at 1000 g/kg as the catalogue powder entry, not a complete bread dough.
- One-line method: Use dried sour powder as an acidifying ingredient in a yeasted dough.
- Notes: Draft because the catalogue does not provide the needed dough mass, yeast mass, or duration defaults.

### poolish - Poolish

- Sources: FT-sourdough-catalogue lines 202-205; FT-sourdough-router lines 44-59. The catalogue entry has no external `sources`.
- Facts copied: hydration 100%; seed ratio 1000 g flour per g yeast; temperature 20 deg C; description states about 0.1% yeast and 12-16 h.
- Derivation: total = 1 + 1000 + 1000 = 2001. Instant yeast = 0.5 g/kg; White wheat flour = 499.8 g/kg; Water = 499.8 g/kg. Duration range = 12-16 h, median 14 h.
- One-line method: Mix a 100% hydration yeasted white-wheat preferment and ferment at room temperature.
- Notes: Draft because no external source entry is present in the catalogue.

### biga - Biga

- Sources: FT-sourdough-catalogue lines 208-211; FT-sourdough-router lines 44-59. The catalogue entry has no external `sources`.
- Facts copied: hydration 50%; seed ratio 330 g flour per g yeast; temperature 18 deg C; description states 16-20 h.
- Derivation: water = 330*0.50 = 165; total = 1 + 330 + 165 = 496. Instant yeast = 2.0 g/kg; White wheat flour = 665.3 g/kg; Water = 332.7 g/kg. Duration range = 16-20 h, median 18 h.
- One-line method: Mix a stiff yeasted white-wheat preferment and ferment cool.
- Notes: Draft because no external source entry is present in the catalogue.

### wine_orleans_surface - Wine vinegar by surface Orleans method

- Sources: AWRI2022-wine-vinegar; NCState-vinegar; UCDavis-vinegar; NIST-conversions.
- Facts copied: AWRI base wine ideal 8-10% v/v alcohol and final barrel addition of 25% culture to 75% wine/water mixture at 8% v/v alcohol to yield about 6% v/v final alcohol; AWRI temperature 20-30 deg C. NC State wine section gives wine diluted from 11-12% alcohol to 5.5-7% before vinegar and at least 5% acetic acid for preserving and pickling; NC State gives 3-4 weeks and 80-85 deg F ideal. UC Davis gives legal minimum 4% acetic acid and 6-8% ethyl alcohol optimal for vinegar.
- Derivations: temperature = AWRI 20-30 deg C, median 25.0 deg C. Duration = 3-4 weeks = 504-672 h, median 588 h. Ingredient normalization uses a 1000 g starting batch with AWRI's 25% culture inoculation: mother = 250 g/kg and diluted wine-water phase = 750 g/kg. To split the 8% v/v wine-water phase using NC State's 11-12% source wine, wine fraction median = 8/11.5 = 0.6957; Red wine = 750*0.6957 = 521.7 g/kg. Low/high Red wine = 750*(8/12) = 500.0 to 750*(8/11) = 545.5 g/kg. Water is the complement within the 750 g/kg diluted phase: median 228.3 g/kg, range 204.5-250.0 g/kg.
- One-line method: Dilute wine for surface acetification, inoculate with active mother culture, keep oxygen available, and ferment until target acidity is reached.
- **Safety note:** verify acidity before using vinegar for preserving; NC State says at least 5% acetic acid for preserving and pickling and UC Davis states a US minimum of 4% acetic acid for vinegar.
- Notes: Ethanol recommendations conflict slightly: NC State gives 5.5-7% diluted wine, AWRI's final barrel method yields about 6%, and UC Davis gives 6-8% as optimal.

### cider_vinegar_surface - Cider vinegar from hard cider

- Sources: PennState-cider-vinegar; NCState-vinegar; UCDavis-vinegar; NIST-conversions.
- Facts copied: Penn State/Ohio State cider leaflet gives 60-80 deg F, oxygen supply, daily stirring, and full fermentation 3-4 weeks; NC State Orleans section says wine or cider can be fermented in barrels or covered vats, about 3/4 drawn off and replaced, so 25% mother/backslop is retained; NC State rate section gives 6-8% ethyl alcohol optimal and 68-96 deg F range; UC Davis gives minimum 4% acetic acid for vinegar.
- Derivations: cider-specific 60-80 deg F converts by NIST to 15.6-26.7 deg C. NC State's general vinegar range 68-96 deg F converts to 20.0-35.6 deg C. Combined temperature range covers both: 15.6-35.6 deg C. Median uses the midpoint between the cider-specific midpoint (21.1 deg C) and the general optimum (26.7 deg C) = 23.9 deg C. Duration = 3-4 weeks = 504-672 h, median 588 h. Ingredient normalization uses 25% retained mother/backslop from the Orleans replacement ratio: Hard cider = 750 g/kg and Mother of vinegar = 250 g/kg.
- One-line method: Inoculate hard cider with retained mother/backslop in an oxygen-accessible covered vessel and ferment until acidic.
- **Safety note:** Penn State warns homemade vinegar acidity varies and should not be used for foods canned or stored at room temperature unless acidity is verified.
- Notes: Active because every numeric value is sourced, but the cider ethanol value uses NC State/UC Davis general vinegar guidance rather than the cider leaflet itself.

## D. Envelope check

- Profiles read from **FT-profiles**:
  - `sourdough`: typical 26 deg C; range 22-30 deg C; horizon 24 h; starter fraction 0.20; typical fed levain recipe is unsalted.
  - `vinegar`: typical 27 deg C; range 24-30 deg C; horizon 1440 h; aerobic; starter fraction 0.15; typical recipe includes 55 g/kg ethanol and an acetic-acid milestone of 40 g/kg.
- `home_starter`: 24 deg C is inside the sourdough profile range; no fixed duration is catalogued; salt is 0 because this is a levain build.
- `levain_liquide`: 26 deg C matches the sourdough profile typical; no fixed duration is catalogued; salt is 0.
- `levain_dur`: 24 deg C is inside the sourdough profile range; no fixed duration is catalogued; salt is 0.
- `lievito_madre`: 27 deg C is inside the sourdough profile range; no fixed duration is catalogued; salt is 0.
- `san_francisco`: 27 deg C is inside the sourdough profile range; 8 h is inside the 24 h horizon; salt is 0.
- `rye_sour`: 28 deg C is inside the sourdough profile range; 16 h is inside the 24 h horizon; salt is 0.
- `type_ii`: 37 deg C is outside the sourdough profile range of 22-30 deg C; 18 h is inside the 24 h horizon; salt is 0. This is an intentional catalogue acidifier style rather than a normal bread leavener.
- `type_iii`: 26 deg C matches the sourdough profile typical, but no duration or full dough formula is catalogued.
- `poolish`: 20 deg C is below the sourdough profile range; 12-16 h is inside the 24 h horizon; salt is 0. This is a yeasted Type 0 preferment and has no external catalogue source entry.
- `biga`: 18 deg C is below the sourdough profile range; 16-20 h is inside the 24 h horizon; salt is 0. This is a yeasted Type 0 preferment and has no external catalogue source entry.
- `wine_orleans_surface`: 20-30 deg C overlaps the vinegar profile but its lower edge is below the 24-30 deg C profile range; 504-672 h is shorter than the 1440 h profile horizon; 25% culture inoculation exceeds the profile's 15% starter fraction. Starting final alcohol around 6% v/v is close to the profile's 55 g/kg ethanol order of magnitude.
- `cider_vinegar_surface`: 15.6-35.6 deg C extends below and above the vinegar profile range because the cider-specific leaflet and general vinegar source disagree; 504-672 h is shorter than the 1440 h horizon; 25% retained mother exceeds the profile's 15% starter fraction.

## E. Unverified leads

- FAO fruit-processing vinegar pages were attempted but not retrievable in this environment, so no FAO numbers were used.
- No new sourdough recipes were researched. Poolish and biga are included only because they are existing `/sourdough/catalog` styles; both remain draft because their catalogue entries lack external `sources`.

## F. Ingredient gaps

Ranked by recipe count. `existing_no_aroma` means present in `seed_data.py` but absent from `AROMA_INGREDIENTS`; `new` means absent from the seed catalogue.

| ingredient | catalogue_status | recipe_count | recipes |
|---|---:|---:|---|
| Water | existing_no_aroma | 10 | home_starter; levain_liquide; levain_dur; lievito_madre; san_francisco; rye_sour; type_ii; poolish; biga; wine_orleans_surface |
| Starter/levain | existing_no_aroma | 7 | home_starter; levain_liquide; levain_dur; lievito_madre; san_francisco; rye_sour; type_ii |
| Mother of vinegar (Acetobacter) | existing_no_aroma | 2 | wine_orleans_surface; cider_vinegar_surface |
| Instant yeast | new | 2 | poolish; biga |
| Dried sourdough powder | new | 1 | type_iii |
