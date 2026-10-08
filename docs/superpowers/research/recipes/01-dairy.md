# Dairy recipe research

Group: `dairy`

## A. Sources opened

- **Youn2022-kefir** — Youn, Hye-Young; Kim, Dong-Hyeon; Kim, Hyeon-Jin; Bae, Dongryeoul; Song, Kwang-Young; Kim, Hyunsook; Seo, Kun-Ho. 2022. "Survivability of Kluyveromyces marxianus Isolated From Korean Kefir in a Simulated Gastrointestinal Environment." *Frontiers in Microbiology*. DOI: 10.3389/fmicb.2022.842097. URL: https://www.frontiersin.org/journals/microbiology/articles/10.3389/fmicb.2022.842097/full. Locator: "Isolation of Yeast Strains From Kefir": 50 g viable kefir grains; 1 L sterilized milk; 25°C; 24 h.
- **Kim2016-kefir-antimicrobial** — Kim, Dong-Hyeon; Jeong, Dana; Kim, Hyunsook; Kang, Il-Byeong; Chon, Jung-Whan; Song, Kwang-Young; Seo, Kun-Ho. 2016. "Antimicrobial Activity of Kefir against Various Food Pathogens and Spoilage Bacteria." *Korean Journal for Food Science of Animal Resources* 36(6):787-790. DOI: 10.5851/kosfa.2016.36.6.787. URL: https://pmc.ncbi.nlm.nih.gov/articles/PMC5243963/. Locator: "Kefir preparation": 100 g viable kefir grains; 1000 mL sterilized milk; 10% w/v; 25°C; 24, 36, 48, or 72 h. Locator: Table 1: pH range across kefirs/timepoints 4.05 at 24 h to 3.64 at 72 h.
- **AcademyCheese-lactic** — Academy of Cheese. 2024. "Lactic Cheese." Academy of Cheese technical PDF. URL: https://academyofcheese.org/wp-content/uploads/2024/03/lactic-pdf.pdf. Locator: "STEP INSTRUCTIONS": heat milk to 21-22°C; starter culture options include bulk starter incubated at 21°C for 18 h until pH 4.6; starter dose 0.5-0.8%; ripen milk 2-3 h until pH 6.3-6.5; rennet strength 140 IMCU/mL and 5-10 mL/100 L; leave to coagulate until pH 4.60 after 8-18 h; salt 1.0-1.3% after draining.

## B. Recipes

### milk_kefir_grains_5pct_24h — Milk kefir from grains 5%

- Sources: Youn2022-kefir.
- Facts copied: 50 g viable kefir grains were added to 1 L sterilized milk and fermented at 25°C for 24 h.
- Derivations: 50 g grains per 1 L milk = 5% w/v. For FermentTrack batch normalization, 1 L milk is treated as 1000 g; total starting mass = 1050 g. Milk = 1000/1050 x 1000 = 952.4 g/kg. Kefir grains = 50/1050 x 1000 = 47.6 g/kg.
- One-line method: Add kefir grains to milk, ferment for 24 h at 25°C, then strain out the grains.
- Notes: The source states the inoculation as w/v; normalized g/kg values use the explicit 1 L milk ≈ 1000 g approximation.

### milk_kefir_grains_10pct_extended — Milk kefir from grains 10% extended

- Sources: Kim2016-kefir-antimicrobial.
- Facts copied: 100 g viable kefir grains were inoculated in 1000 mL sterilized milk (10% w/v) and cultured at 25°C for 24, 36, 48, or 72 h. Table 1 reports pH values from 4.05 at 24 h to 3.64 at 72 h across the tested kefirs.
- Derivations: 100 g grains per 1000 mL milk = 10% w/v. For FermentTrack batch normalization, 1000 mL milk is treated as 1000 g; total starting mass = 1100 g. Milk = 1000/1100 x 1000 = 909.1 g/kg. Kefir grains = 100/1100 x 1000 = 90.9 g/kg. Time range 24-72 h gives median 48 h.
- One-line method: Inoculate milk with a high kefir-grain load, ferment at 25°C for 24-72 h, then strain the grains.
- Notes: Included as a materially different kefir envelope because both grain load and duration exceed the 5%/24 h recipe.

### lactic_fresh_cheese_curd — Lactic fresh cheese curd

- Sources: AcademyCheese-lactic.
- Facts copied: Heat milk to 21-22°C. Add starter cultures; source gives bulk starter dose 0.5-0.8%. Ripen for 2-3 h until pH 6.3-6.5. Add rennet; source gives 5-10 mL/100 L with strength 140 IMCU/mL. Leave to coagulate until pH 4.60 after 8-18 h. Salt 1.0-1.3% is measured after draining.
- Derivations: Total fermentation/curd-set time from culture addition to pH 4.60 = 2-3 h ripening + 8-18 h coagulation = 10-21 h; midpoint = 15.5 h. Ingredient normalization uses a 100 L milk basis treated as 100,000 g milk. Median additions: starter 650 g and rennet 7.5 g, total = 100,657.5 g; milk = 100000/100657.5 x 1000 = 993.47 g/kg; starter = 650/100657.5 x 1000 = 6.46 g/kg; rennet = 7.5/100657.5 x 1000 = 0.07 g/kg. Low/high rows use the 0.5-0.8% starter and 5-10 mL/100 L rennet range with rennet treated as water-density liquid.
- One-line method: Culture milk at 21-22°C, add rennet after early acidification, and drain the curd once it reaches pH 4.60.
- Notes: Salt is documented by the source but excluded from the recipe normalization because it is added after curd formation/drainage, outside this acidification-stage scope.

## D. Envelope check

- Profiles read from `profiles.py`:
  - `kefir`: typical 22°C; range 18-25°C; horizon 48 h; typical recipe is milk-like solids; starter fraction 0.05; notes say 2-5% grains assumed when none is logged.
  - `cheese`: typical 30°C; range 28-32°C; horizon 24 h; models milk/curd acidification only, not ripening; milestone includes pH below 4.6 for acid-set fresh cheese range.
- `milk_kefir_grains_5pct_24h`: 25°C is at the upper edge of the `kefir` range; 24 h is inside the 48 h horizon; 47.6 g/kg grains is consistent with the profile's 5% starter assumption.
- `milk_kefir_grains_10pct_extended`: 25°C is at the upper edge of the `kefir` range; 72 h upper duration exceeds the 48 h profile horizon; 90.9 g/kg grains exceeds the profile note's 2-5% grain assumption.
- `lactic_fresh_cheese_curd`: 21-22°C is below the current `cheese` profile range of 28-32°C; 10-21 h is inside the 24 h horizon; the pH 4.60 endpoint matches the acid-set fresh-cheese milestone.

## E. Unverified leads

- Backslopped or mother-culture kefir: searches/opened pages did not yield a stronger public source with a materially different backslopped method that stated ratio, temperature and hours together, so no row was added.
- Quark or cultured-milk curd: opened quark leads included a PMC buttermilk-quark paper and a NepJOL PDF lead, but the accessible/parsible text did not provide a compact, source-stated starting recipe with culture or rennet dose, temperature and set time; no row was added.
- Commercial fromage blanc/chevre recipes: opened one fromage blanc recipe page, but it was superseded by AcademyCheese-lactic because the Academy guide states culture dose, rennet dose, temperature, pH and hours in one technical source.

## F. Ingredient gaps

Ranked by recipe count. `existing_no_aroma` means present in `seed_data.py` but absent from `AROMA_INGREDIENTS`; `new` means absent from the seed catalogue.

| ingredient | catalogue_status | recipe_count | recipes |
|---|---:|---:|---|
| Kefir grains | existing_no_aroma | 2 | milk_kefir_grains_5pct_24h; milk_kefir_grains_10pct_extended |
| Starter/cheese culture | existing_no_aroma | 1 | lactic_fresh_cheese_curd |
| Rennet | existing_no_aroma | 1 | lactic_fresh_cheese_curd |
