# Aroma evidence — kombucha, vinegar, sourdough (dough/starter), koji

Research slice 02 for the aroma increment (brief: `BRIEF.md`). Tables B (evidence per ferment) and D (missing key odorants) per ferment, then table E (unverified leads) and Sources.

Conventions: concentrations in µg/kg (≈ µg/L); "area only" = relative peak area / semi-quantitative, used as presence evidence only. "(fig., ±~10 %)" = read from a figure. Source tags [K1], [V1], [S1], [J1] refer to the Sources list.

Status: done (2026-10-05). Kombucha, vinegar, sourdough, koji: tables B + D; table E; Sources.

## 1. Kombucha

**Studies used** (all opened; tables extracted from the PMC/journal HTML):

| Tag | Design | Quantification | Caveat |
|---|---|---|---|
| [K1] Suffys 2023 | Commercial SCOBY (Fairment; *Brettanomyces*/*Komagataeibacter* typical), 1:1 green+black tea 8 g/L, sucrose 60 g/L, 10 % starter, **30 °C**, D0/2/4/7/9/11/14 (20 °C run "similar trends", not tabulated). SBSE-GC-MS. Table 1 (conc.), Table 2 (OAV). | "ppm", semi-quantified vs heptan-1-ol internal standard | **Shape only.** Printed thresholds (linalool 10 ppm, 2-PE 20 ppm) are ~10³× literature water thresholds, so the "ppm" magnitudes are not absolute. pH 4.05 → 3.00; ethanol 0.13 → 0.74 %. |
| [K2] Wu 2023 | Fu-brick tea 5 g/L, sucrose 100 g/L, 10 % SCOBY, **30 °C**, D0/3/7/10/14; *Komagataeibacter* 68–96 %, *Zygosaccharomyces*/*Dekkera* after D3. HS-SPME-GC-MS. Table 3. | ng/g, internal-standard equivalent (1,2-dichlorobenzene) | Semi-quant: their SPME "ethanol" 24 mg/kg vs 1.23 % by Table 2 and "acetic acid" 29 mg/kg vs 10.6 g/L → polar compounds badly under-recovered; usable for shape and for ratios within a compound. |
| [K3] Tran 2022 | Defined consortia (*B. bruxellensis*, *Hanseniaspora valbyensis*, *Acetobacter indonesiensis*) and black/green tea kombucha; black tea, sucrose 50 g/L, **28 °C**, D0/7/12 (D7–12 sealed). HS-SPME-GC-MS with **calibration curves** (absolute µg/L). | absolute, but per-compound values only in figures/heatmaps; text gives ranges | Ranges from Results text only. |
| [K4] Ferremi Leali 2022 | Isolates from kombucha (*Zygosaccharomyces parabailii*, *B. bruxellensis*, *Nakazawaea hansenii*, *Komagataeibacter*/*Acetobacter*), 80/20 green/black tea 3 %, **28 °C, 14 d**. SPE/SPME-GC-MS with calibration (2-octanol IS). | absolute µg/L (end point) | Only a few numbers in text; rest in heatmap (Fig. 4). |
| [K5] Meng 2024 (abstract) | Traditional kombucha, *Komagataeibacter* + *Dekkera*/*S. cerevisiae*; HS-SPME-GC-MS. | "µg/L" | Ethanol given as 71.59–248.23 µg/L, i.e. semi-quant (real kombucha ethanol is g/L); treat ethyl acetate range likewise. |
| [K6] Sales 2023 | Black tea 3 %, sucrose 10 %, SCOBY, **23 °C**, BT infusion and BT-K D0/3/6/9. HS-SPME-GC-MS, Table 2. | **presence/absence only** | Presence time course. |

### Table B — kombucha

Day columns for [K1]: D0, 2, 4, 7, 9, 11, 14; for [K2]: D0, 3, 7, 10, 14. "nd" = not detected. All [K1]/[K2] numbers are semi-quantitative (see above) — use for **direction and timing**, anchor magnitudes on [K3]/[K4] where available.

| ferment | compound key | tier proposed | time course? (times → µg/kg) | end-point range µg/kg | key-odorant data (FD/OAV) | producer(s) / mechanism | conditions | source (where) |
|---|---|---|---|---|---|---|---|---|
| kombucha | 3-methylbutanol | calibrated | [K1] 22.3, 27.4, 41.9, 66.5, 61.4, 115.6, 113.4 "ppm" (monotone rise ×5); [K2] 2100, 5633, 5097, 3626, 2014 ng/g (peak D3–7 then falls ×0.36) | 700–2000 µg/L at D12 (absolute) [K3] | OAV 0.40 → 2.27 by [K1]'s own threshold | Ehrlich (Leu) by yeast; [K4]: *Z. parabailii* ≈6× *B. bruxellensis*; [K2] decline suggests AAB oxidation of fusel alcohols | 28–30 °C | [K1] Table 1–2; [K2] Table 3; [K3] Results text; [K4] Discussion |
| kombucha | 2-methylbutanol | reported | [K6] present D0–D6, absent D9 (presence) | — | — | Ehrlich (Ile) | 23 °C | [K6] Table 2 |
| kombucha | 2-methylpropanol | reported (2-point course) | [K2] nd, nd, nd, 242.7, 124.5 ng/g | 700–2000 µg/L at D12 [K3] | — | Ehrlich (Val) | 28–30 °C | [K2] Table 3; [K3] Results |
| kombucha | 2-phenylethanol | calibrated | [K1] 35.8, 77.8, 135.6, 225.0, 242.1, 288.6, 273.2 "ppm"; [K2] 445, 1657, 2905, 2904, 2948 ng/g (rise then plateau from D7) | — (absolute in [K3] Fig. only) | OAV 1.77 (D0) → 13.66 (D14) [K1]; dominant "sweet-floral-honey" note at end [K1] | Ehrlich (Phe); tea-bound share at D0 (green tea nd, black tea 1.97 "ppm" [K1]); *Z. parabailii* ≈3× *B. bruxellensis* [K4] | 28–30 °C | [K1] T1–2; [K2] T3; [K4] |
| kombucha | 3-methylbutanal | reported | [K6] present in BT infusion and D0 only (tea-derived, lost) | — | — | tea (varietal) [K3] | 23 °C | [K3] Table 2; [K6] Table 2 |
| kombucha | 2-methylbutanal | reported | [K6] D0 only | — | — | tea + Ehrlich | | [K3] T2; [K6] T2 |
| kombucha | phenylacetaldehyde | reported | [K1] nd until D14 (1.35 "ppm") | — | — | Ehrlich / tea | 30 °C | [K1] T1 |
| kombucha | methionol | reported | — | in Fig. 4 heatmap only | — | *Z. parabailii* highest producer | 28 °C, 14 d | [K4] Results |
| kombucha | 2-methylpropanal, methional | plausible | not reported in sources opened | | | Ehrlich (Val, Met) | | — |
| kombucha | 3-methylbutanoic acid | calibrated | [K1] nd(BT), nd(GT), 5.81, 7.66, 7.74, 13.86, 17.54, 31.95, 40.74 "ppm" (D0→D14 ×7); [K2] 181, 1542, 1268, 860, 2472 ng/g | 600–7000 µg/L (with ethyl acetate) [K3] | OAV 0.12 → 0.81 [K1] | Ehrlich oxidative branch; co-culture synergy [K4] | 28–30 °C | [K1] T1–2; [K2] T3; [K3]; [K4] |
| kombucha | 2-methylpropanoic acid | calibrated | [K1] nd, nd, 2.71, 3.03, 2.93, 5.84, 8.13 "ppm"; [K2] 66, 342, 262, 348, 514 ng/g | — | — | Ehrlich (Val) | 30 °C | [K1] T1; [K2] T3 |
| kombucha | 2-methylbutanoic acid | reported | [K6] present D6, D9 only | — | — | Ehrlich (Ile) | 23 °C | [K6] T2 |
| kombucha | ethyl acetate | calibrated | [K2] 2529, 3523, 6785, 15 836, 21 177 ng/g (×8.4, accelerating after D7) | 600–7000 µg/L [K3]; 51.3 µg/L (3-strain co-culture, D14; pairs < 10 µg/L) [K4]; 44.5–181.6 "µg/L" semi-quant [K5] | — | yeast AATase + chemical esterification of ethanol + acetic acid; *H. valbyensis* signature [K3]; yeast synergy needed [K4] | 28–30 °C | [K2] T3; [K3] Results; [K4] Results; [K5] abstract |
| kombucha | isoamyl acetate | calibrated (late appearance) | [K2] nd, nd, nd, 1136, 1187 ng/g | — | — | yeast AATase | 30 °C | [K2] T3; presence [K6], [K3] |
| kombucha | 2-phenylethyl acetate | calibrated | [K1] 4.63, 3.93, 7.12, 12.93, 19.63, 28.51, 40.66 "ppm" (×9); [K2] 63, 165, 273, 647, 905 ng/g (×14) | — | — | yeast AATase on 2-PE; *Z. parabailii* [K4]; *H. valbyensis* D7 signature [K3] | 28–30 °C | [K1] T1; [K2] T3 |
| kombucha | ethyl hexanoate | calibrated | [K1] nd ×3, 2.36, 3.31, 3.99, 5.87 "ppm" (appears D7); [K2] nd ×3, 125, 167 ng/g | — | — | yeast FAEE (Eeb1/Eht1) or chemical | 30 °C | [K1] T1; [K2] T3 |
| kombucha | ethyl octanoate | reported | [K6] present D6, D9 | — | — | FAEE; associated with *B. bruxellensis* [K4] | 23–28 °C | [K6] T2; [K4] |
| kombucha | ethyl decanoate | calibrated | [K2] nd, 85, 126, 146, 129 ng/g | — | — | FAEE | 30 °C | [K2] T3 ("ethyl caprate") |
| kombucha | ethyl 2-methylpropanoate | reported | — | — | — | signature of *B. bruxellensis* D12 | 28 °C | [K3] Table 2 |
| kombucha | isobutyl acetate, ethyl butanoate, ethyl 2-methylbutanoate | plausible | not reported in tea kombucha in sources opened (ethyl 2-methylbutanoate only in cascara kombucha, [K6]) | | | yeast esters | | [K6] |
| kombucha | hexanoic acid | calibrated | [K1] 21.2, 29.4, 43.1, 56.0, 44.2, 60.8, 51.4 "ppm" | — | — | yeast MCFA (FAS release) | 30 °C | [K1] T1 |
| kombucha | octanoic acid | calibrated | [K1] 74.7, 164.6, 284.0, 313.9, 321.7, 339.2, 303.5 "ppm"; [K2] nd, 257, 296, nd, 181 ng/g | — | — | yeast MCFA; highest with *B. bruxellensis* [K4] | 30 °C | [K1] T1; [K2] T3 |
| kombucha | decanoic acid | calibrated | [K1] 13.1, 3.5, 30.6, 62.5, 72.0, 94.6, 89.1 "ppm"; [K2] nd, 60, 400, nd, nd ng/g | — | — | yeast MCFA | 30 °C | [K1] T1; [K2] T3 |
| kombucha | acetaldehyde | reported | [K6] present D0, D3, D6, D9 (presence) | absolute values only in [K3] figures | — | yeast pyruvate decarboxylase; AAB ethanol → acetaldehyde → acetic acid (ADH/ALDH) | 23–28 °C | [K3] T2; [K6] T2 |
| kombucha | diacetyl | reported | — | — | — | yeast/AAB pyruvate overflow | 28 °C | [K3] Table 2 (detected, "no association") |
| kombucha | acetoin | reported | — | — | — | idem; AAB oxidise 2,3-butanediol/lactate to acetoin | 28 °C | [K3] Table 2 |
| kombucha | 2,3-pentanedione, 2,3-butanediol, ethyl lactate | plausible | not reported | | | pyruvate overflow / lactic acid minor | | — |
| kombucha | hexanal | reported (decline) | [K1] BT 10.0, GT 22.5; D0–D14: 9.07, 6.32, 4.73, 2.96, 1.93, 2.68, nd "ppm" | — | listed as key OAV odorant of BT kombucha in a review summary (not opened, see E) | tea (varietal); loss by reduction/volatilisation | 23–30 °C | [K1] T1; [K3]; [K6] |
| kombucha | nonanal | calibrated | [K1] BT 34.7; D0 nd, then 7.06, 7.07, 6.57, 4.94, 4.86, 4.13 "ppm"; [K2] 59, 34, 180, 157, nd ng/g | — | — | tea lipid oxidation | 30 °C | [K1] T1; [K2] T3; [K6] |
| kombucha | 1-octen-3-ol | reported | — | — | — | tea/fermentative; associated with *B. bruxellensis*/*H. valbyensis* D7 | 28 °C | [K3] Table 2 |
| kombucha | (Z)-3-hexenal, (Z)-3-hexenol, (E)-2-nonenal, 2-pentylfuran, (Z)-4-heptenal, 1-octen-3-one, 3-octanone, 3-octanol | plausible (green tea) / drop | not reported in sources opened | | | tea LOX volatiles | | — |
| kombucha | linalool | calibrated (direction study-dependent) | [K1] BT 222.3, GT 5.44; D0–D14: 72.2, 45.8, 33.8, 38.4, 43.9, 53.1, 48.7 "ppm" (dip then partial recovery); [K2] 111, 367, 525, 409, 270 ng/g (rise ×4.7 to D7, then fall) | +11.27 µg/L (3-strain co-culture), 8.17 µg/L (*Z. parabailii* alone), 4.14 µg/L (*B. bruxellensis* alone), D14 [K4] | OAV 7.4 (D0) → 4.9 (D14); black-tea infusion 22.3 [K1] | tea free + glycoside release (yeast β-glucosidase) − loss/oxidation to linalool oxides | 28–30 °C | [K1] T1–2; [K2] T3; [K4] Results |
| kombucha | geraniol | calibrated (decline) | [K1] BT 44.0, GT nd; 18.03, 16.34, 15.32, nd, 13.88, 12.78, 12.09 "ppm" | — | OAV 5.8 → 4.0 [K1] | tea; loss | 30 °C | [K1] T1–2 |
| kombucha | citronellol | reported | — | in Fig. 4 heatmap only | — | β-citronellol associated with *B. bruxellensis*; high in native consortium | 28 °C | [K4] Results |
| kombucha | methyl salicylate | calibrated (decline) | [K1] BT 17.03, GT nd; 17.61, 10.05, nd thereafter "ppm"; [K2] 28.6 ng/g D0, nd after | — | OAV 1.72 → 1.00 → nd [K1] | tea glycoside; [K4] *B. bruxellensis* monoculture highest producer (opposite direction) | 28–30 °C | [K1] T1–2; [K2] T3; [K4] |
| kombucha | β-damascenone | reported | [K6] present BT and D0–D9 | — | — | tea carotenoid; highest in *N. hansenii* (n.s.) [K4] | 23–28 °C | [K6] T2; [K4] |
| kombucha | β-ionone | calibrated (decline) | [K1] BT 6.15, GT 23.29; 2.77, 1.63, then nd "ppm"; [K2] 68.7 ng/g D0, nd after | — | — | tea carotenoid degradation; loss | 30 °C | [K1] T1; [K2] T3; [K6] presence |
| kombucha | limonene | calibrated (decline) | [K1] BT 60.3, GT 121.0; nd, 13.0, 8.3, 4.3, 3.7, 3.4, nd "ppm" | — | OAV infusions 2.0 (BT) / 4.0 (GT); D0 0.41 → ~0 [K1] | tea; volatilisation | 30 °C | [K1] T1–2 |
| kombucha | geranial, neral, zingiberene, carvone | drop (plausible only with added lemongrass/citrus/ginger/mint) | — | | | ingredient terpenes | | — |
| kombucha | 4-ethylguaiacol | calibrated (but **organism not in model**) | [K1] (BT nd, GT nd) 7.86, 11.82, 29.02, 30.88, 30.85, 32.44, 29.59 "ppm"; [K2] nd, 76, 69, 62, 67 ng/g | — | OAV 0.27 → 1.08 [K1] | *Brettanomyces/Dekkera* vinylphenol reductase | 30 °C | [K1] T1–2; [K2] T3 |
| kombucha | 4-ethylphenol | calibrated (but organism not in model) | [K2] 41, 221, 244, 235, 283 ng/g | — | — | *B. bruxellensis* highest producer [K4] | 28–30 °C | [K2] T3; [K4]; [K6] presence D0–D9 |
| kombucha | 4-vinylguaiacol | reported | — | heatmap only | — | highest in *N. hansenii* monoculture (n.s.) | 28 °C | [K4] Results |
| kombucha | 4-vinylphenol | plausible | — | | | hydroxycinnamate decarboxylase | | — |
| kombucha | dimethyl sulfide | reported | — | heatmap only | — | *Z. parabailii* biggest producer | 28 °C | [K4] Results |
| kombucha | methanethiol, DMDS, DMTS, S-methyl thioacetate | plausible | | | | Met catabolism by yeast | | — |
| kombucha | glucosinolate, allium, Maillard/pyrazine, milk-derived, TMA, 2-AP compounds | drop | no precursor in sweetened tea | | | | | — |
| kombucha | acetic acid | (engine pool) | [K1] nd until D14; [K2] 3607 → 29 034 ng/g (semi-quant) | | OAV 0.30 at D14 [K1] | AAB | | [K1]; [K2] |

**Model implications.** (1) Tea terpenes/norisoprenoids (geraniol, β-ionone, methyl salicylate, limonene, hexanal) mostly *decline* from D0 — a first-order loss term with the infusion as the initial pool reproduces [K1]; linalool is the exception with a yeast-dependent rise in [K2]/[K4] (glycoside release). (2) Fusel alcohols rise with yeast growth; [K2]'s late fall of 3-methylbutanol is consistent with AAB oxidising alcohols (a `c_ij` term for *Komagataeibacter/Acetobacter*). (3) Acetate esters appear late (D7–D10) in both [K1] and [K2]. (4) The 4-ethylphenols are clear in both time courses but need *Brettanomyces/Dekkera*, which is not in the organism list; keep them inactive.

### Table D — kombucha missing key odorants

| ferment | compound | tier proposed | time course? | end-point range | key-odorant data | producer / mechanism | conditions | source (where) |
|---|---|---|---|---|---|---|---|---|
| kombucha | α-farnesene | calibrated | [K1] nd ×7, 1.08 "ppm" at D14 only in Table 1, but OAV row shows 10.1, 20.8, 12.3, 8.4, 10.6, 5.1 from D2–D14 (Table 2; inconsistent with Table 1 — check PDF) | — | highest OAV mid-fermentation [K1] | possibly yeast terpene synthesis | 30 °C | [K1] T1–2 |
| kombucha | α-terpineol | calibrated | [K1] nd, 13.2, 11.3, 13.2, 13.2, 18.1, 16.5 "ppm"; [K2] nd, nd, 61.5, 71.1, 109.1 ng/g | — | — | tea; linalool acid rearrangement at pH ~3 | 30 °C | [K1] T1; [K2] T3 |
| kombucha | linalool oxides (trans-furanoid) | calibrated (decline) | [K1] BT 109.3; 15.95, 15.90, 10.64, 7.97, 5.95, 6.95, 5.28 "ppm" | — | — | tea; oxidation of linalool | 30 °C | [K1] T1 |
| kombucha | benzaldehyde | reported | [K1] 34.4, nd, nd, 1.78, 1.02, nd, nd; [K2] D3 only 186.6 ng/g | — | OAV 0.04–0.70 [K1] | tea; *Z. parabailii* [K4] | 30 °C | [K1] T1–2; [K2] T3 |
| kombucha | ethyl phenylacetate | calibrated | [K1] nd until D9: 1.25, 1.55, 1.86 "ppm"; [K2] nd ×3, 87.9, 163.2 ng/g | — | — | yeast | 30 °C | [K1] T1; [K2] T3 |
| kombucha | methyl acetate | reported | [K2] D14 only 524 ng/g | — | — | esterification with methanol (pectin-free tea → low) | 30 °C | [K2] T3; [K3] T2 |
| kombucha | ethyl propanoate, propyl acetate | reported | — | — | — | *H. valbyensis* signatures D7–12 | 28 °C | [K3] Table 2 |
| kombucha | dodecanoic (lauric) acid | reported | — | 105.5 (Nh) – 1472 µg/L (native consortium) at D14 | — | yeast FAS | 28 °C | [K4] Results |

## 2. Vinegar

**Studies used.** No open-access *absolute* time course of volatiles during static/surface acetification was found; the two genuine acetification time courses ([V1], [V2]) are paywalled and were read as abstracts only (direction of change, no numbers). Wine → vinegar contrasts with semi-quantitative data come from [V3]–[V5]; absolute end-point ranges for Sherry vinegar come from a review table [V6] (secondary; units inconsistent, see note).

| Tag | Design | Quantification | Caveat |
|---|---|---|---|
| [V1] Baena-Ruano 2010 | White wine, **submerged** semi-continuous acetification (pilot), whole cycle followed vs AAB cells, acidity, ethanol | GC (abstract only) | Directions only. |
| [V2] Morales 2001 | Sherry wine, **submerged** acetification monitored | (abstract only) | Lists compounds with significant change; no direction in abstract. |
| [V3] Es-sbata 2022 (Foods) | Prickly-pear juice → wine → **surface-culture** vinegar, 500 mL flasks, **30 and 37 °C**, inocula *Acetobacter*, *Gluconobacter* or Sherry-vinegar AAB mix; sampled every 3 weeks to constant acidity. SBSE-GC-MS, Table 1 (juice/wine/vinegar). | relative area vs 4-methyl-2-pentanol IS | Direction only; 37 °C gave lower volatiles (evaporation). |
| [V4] Bagnulo 2025 | Date fruit → juice → alcoholic product → vinegar (artisanal samples); HS-SPME-GC-MS, Table 1 "normalized response vs IS". Acetoin also quantified separately. | normalized response (relative); acetoin absolute | Process conditions not given. |
| [V5] Chen 2025 | Blackened-pear juice + food-grade ethanol to 9 % v/v (no yeast stage), *A. pasteurianus* CICC 20001 10 %, **30 °C, 10 d**, D0/2/4/6/8/10; HS-SPME-GC-MS, IS 2-octanol (µg/L equiv.). | IS-equivalent; per-compound values in Tables S5–S6 (not opened) | OAVs quoted in Results text; SPME "ethanol" 6452 → 2432 µg/L shows semi-quant scale. |
| [V6] Durán-Guerrero 2021 review, Table 3 | Ranges for Sherry vinegars compiled from 25 primary studies (refs 16, 70–94 of the review) | as printed, "mg/L" | Secondary. Printed unit is mg/L for all rows, but e.g. 3-methyl-1-butanol "5000–60 000" cannot be mg/L — some rows are evidently µg/L. Use as order-of-magnitude only; follow to primaries (see E). |
| [V7] Callejón 2008a; [V8] Callejón 2008b; [V9] Ríos-Reina 2020 | Sherry / Spanish PDO wine vinegars: GC-O (frequency, AEDA), OAV | abstracts | Key-odorant evidence (aged vinegars). |
| [V10] Palacios 2002 | Industrial Sherry vinegar ageing (solera) | abstract | Higher alcohols decrease "because of the synthesis of acetates"; acetoin increases. |
| [V11] Román-Camacho 2024 | Three submerged acetification profiles (alcohol medium, fine wine, craft beer); SBSE-GC-MS | concentrations in Table S3 (not opened) | *Komagataeibacter* negatively correlated with isoamyl alcohol, 2-PE, isoamyl/isobutyl/phenylethyl acetate, ethyl octanoate, ethyl propanoate — "consumption rather than biosynthesis". |
| [V12] OuYang 2025 | Citrus vinegar, *L. plantarum* NF2 + *A. pasteurianus* NF171, 33 °C, 120 rpm | acetoin absolute | Co-culture, not a classical vinegar. |
| [V13] Plioni 2021 | Corinthian-currant sweet wine → vinegar, *A. aceti* + *K. europaeus* (free/immobilised) or wild culture, 30 °C, aerated | normalized peak area % | Presence only (no wine column). |

### Table B — vinegar

| ferment | compound key | tier proposed | time course? (times → µg/kg) | end-point range µg/kg | key-odorant data (FD/OAV) | producer(s) / mechanism | conditions | source (where) |
|---|---|---|---|---|---|---|---|---|
| vinegar | acetaldehyde | calibrated (direction: **consumed**) | [V1] consumed "in substantial amounts" over the cycle; [V2] significant change; [V4] alcohol 197.9 → vinegar 47.5 (norm. resp.) | Sherry vinegar 5–61 (printed mg/L) [V6] | — | AAB membrane ADH (PQQ) makes it, ALDH removes it; net intermediate that does not accumulate | submerged white/Sherry wine [V1, V2] | [V1], [V2] abstracts; [V4] Table 1; [V6] Table 3 |
| vinegar | ethyl acetate | calibrated (direction **process-dependent**) | [V1] no significant change wine → vinegar (submerged); [V3] wine 13.96 → vinegar 0.17 rel. area (surface flasks, −99 %); [V4] 6921 → 5186 | Sherry vinegar 0.1–3.9 (printed mg/L; implausibly low, unit suspect) [V6]; "can reach > 3500 mg/L" in aged products (secondary statement in [V13], refs 25–27 there) | highest GC-O frequency but FD 4 [V7]; high OAV [V8]; key with diacetyl and sotolon in reconstitution [V7] | chemical esterification (EtOH + AcOH) vs stripping by aeration/evaporation; AAB esterase | 30–37 °C surface [V3] | [V1]; [V3] T1; [V4] T1; [V6] T3; [V7], [V8] |
| vinegar | acetoin | calibrated (direction: **produced**) | [V1] the one compound not consumed; [V3] wine nd → vinegar 0.137 rel. area; [V4] 675.5 → 1276.2 (norm. resp.); [V10] increases during ageing | 855 ± 150 mg/L (date vinegar) [V4]; 4033.72 ± 64.48 mg/L (co-culture, ~8× the monoculture) [V12]; Sherry 0.28–708 (printed mg/L) [V6] | key odorant of Montilla-Moriles Reserva [V9] | AAB oxidation of 2,3-butanediol and lactate; *A. pasteurianus* α-acetolactate route [V12] | 30–33 °C | [V1]; [V3] T1; [V4] T1 + text; [V6]; [V9]; [V12] abstract |
| vinegar | diacetyl | reported | [V3] wine nd → vinegar 0.0093 (n.s.) | Sherry 17–42 (printed mg/L) [V6] | highest frequency and FD with isoamyl acetate, acetic acid, sotolon [V7]; high OAV [V8]; key odorant of Jerez PX [V9] | AAB/LAB α-acetolactate oxidative decarboxylation; acetoin oxidation | | [V3]; [V6]; [V7]–[V9] |
| vinegar | 2,3-butanediol | reported | [V1] no significant change; [V3] 0.0059 → 0.0151 rel. area; [V4] 9.3 → 12.4 | — | — | carried over from wine; AAB oxidise it to acetoin | | [V1]; [V3]; [V4] |
| vinegar | 2,3-pentanedione | plausible | | | | AAB/LAB (Ile pathway) | | — |
| vinegar | ethyl lactate | calibrated (direction study-dependent) | [V1] consumed; [V2] significant change; [V3] 0.204 → 0.370 rel. area | Sherry 0.007–63 [V6] | — | chemical esterification; hydrolysis/consumption | | [V1]; [V2]; [V3]; [V6] |
| vinegar | 3-methylbutanol | calibrated (direction: **consumed**) | [V1] consumed; [V2] significant change; [V3] 0.383 → 0.028 rel. area; [V4] 1976 → 584; [V10] decreases in ageing; ([V5] increases when the base is juice + added ethanol, OAV 1.10 at end) | Sherry: "5000–60 000" (unit evidently µg/L) [V6] | — | AAB oxidation to 3-methylbutanoic acid; acetylation | 30 °C | [V1]; [V3]; [V4]; [V5] text; [V6]; [V10] |
| vinegar | 2-methylbutanol | calibrated (consumed) | [V1] consumed; [V2] significant change, the only compound sensitive to cycle length; [V3] 0.400 → 0.023 | Sherry "560–13 000" (µg/L?) [V6] | — | AAB oxidation | | [V1]; [V2]; [V3]; [V6] |
| vinegar | 2-methylpropanol | calibrated (consumed) | [V1] consumed; [V2] significant change; [V3] 0.033 → 0.003; [V4] 161.5 → 17.1 | Sherry 3.5–14.3 [V6] | — | AAB oxidation to 2-methylpropanoic acid | | [V1]; [V2]; [V3]; [V4]; [V6] |
| vinegar | 2-phenylethanol | calibrated (flat to rising) | [V1] no significant change; [V3] 0.172 → 0.264; [V4] 2073 → 3350 | Sherry 0.013–27.1 [V6] | OAV > 1 in pear vinegar [V5] | carried from wine; poor AAB substrate | | [V1]; [V3]; [V4]; [V5]; [V6] |
| vinegar | 3-methylbutanal, 2-methylbutanal | reported | [V4] 3-MB-al 10.3 (juice) → nd (alcohol) → 3.7 (vinegar); 2-MB-al 2.1 → nd → 1.0 | presence in Sherry [V6] | — | AAB alcohol dehydrogenase on fusel alcohols (aldehyde intermediates) | | [V4] T1; [V6] |
| vinegar | 2-methylpropanal | reported | — | presence in raw currant only [V13] | — | idem | | [V13] T3 |
| vinegar | methional | reported | — | — | "methional/furfural" key odorant of Jerez PX vinegar (co-eluting) [V9] | wine/ageing | | [V9] abstract |
| vinegar | phenylacetaldehyde, methionol | plausible | | | | | | — |
| vinegar | 3-methylbutanoic acid | reported (rises) | [V4] 44.3 → 93.0; [V13] presence | — | high OAV in Sherry vinegar [V8] | AAB oxidation of 3-methylbutanol | | [V4]; [V8]; [V13] |
| vinegar | 2-methylpropanoic acid | reported (rises) | [V4] 28 → 90.7 | Sherry 0.06–0.15 [V6] | — | AAB oxidation of isobutanol | | [V4]; [V6] |
| vinegar | 2-methylbutanoic acid | reported | — | presence 0.08–0.28 % area [V13] | — | AAB oxidation of 2-methylbutanol | 30 °C | [V13] T3 |
| vinegar | isoamyl acetate | reported (direction study-dependent; time course in [V5] supplement, not opened) | [V3] wine 0.812 → vinegar 0.040; [V4] 1028 → 689; [V5] OAV 5.46 late stage (juice + ethanol base) | Sherry 2.7–16.3 [V6] | highest frequency + FD [V7]; high OAV [V8]; [V5] key (OAV > 1, VIP > 1) | carried from wine; hydrolysis/stripping; [V10] acetates form during ageing | 30 °C | [V3]; [V4]; [V5]; [V6]–[V8] |
| vinegar | isobutyl acetate | reported | [V3] 0.0915 → 0.0047; [V4] 226.6 → 66.5 | Sherry 1.0–4.3 [V6] | key odorant of Condado de Huelva Reserva [V9] | idem | | [V3]; [V4]; [V6]; [V9] |
| vinegar | 2-phenylethyl acetate | reported | [V3] n.s.; [V4] 347 → 1183 | Sherry 0.5–4.8 [V6] | — | idem | | [V3]; [V4]; [V6] |
| vinegar | ethyl butanoate | reported | — | Sherry 0.05–0.3 [V6] | — | from wine | | [V6] |
| vinegar | ethyl hexanoate | reported (falls) | [V3] 0.029 → 0.004; [V4] 24.6 → 12 | Sherry 0.05–75 [V6] | — | from wine; stripping | | [V3]; [V4]; [V6] |
| vinegar | ethyl octanoate | reported (falls from wine) | [V3] 0.120 → 0.0007; [V4] 441.5 → nd; [V5] OAV 1.76 early → 6.73 late (juice + ethanol base) | Sherry 0.02–0.05 [V6] | key odorant of Jerez Reserva [V9] | from wine; stripping | | [V3]; [V4]; [V5]; [V6]; [V9] |
| vinegar | ethyl decanoate | reported (falls) | [V3] 0.025 → nd; [V4] 73.7 → nd | Sherry 0.008–0.054 [V6] | OAV > 1 late in [V5] | from wine | | [V3]; [V4]; [V5]; [V6] |
| vinegar | ethyl 2-methylbutanoate | reported | — | Sherry 0.07–0.15 [V6] | first reported in Sherry vinegar by [V8] | | | [V6]; [V8] |
| vinegar | ethyl 2-methylpropanoate | reported | [V4] 131.9 → 24.4 | Sherry 0.006–1 [V6] | high OAV in Sherry vinegar [V8] | | | [V4]; [V6]; [V8] |
| vinegar | hexanoic, octanoic, decanoic acid | reported (rise) | [V4] hexanoic 23.6 → 299.3, octanoic 98 → 777, decanoic 3.8 → 78.2; [V3] octanoic 0.168 → 0.111, decanoic 0.116 → 0.026 | Sherry: hexanoic 1.3–2.2, octanoic 0.7–2.6, decanoic 0.03–0.5 [V6] | — | ester hydrolysis at low pH; carry-over | | [V3]; [V4]; [V6] |
| vinegar | hexanal | reported | [V3] juice 0.011 → wine 0.0028 → vinegar 0.0026 | Sherry 0.009–0.05 [V6] | — | fruit | | [V3]; [V6] |
| vinegar | nonanal | reported | [V4] 52.6 → 74.9 | — | OAV 7.25 late [V5] | fruit lipid | 30 °C | [V4]; [V5] |
| vinegar | 1-octen-3-one | reported | — | presence in Sherry [V6] | — | | | [V6] |
| vinegar | (Z)-3-hexenal, (Z)-3-hexenol, (E)-2-nonenal, 2-pentylfuran, (Z)-4-heptenal, 1-octen-3-ol, 3-octanone, 3-octanol | plausible (fruit base) / drop | | | | | | — |
| vinegar | linalool | reported (falls) | [V3] wine 0.067 → vinegar 0.0012 | presence in Sherry [V6] | — | fruit; acid-catalysed loss | | [V3]; [V6] |
| vinegar | citronellol | reported | — | — | OAV 1.07 late [V5] | fruit | | [V5] |
| vinegar | β-damascenone | reported (falls) | [V3] wine 0.0075 → nd | — | — | fruit/wine | | [V3] |
| vinegar | 4-ethylguaiacol, 4-ethylphenol | reported (organism/wood not in model) | — | Sherry 0.6–2.9 and 0.02–1.6 [V6] | 4-ethylphenol key odorant of Jerez Reserva [V9] | *Brettanomyces* in wine; wood ageing | | [V6]; [V9] |
| vinegar | 4-vinylguaiacol | reported | — | — | discriminates submerged vs surface orange vinegar | from fruit hydroxycinnamates | | Cejudo-Bastante 2018 abstract [V14] |
| vinegar | sotolon | reported (aged vinegar only) | — | Sherry 0.748 [V6] | highest frequency/FD [V7], high OAV [V8], needed in reconstitution [V7] | slow chemistry in wood ageing | months–years | [V6]–[V8] |
| vinegar | other Maillard/furans, glucosinolates, sulfur, milk, fish/rice compounds | drop | no precursor/time scale in a weeks-long acetification | | | | | — |

**Model implications.** In vinegar the AAB act mostly as a *sink*: fusel alcohols, acetaldehyde and (in some processes) ethyl lactate are oxidised, so the `c_ij·X_AAB` loss term (plus a matching source for the corresponding acids: 3-methylbutanoic, 2-methylpropanoic, 2-methylbutanoic) carries the calibration; acetoin is the main AAB *product* (from 2,3-butanediol/lactate oxidation). Ethyl acetate and the yeast esters are inherited from the base and then either roughly conserved (submerged, [V1]) or largely stripped (open flasks, [V3]) — the `k0` evaporation term should be per-process (surface vs aerated) and is the dominant uncertainty. The engine's vinegar model has to start from a base with yeast volatiles (wine/cider priors) for any of this to show.

### Table D — vinegar missing key odorants

| ferment | compound | tier proposed | time course? | end-point range | key-odorant data | producer / mechanism | conditions | source (where) |
|---|---|---|---|---|---|---|---|---|
| vinegar | ethyl propanoate | reported | — | Sherry 0.6–1.5 [V6] | key odorant of Jerez Reserva [V9] | esterification of propanoic acid | | [V6]; [V9] |
| vinegar | propanoic acid | reported | — | presence [V6] | key odorant of Jerez Reserva [V9] | | | [V9] |
| vinegar | 1,1-diethoxyethane (acetaldehyde diethyl acetal) | reported | — | — | key odorant of Condado de Huelva Reserva [V9] | chemical acetalisation of acetaldehyde + ethanol | | [V9] |
| vinegar | ethyl 3-methylbutanoate (ethyl isovalerate) | reported | — | Sherry 0.03–1.1 [V6] | key odorant of Condado de Huelva Reserva [V9] | esterification of AAB-made isovaleric acid | | [V6]; [V9] |
| vinegar | ethyl phenylacetate | reported | — | — | key odorant of Montilla-Moriles PX [V9] | | | [V9] |
| vinegar | 3-oxobutan-2-yl acetate (acetoin acetate) | reported | — | presence [V6] | — | acetylation of acetoin | | [V6] |
| vinegar | hydroxyacetone (acetol) | reported | [V3] 0.049 (wine) → 0.0085 | Sherry 5.34–70 [V6] | — | | | [V3]; [V6] |
| vinegar | guaiacol, vanillin | reported (wood-aged only) | — | vanillin 2.5–4.4 [V6] | key odorants of Condado Reserva / Montilla PX [V9] | oak | | [V6]; [V9] |

## 3. Sourdough (dough / starter, before baking)

**Studies used.** The two SIDA (absolute) studies of flour → sourdough ([S1] wheat, [S2] rye) are closed-access; only their abstracts were opened, which give **directions of change** and OAV statements but no numbers (numbers → table E). The only open absolute dough data found is [S3] (µg/kg, 5-day starter at 15 °C). No open hour-by-hour volatile time course of a sourdough was found.

| Tag | Design | Quantification | Caveat |
|---|---|---|---|
| [S1] Czerny & Schieberle 2002 | Wholemeal and white wheat flour, flour suspensions fermented with LAB; AEDA + SIDA | absolute (abstract only) | Directions: acetic acid, 3-methylbutanal ↑; lipid-derived aldehydes ↓; "no new odorants". |
| [S2] Kirchhoff & Schieberle 2002 | Rye flour (type 1150) → rye sourdough, five flours; AEDA + SIDA, OAV in water/starch | absolute (abstract only) | Directions + OAV > 100 list. |
| [S3] Liszkowska 2025 | Wheat sourdough, **15 °C, 5 days**, 3 *S. cerevisiae* strains × (*L. brevis* B46, *L. brevis* B48, *L. plantarum/pentosus* B56); HS-GC-MS (SIM); paper Table 5 (VOC, µg/kg) and Table 3 (acids, ethanol, g/100 g) | µg/kg as printed (calibration not described in the text I opened) | End point only; 9 combinations give the spread. Acetic 0.38–0.71 g/100 g, ethanol 0.07–0.43 g/100 g. |
| [S4] Liu T 2022 (Foods) | Wheat dough, *F. sanfranciscensis* (LS), *S. cerevisiae* (SC) or both, **30 °C, 12 h**; HS-SPME-GC-MS, Table 1 | peak area ×10⁶ | Attribution by organism; relative only. |
| [S5] Reale 2019 | 28 traditional Irpinian sourdoughs (type I), SPME-GC-MS, Table 2 | relative to IS (4-methyl-2-pentanol) | Presence + spread. |
| [S6] Galoburda 2020 | Triticale sourdough with *L. sanfranciscensis*-based cultures (ready-to-use and two-stage); SPME, Table 1 | relative % | Headspace dominated by ethyl acetate, ethanol, acetic acid. |
| [S7] Guerzoni 2007 | *S. cerevisiae* LBS + *L. sanfranciscensis* LSCE1, stress exposure (abstract) | — | Acid stress → isovaleric, acetic acids and higher alcohols accumulate. |
| [S8] Liu T 2020 (Food Chem) | 10 LAB strains from Chinese sourdough, sourdough volatiles (abstract) | — | Homofermentative → more C>6 aldehydes/ketones; heterofermentative → ethanol + esters. |
| [S9] Wang X 2020 | Type I sourdough, retarded sponge dough 12–24 h, *L. sanfranciscensis* + *K. humilis* dominant (abstract) | — | "Volatile compounds became more abundant with much more esters as sponge retarding time extended." |

### Table B — sourdough

[S3] ranges are min–max over the nine yeast × LAB combinations (µg/kg dough, 15 °C, 5 d); the D3 yeast strain gave the highest values throughout.

| ferment | compound key | tier proposed | time course? (times → µg/kg) | end-point range µg/kg | key-odorant data (FD/OAV) | producer(s) / mechanism | conditions | source (where) |
|---|---|---|---|---|---|---|---|---|
| sourdough | 3-methylbutanal | calibrated (direction ↑, flour → sourdough) | [S1] increased during LAB fermentation of wheat flour; [S2] OAV > 100 in rye sourdough | — | OAV > 100 [S2] | Leu transamination/decarboxylation (yeast Ehrlich; LAB) + flour | wheat [S1], rye [S2] | [S1], [S2] abstracts |
| sourdough | 2-methylbutanal | calibrated (direction ↓) | [S2] decreased flour → rye sourdough | — | — | flour; reduced to alcohol by yeast/LAB | rye | [S2] abstract |
| sourdough | 2-methylpropanal | plausible | | | | Val, Ehrlich | | — |
| sourdough | phenylacetaldehyde | plausible | not in dough sources opened | | | Phe, Ehrlich | | — |
| sourdough | methional | reported | — | — | OAV > 100 in rye flour and rye sourdough [S2]; much higher in wholemeal than white wheat flour [S1] | flour + Met (Ehrlich) | | [S1], [S2]; methionol presence [S5] |
| sourdough | 3-methylbutanol | calibrated (direction ↑) | [S2] "much increased" flour → sourdough | 823–12 838 [S3]; LS alone 0.84 vs SC 35.3 vs LS+SC 28.7 (area) [S4] | — | yeast Ehrlich (Leu); *F. sanfranciscensis* lowers yeast output in co-culture [S4] | 15 °C [S3]; 30 °C 12 h [S4] | [S2]; [S3] T5; [S4] T1 |
| sourdough | 2-methylbutanol | reported | — | 126–2028 [S3] | — | yeast Ehrlich (Ile) | 15 °C | [S3] T5 |
| sourdough | 2-methylpropanol | reported | — | 167–3563 [S3]; SC only (LS nd) [S4] | — | yeast Ehrlich (Val) | | [S3]; [S4]; [S5] |
| sourdough | 2-phenylethanol | reported | — | 15 729–69 598 [S3] | — | yeast Ehrlich (Phe) | 15 °C | [S3] T5; [S5] |
| sourdough | methionol | reported | — | presence [S5] | — | yeast Ehrlich (Met) | | [S5] T2 |
| sourdough | 3-methylbutanoic acid | reported | — | — | OAV > 100 in rye sourdough [S2]; accumulates under acid stress [S7] | Ehrlich oxidative branch, LAB | | [S2], [S7] |
| sourdough | 2-methylpropanoic, 2-methylbutanoic acid | reported | — | presence [S5] | — | Ehrlich | | [S5] T2 |
| sourdough | ethyl acetate | reported (direction ↑ with fermentation time [S9]) | [S9] esters ↑ from 12 to 24 h retarding | 1345–56 907 [S3]; LS alone 9.66, SC 5.38, LS+SC 14.13 (area) [S4] | dominant headspace volatile of triticale sourdough [S6] | heterofermentative LAB (acetate + ethanol) and yeast; chemical | 15 °C [S3]; 30 °C [S4] | [S3]; [S4]; [S6]; [S9] |
| sourdough | isoamyl acetate | reported | — | nd–6.73 [S3] | — | yeast AATase | 15 °C | [S3]; [S5] |
| sourdough | 2-phenylethyl acetate, isobutyl acetate | reported | — | presence [S5] | — | yeast AATase | | [S5] T2 |
| sourdough | ethyl butanoate | reported | — | nd–6.93 [S3] | — | yeast | | [S3]; [S5] |
| sourdough | ethyl hexanoate | reported | — | 4.17–604 [S3] | — | yeast FAEE | | [S3]; [S5] |
| sourdough | ethyl octanoate | reported | — | 0.68–60.7 [S3] | — | yeast FAEE | | [S3]; [S5] |
| sourdough | ethyl decanoate | reported | — | nd–3.73 [S3] | — | yeast FAEE | | [S3]; [S5] |
| sourdough | ethyl 2-methylbutanoate | reported | — | nd–0.61 [S3] | — | yeast | | [S3] |
| sourdough | ethyl 2-methylpropanoate | reported | — | nd–1.73 [S3] | — | yeast | | [S3] |
| sourdough | hexanoic, octanoic acid | reported | — | hexanoic: LS 4.42, SC 2.14, LS+SC 5.43 (area) [S4]; both present [S5] | — | LAB/yeast lipid metabolism | | [S4]; [S5] |
| sourdough | decanoic acid | plausible | | | | yeast | | — |
| sourdough | acetaldehyde | reported | — | presence, nd–13.7 rel. to IS across sourdoughs [S5] | — | yeast PDC; heterofermentative LAB | | [S5] T2 |
| sourdough | diacetyl | calibrated (direction ↑) | [S2] "much increased" flour → rye sourdough | — | OAV > 100 [S2] | LAB citrate/pyruvate (α-acetolactate) | rye | [S2] abstract |
| sourdough | acetoin | reported | — | SC 2.07, LS+SC 0.33, LS nd (area) [S4]; presence [S5] | — | yeast (and LAB) | 30 °C, 12 h | [S4]; [S5] |
| sourdough | 2,3-pentanedione, 2,3-butanediol | plausible | | | | | | — |
| sourdough | ethyl lactate | reported | — | presence [S5] | — | chemical esterification | | [S5] T2 |
| sourdough | hexanal | calibrated (direction ↓) | [S1] lipid-derived aldehydes decreased during LAB fermentation | 100–372 [S3]; LS 2.11, SC 2.08, LS+SC 1.24 (area) [S4] | OAV > 100 in rye **flour** [S2] | flour LOX/autoxidation; reduced to hexanol by LAB/yeast (hexanol up to 2577 µg/kg in [S3]) | 15 °C [S3] | [S1]; [S2]; [S3]; [S4] |
| sourdough | (E)-2-nonenal | calibrated (direction ↓) | [S1] lipid-derived aldehydes decreased | — | high odour activity in wheat flour [S1]; OAV > 100 in rye flour [S2] | flour; LAB reduction (primary study Vermeulen 2007 not opened → E) | | [S1], [S2] |
| sourdough | nonanal | reported | — | presence [S5] | — | flour | | [S5] |
| sourdough | 2-pentylfuran | reported | — | presence [S5] | — | flour linoleate | | [S5] |
| sourdough | 1-octen-3-one | reported (flour-derived) | — | — | highest FD in rye flour [S2] | flour LOX | | [S2] |
| sourdough | 1-octen-3-ol, 3-octanol | reported | — | presence [S5] | — | flour LOX | | [S5] T2 |
| sourdough | (Z)-3-hexenal, (Z)-3-hexenol, (Z)-4-heptenal, 3-octanone | plausible | | | | flour LOX | | — |
| sourdough | 4-vinylguaiacol | plausible | not reported in sources opened | | | ferulic acid decarboxylation (*L. plantarum*, *S. cerevisiae* PAD1/FDC1) | | — (lead in E) |
| sourdough | 4-vinylphenol | plausible | | | | p-coumaric acid decarboxylation | | — |
| sourdough | limonene | reported | — | presence [S5] | — | flour/ingredients | | [S5] |
| sourdough | 2-heptanone, butanoic acid | reported | — | presence [S5] | — | lipid oxidation / LAB | | [S5] T2 |
| sourdough | sotolon (3-hydroxy-4,5-dimethyl-2(5H)-furanone) | reported (flour-derived) | — | — | high odour activity in both wheat flours [S1] | flour | | [S1] abstract |
| sourdough | glucosinolate, allium, tea terpenes, Maillard/pyrazines, furaneol, maltol, 2-AP, lactones, TMA, 4-ethylphenols | drop | no precursor or formed only on baking | | | | | — |
| sourdough | acetic acid | (engine pool) | [S1], [S2] increased | 0.38–0.71 g/100 g [S3] | OAV > 100 [S2] | heterofermentative LAB | | [S1]–[S3] |

**Model implications.** For sourdough the flour is the main aroma source and the microbes mostly *modulate* it ([S1], [S2]): lipid aldehydes (hexanal, (E)-2-nonenal, decadienal) need a first-order microbial reduction term (`c_ij`) with the flour as initial pool; 3-methylbutanol, diacetyl and acetic acid increase. Yeast dominates the Ehrlich alcohols and esters ([S3], [S4]: *F. sanfranciscensis* alone makes almost no 3-methylbutanol or isobutanol), while heterofermentative LAB contribute ethyl acetate and acetic acid. Magnitudes for priors: [S3] (but at 15 °C over 5 days; a 30 °C overnight dough will sit lower).

### Table D — sourdough missing key odorants

| ferment | compound | tier proposed | time course? | end-point range | key-odorant data | producer / mechanism | conditions | source (where) |
|---|---|---|---|---|---|---|---|---|
| sourdough | (E,E)-2,4-decadienal | calibrated (direction ↓) | [S2] decreased flour → sourdough | — | OAV > 100 in rye sourdough [S2]; higher in wholemeal wheat flour [S1] | flour linoleate; LAB reduction | rye, wheat | [S1], [S2] |
| sourdough | vanillin | reported (flour-derived) | — | — | OAV > 100 in rye sourdough [S2]; high in wheat flours [S1] | flour ferulate | | [S1], [S2] |
| sourdough | 1-hexanol | reported | — | nd–2577 [S3] | — | reduction of hexanal by yeast/LAB | 15 °C | [S3] T5 |
| sourdough | (E)-2-hexenal | reported | — | presence [S5] | — | flour LOX | | [S5] |
| sourdough | isoamyl lactate | reported | — | presence [S5] | — | esterification | | [S5] |
| sourdough | γ-decalactone | reported | — | — | overproduced by LAB under oxidative stress [S7] | LAB | | [S7] abstract |

## 4. Koji

**Studies used.** No study of steamed-rice koji with a quantitative 1-octen-3-ol time course could be opened. [J1] gives a *relative* time course on bran substrates; [J2] gives an end point on rice (printed ppm, basis not stated).

| Tag | Design | Quantification | Caveat |
|---|---|---|---|
| [J1] Holt 2026 | *A. oryzae* SSF on wheat bran, rye bran, rapeseed and pumpkin-seed press cake, varying moisture, **30 °C, 70 % RH, to 48 h**; dynamic-headspace GC-MS, untargeted (PARADISe) | relative abundance (clusters, figures) | Direction/timing only; bran not rice. |
| [J2] McCarthy 2026 | Autoclaved short-grain rice, *A. oryzae* RIB40 vs *A. flavus*, sealed Petri dishes, **30 °C, 48 h**; dynamic-headspace GC-MS, Table 1 (2 replicates) | "parts per million" as printed (calibration not described) | End point vs unfermented rice; treat as relative. No 1-octen-3-ol listed (sealed dishes?). |
| [J3] Kataoka 2020 | Rice koji with *A. luchuensis* (black koji) and ΔppoA/ΔppoC; SPME-GC-MS (abstract) | — | 1-octen-3-ol present in rice koji, absent in ΔppoC. |
| [J4] Sandoval 2026 | *A. oryzae* (barley- and red-rice-koji strains), *N. intermedia*, *R. oligosporus* SSF on bread crust ± ryegrass protein, 0/24/48/72 h; SPME-GC-MS with IS | µg/kg (IS-based) in text | Hexanal 180 µg/kg in unfermented bread-crust substrate, declines with SSF time; per-fungus numbers mainly in figures. |

### Table B — koji

[J2] values: *A. oryzae* RIB40 replicate 1 / replicate 2 vs unfermented rice ("ppm" as printed).

| ferment | compound key | tier proposed | time course? (times → µg/kg) | end-point range µg/kg | key-odorant data (FD/OAV) | producer(s) / mechanism | conditions | source (where) |
|---|---|---|---|---|---|---|---|---|
| koji | 1-octen-3-ol | calibrated (relative; bran) | [J1] absent/very low in substrates, increases with time, highest at 48 h | — (rice: present, [J3]; not listed by [J2]) | "character impact compound for koji aroma" (cited in [J1]) | fungal fatty-acid oxygenase/lipoxygenase on linoleic acid (*ppoC* required, [J3]) | 30 °C, 48 h | [J1] Results (cluster 4); [J3] abstract |
| koji | 3-octanone | calibrated (relative; bran) | [J1] increases to 48 h | — | — | C8 oxylipin branch | 30 °C | [J1] cluster 4 |
| koji | 3-octanol | calibrated (relative; bran) | [J1] increases to 48 h; strongest on wheat bran | — | — | C8 oxylipin branch | 30 °C | [J1] cluster 4 |
| koji | 1-octen-3-one | plausible | not reported in sources opened | | | C8 oxylipin | | — |
| koji | 3-methylbutanol | reported | [J1] presence | 138.5 / 200.0 vs 0.23 [J2] | — | fungal Ehrlich (Leu) | 30 °C, 48 h | [J2] T1; [J1] |
| koji | 2-methylpropanol | reported | — | 217.5 / 307.8 vs 0.76 [J2] | — | Ehrlich (Val) | | [J2] T1 |
| koji | 2-methylbutanol | reported | — | presence in the SSF odorant table (fungus not specified per row) [J4] | — | Ehrlich (Ile) | | [J4] table |
| koji | 2-phenylethanol | plausible for *A. oryzae* | — | nd in *A. oryzae* rice, 1.44–2.14 with *A. flavus* [J2]; presence in bread-crust SSF [J4] | — | Ehrlich (Phe) | | [J2] T1; [J4] |
| koji | 3-methylbutanal | reported | [J1] presence | 278.7 / 226.3 vs 0.41 [J2] | — | Ehrlich (Leu) | | [J2] T1; [J1] |
| koji | 2-methylbutanal | reported | — | 137.7 / 104.3 vs 0.16 [J2] | — | Ehrlich (Ile) | | [J2] T1 |
| koji | 2-methylpropanal | reported | — | 660.6 / 577.8 vs 0.34 [J2] | — | Ehrlich (Val) | | [J2] T1 |
| koji | phenylacetaldehyde | reported | [J4] classes it as Maillard + SSF-derived (direction in figure only) | 21.0 / 14.6 vs 0 [J2] | — | Ehrlich (Phe) / Strecker | | [J2] T1; [J4] |
| koji | methional | reported | — | 2.71 / 1.32 vs 0 [J2] | — | Ehrlich (Met) | | [J2] T1 |
| koji | methionol | plausible | | | | | | — |
| koji | 3-methylbutanoic, 2-methylpropanoic, 2-methylbutanoic acid | reported | [J1] present (late, amino-acid-derived phase) | 3-MB acid 0.23 / 1.0; 2-MP acid 0.59 / 0.44 [J2] | — | aldehyde oxidation | | [J1]; [J2] T1 |
| koji | ethyl acetate | calibrated (relative; transient) | [J1] acetate esters enriched mid-fermentation, decline at 48 h | 0.78 / 1.39 vs 0.08 [J2] | — | fungal AATase; esterase at late stage | 30 °C | [J1] Discussion; [J2] T1 |
| koji | isoamyl acetate | calibrated (relative; transient) | [J1] as above | — | — | idem | | [J1] |
| koji | ethyl 2-methylpropanoate, ethyl 2-methylbutanoate | reported | — | 0.89 / 2.52 and 0.25 / 0.48 [J2] | — | | | [J2] T1 |
| koji | ethyl hexanoate, ethyl octanoate | reported | — | 0.34 / 0.26 and 0.14 / 0.15 [J2] | — | | | [J2] T1 |
| koji | ethyl decanoate | plausible | — | *A. flavus* only [J2] | | | | [J2] |
| koji | isobutyl acetate, ethyl butanoate, 2-phenylethyl acetate, MCFA | plausible | | | | | | — |
| koji | acetaldehyde | reported | — | 8.92 / 12.02 vs 0.44 [J2] | — | fungal PDC | | [J2] T1 |
| koji | diacetyl | reported | [J1] high-moisture cluster | — | — | redox overflow (high moisture) | 30 °C | [J1] cluster 5 |
| koji | acetoin | reported | — | 2.83 / 1.90 vs 0 [J2] | — | overflow | | [J2] T1 |
| koji | 2,3-pentanedione | reported | — | 0.56 / 0.25 vs 0 [J2] | — | overflow | | [J2] T1 |
| koji | 2,3-butanediol | reported | [J4] classes it as SSF-derived | 5.79 / 6.15 (+ R-isomer 7.83 / 10.87) vs 0 [J2] | — | overflow | | [J2] T1; [J4] |
| koji | hexanal | calibrated (direction ↓ on bran/bread; ~flat on rice) | [J1] linear aldehydes "declined rapidly in cereal substrates"; [J4] 180 µg/kg (unfermented bread-crust + water) falling with SSF time | rice: 4.15 / 8.34 vs 4.05 [J2] | — | substrate lipid oxidation, consumed/reduced by fungus | 30–32 °C | [J1]; [J2] T1; [J4] text |
| koji | nonanal | reported | — | 0.74 / 0.87 vs 0.54 [J2] | — | substrate | | [J2] T1 |
| koji | 2-pentylfuran | reported (declines on bran) | [J1] cluster 1 (declining) | 0.28 / 0.28 vs 0.19 [J2] | — | substrate linoleate | | [J1]; [J2] |
| koji | (E)-2-nonenal, (Z)-3-hexenal, (Z)-3-hexenol, (Z)-4-heptenal | plausible | | | | substrate lipid | | — |
| koji | 2-heptanone, 2-nonanone | calibrated (relative; bran) | [J1] methyl ketones increase to 48 h (strongest on wheat bran) | 2-heptanone 0.16 / 0.17 vs 0.09 [J2] | — | fungal β-oxidation of fatty acids (methyl-ketone pathway) | 30 °C | [J1] cluster 4; [J2] |
| koji | 4-vinylguaiacol | reported | [J1] phenolics transiently enriched mid-fermentation | 0.29 / 0.39 vs 0 [J2] | — | ferulic acid decarboxylation | | [J1]; [J2] T1 ("2-methoxy-4-vinylphenol") |
| koji | 4-ethylguaiacol | reported (high moisture only) | [J1] cluster 5 | — | — | (reduction; organism unclear) | | [J1] |
| koji | 2-acetyl-1-pyrroline | plausible | not reported in koji sources opened | | | rice precursor; volatilisation | | — |
| koji | isothiocyanates / nitriles | drop for rice/barley koji (rapeseed only) | [J1] rapeseed press cake only | | | glucosinolates | | [J1] |
| koji | sulfur (DMS, DMDS, DMTS, MeSH), terpenoids, pyrazines, furaneol, maltol, HEMF, sotolon, lactones, TMA | drop (koji stage) | | | | | | — |
| koji | ethanol | (engine pool) | — | 2799 / 4450 vs 109 [J2] | — | *A. oryzae* fermentative metabolism in sealed dishes | | [J2] T1 |

**Model implications.** The koji-specific signal is the C8 oxylipin family (1-octen-3-ol, 3-octanone, 3-octanol) plus methyl ketones, all rising monotonically to 48 h ([J1]) — a growth-linked `a_ij·μX` term for *A. oryzae* on a linoleate precursor pool fits. Strecker/Ehrlich aldehydes (2-methylpropanal, 3-methylbutanal, 2-methylbutanal) are large in [J2] and should be tied to the free-amino-acid pool released by *A. oryzae* proteases. Hexanal decays from the substrate pool. Absolute magnitudes for rice koji remain the main gap.

### Table D — koji missing key odorants

| ferment | compound | tier proposed | time course? | end-point range | key-odorant data | producer / mechanism | conditions | source (where) |
|---|---|---|---|---|---|---|---|---|
| koji | 3-octen-2-one | reported | — | 0.20 / 0.20 vs 0.05 [J2] | flagged as "mushroom or earthy", pleasant marker of *A. oryzae* rice [J2] | fungal lipid | 30 °C, 48 h | [J2] T1 + Discussion |
| koji | 2-methyl-3-buten-2-ol | reported | — | 1.32 / 1.30 vs 0.08 [J2] | flagged as fruity/green marker [J2] | — | | [J2] |
| koji | 2-undecanone | calibrated (relative) | [J1] increases to 48 h | — | — | methyl-ketone pathway | | [J1] |
| koji | 1-heptanol | reported | — | 13.5 / 22.5 vs 0 [J2] | — | | | [J2] T1 |
| koji | acetoin acetate (3-oxobutan-2-yl acetate) | reported | [J1] high-moisture cluster | — | — | acetylation of acetoin | | [J1] |

## E. Unverified leads

None of these values is used as data above.

| lead | why I believe it | what to search / open |
|---|---|---|
| Absolute SIDA concentrations of 3-methylbutanal, 3-methylbutanol, diacetyl, acetic acid, hexanal, (E)-2-nonenal, (E,E)-2,4-decadienal, methional, vanillin in flour vs sourdough (wheat and rye) | [S1], [S2] abstracts state they were quantified by SIDA and give directions/OAV > 100 | Full text: Czerny & Schieberle 2002, JAFC 50:6835 (Tables); Kirchhoff & Schieberle 2002, JAFC 50:5378 (Tables) — closed access (Unpaywall: no OA copy) |
| LAB reduce (E)-2-nonenal and (E,E)-2,4-decadienal in sourdough (rates, strain dependence incl. *L. sanfranciscensis*, *L. plantarum*) | Title of Vermeulen, Czerny, Gänzle, Schieberle, Vogel 2007, J Cereal Sci 45:78–87, doi 10.1016/j.jcs.2006.07.002 | Open the paper (ScienceDirect blocked here) |
| Acetification time course (acetaldehyde, ethyl acetate, acetoin, fusel alcohols, ethyl lactate vs time/acidity) in submerged wine vinegar | [V1], [V2] abstracts | Full text of Baena-Ruano 2010 (JSFA 90:2675, figures) and Morales 2001 (JSFA 81:611, tables) |
| Sherry-vinegar concentrations with OAVs (diacetyl, isoamyl acetate, ethyl isobutyrate, isovaleric acid, sotolon, ethyl acetate) | [V8] abstract ("58 compounds quantified", OAVs) | Callejón 2008, JAFC 56:8086, quantitative table; also Aceña 2011 JAFC 59:4062 (HS-SPME-GC-O of Sherry vinegar) |
| Volatile time course D0–D10 of *A. pasteurianus* acetification (isoamyl acetate, acetoin, 3-methylbutanol, ethyl lactate, µg/L IS-equivalent) | [V5] says the data are in Tables S5–S6 | MDPI supplementary for doi 10.3390/foods14162905 (403 from here) |
| Acetification metabolites in mg/L for three submerged profiles (Table S3) | [V11] text | MDPI supplementary for doi 10.3390/foods14010056 |
| "Acetoin and ethyl acetate can reach > 1000 and > 3500 mg/L in aged vinegars" | Secondary statement in [V13] (its refs 25–27) | Follow [V13] refs 25–27 |
| Per-compound kombucha concentrations (absolute, calibration-based) for acetaldehyde, diacetyl, acetoin, ethyl acetate, isobutanol, isoamyl alcohol by consortium and day | [K3] quantified 32 compounds with calibration curves; numbers only in figures/supplement | Tran et al. 2022 Front Microbiol supplementary material |
| Black-tea kombucha key odorants by OAV: benzaldehyde, linalool, phenylethyl alcohol, hexanal, nonanal | Web-search snippet attributing this to a kombucha study; source not identified/opened | Identify primary paper (search "black tea kombucha OAV benzaldehyde linalool nonanal") |
| Absolute 1-octen-3-ol (and 3-octanone, 3-octanol, 1-octen-3-one) in rice koji vs koji-making time (0–48 h, 30–40 °C) | [J1] cites "Feng et al., 2013" for 1-octen-3-ol as koji character-impact compound; [J3] shows *ppoC*-dependent 1-octen-3-ol in rice koji | Feng et al. 2013 (as cited in [J1]); J Brewing Soc Japan / J Biosci Bioeng studies on koji-making aroma; Kataoka 2020 full text for amounts |
| 2-acetyl-1-pyrroline in steamed rice before/after koji making | Rice precursor; no koji study opened reports it | Search "2-acetyl-1-pyrroline koji" / "aromatic rice koji 2-AP" |
| 4-vinylguaiacol formation in wheat sourdough by *L. plantarum* / yeast (µg/kg) | Known ferulic-acid decarboxylase activity; no sourdough number opened | Search "sourdough 4-vinylguaiacol ferulic acid decarboxylase Lactobacillus plantarum" |

## Sources

All opened as full text (HTML via PMC/publisher) unless marked "(abstract)".

Kombucha
- [K1] Suffys S, Richard G, Burgeon C, Werrie P-Y, Haubruge E, Fauconnier M-L, Goffin D. 2023. Characterization of aroma active compound production during kombucha fermentation: towards the control of sensory profiles. *Foods* 12(8):1657. doi:10.3390/foods12081657. Used: Methods; Table 1 (VOC, "ppm"); Table 2 (OAV).
- [K2] Wu X, Zhang Y, Zhang B, Tian H, Liang Y, Dang H, Zhao Y. 2023. Dynamic changes in microbial communities, physicochemical properties, and flavor of kombucha made from Fu-brick tea. *Foods* 12(23):4242. doi:10.3390/foods12234242. Used: Table 2 (physicochemical), Table 3 (VOC, ng/g).
- [K3] Tran T, Billet K, Torres-Cobos B, Vichi S, Verdier F, Martin A, Alexandre H, Grandvalet C, Tourdot-Maréchal R. 2022. Use of a minimal microbial consortium to determine the origin of kombucha flavor. *Front Microbiol* 13:836617. doi:10.3389/fmicb.2022.836617. Used: Methods (calibration), Results text (concentration ranges), Table 2 (metabolite list/signatures).
- [K4] Ferremi Leali N, Binati RL, Martelli F, Gatto V, Luzzini G, Salini A, Slaghenaufi D, Fusco S, Ugliano M, Torriani S, Salvetti E. 2022. Reconstruction of simplified microbial consortia to modulate sensory quality of kombucha tea. *Foods* 11(19):3045. doi:10.3390/foods11193045. Used: Methods; Results/Discussion text (µg/L values); Table 2.
- [K5] Meng Y, Wang X, Li Y, Chen J, Chen X. 2024. Microbial interactions and dynamic changes of volatile flavor compounds during the fermentation of traditional kombucha. *Food Chem* 430:137060. doi:10.1016/j.foodchem.2023.137060. (abstract)
- [K6] Sales AL, Cunha SC, Morgado J, Cruz A, Santos TF, Ferreira IMPLVO, Fernandes JO, Miguel MAL, Farah A. 2023. Volatile, microbial, and sensory profiles and consumer acceptance of coffee cascara kombuchas. *Foods* 12(14):2710. doi:10.3390/foods12142710. Used: Methods; Table 2 (black-tea kombucha presence/absence D0–D9).

Vinegar
- [V1] Baena-Ruano S, Santos-Dueñas IM, Mauricio JC, García-García I. 2010. Relationship between changes in the total concentration of acetic acid bacteria and major volatile compounds during the acetic acid fermentation of white wine. *J Sci Food Agric* 90(15):2675–2681. doi:10.1002/jsfa.4139. (abstract)
- [V2] Morales ML, Tesfaye W, García-Parrilla MC, Casas JA, Troncoso AM. 2001. Sherry wine vinegar: physicochemical changes during the acetification process. *J Sci Food Agric* 81:611–619. doi:10.1002/jsfa.853. (abstract, via Crossref)
- [V3] Es-sbata I, Castro R, Carmona-Jiménez Y, Zouhair R, Durán-Guerrero E. 2022. Influence of different bacteria inocula and temperature levels on the chemical composition and antioxidant activity of prickly pear vinegar produced by surface culture. *Foods* 11(3):303. doi:10.3390/foods11030303. Used: Methods; Table 1 (juice/wine/vinegar volatiles, mean relative areas).
- [V4] Bagnulo E, Trevisan G, Strocchi G, Caratti A, Tapparo G, Felizzato G, Cordero C, Liberto E. 2025. Integrated characterization of *Phoenix dactylifera* L. fruits and their fermented products: volatilome evolution and quality parameters. *Molecules* 30(14):3029. doi:10.3390/molecules30143029. Used: Table 1 (normalized response), Results text (acetoin 855 ± 150 mg/L).
- [V5] Chen S, Wang Y, Sun X, Han Z, Jiang Q, Gao L, Zhang R. 2025. Investigation on precursor aromas and volatile compounds during the fermentation of blackened pear vinegar. *Foods* 14(16):2905. doi:10.3390/foods14162905. Used: Methods; Results § 3.4 text (OAVs, ethanol).
- [V6] Durán-Guerrero E, Castro R, García-Moreno MV, Rodríguez-Dodero MC, Schwarz M, Guillén-Sánchez D. 2021. Aroma of Sherry products: a review. *Foods* 10(4):753. doi:10.3390/foods10040753. Used: Table 3 (Sherry vinegars; secondary).
- [V7] Callejón RM, Morales ML, Troncoso AM, Silva Ferreira AC. 2008. Targeting key aromatic substances on the typical aroma of Sherry vinegar. *J Agric Food Chem* 56(15):6631–6639. doi:10.1021/jf703636e. (abstract)
- [V8] Callejón RM, Morales ML, Ferreira AC, Troncoso AM. 2008. Defining the typical aroma of Sherry vinegar: sensory and chemical approach. *J Agric Food Chem* 56(17):8086–8095. doi:10.1021/jf800903n. (abstract)
- [V9] Ríos-Reina R, Segura-Borrego MP, Morales ML, Callejón RM. 2020. Characterization of the aroma profile and key odorants of the Spanish PDO wine vinegars. *Food Chem* 311:126012. doi:10.1016/j.foodchem.2019.126012. (abstract)
- [V10] Palacios V, Valcárcel M, Caro I, Pérez L. 2002. Chemical and biochemical transformations during the industrial process of Sherry vinegar aging. *J Agric Food Chem* 50(15):4221–4225. doi:10.1021/jf020093z. (abstract)
- [V11] Román-Camacho JJ, Santos-Dueñas IM, García-García I, García-Martínez T, Peinado RA, Mauricio JC. 2024. Correlating microbial dynamics with key metabolomic profiles in three submerged culture-produced vinegars. *Foods* 14(1):56. doi:10.3390/foods14010056. Used: Table 1 (process), Results text (correlations).
- [V12] OuYang Y, Zou S, Liu P, Xie L, Xiao Y, Wang Y, Wu G, Liu J, Liu B, Gao B, Zhu D. 2025. Synthetic microbial consortium enhances acetoin production and functional quality of citrus vinegar via metabolic and process optimization. *Front Microbiol* 16:1664794. doi:10.3389/fmicb.2025.1664794. Used: abstract numbers.
- [V13] Plioni I, Bekatorou A, Terpou A, Mallouchos A, Plessas S, Koutinas AA, Katechaki E. 2021. Vinegar production from Corinthian currants finishing side-stream: development and comparison of methods based on immobilized acetic acid bacteria. *Foods* 10(12):3133. doi:10.3390/foods10123133. Used: Methods; Table 3 (normalized area %).
- [V14] Cejudo-Bastante C, Durán-Guerrero E, García-Barroso C, Castro-Mejías R. 2018. Comparative study of submerged and surface culture acetification process for orange vinegar. *J Sci Food Agric* 98(3):1052–1060. doi:10.1002/jsfa.8554. (abstract)

Sourdough
- [S1] Czerny M, Schieberle P. 2002. Important aroma compounds in freshly ground wholemeal and white wheat flour — identification and quantitative changes during sourdough fermentation. *J Agric Food Chem* 50(23):6835–6840. doi:10.1021/jf020638p. (abstract)
- [S2] Kirchhoff E, Schieberle P. 2002. Quantitation of odor-active compounds in rye flour and rye sourdough using stable isotope dilution assays. *J Agric Food Chem* 50(19):5378–5385. doi:10.1021/jf020236h. (abstract)
- [S3] Liszkowska W, Motyl I, Pielech-Przybylska K, Dziekońska-Kubczak U, Berłowska J. 2025. Mixed culture of yeast and lactic acid bacteria for low-temperature fermentation of wheat dough. *Molecules* 30(1):112. doi:10.3390/molecules30010112. Used: Methods; Table 3 (acids, ethanol); Table 5 (VOC, µg/kg).
- [S4] Liu T, Shi Y, Li Y, Yi H, Gong P, Lin K, Zhang Z, Zhang L. 2022. The mutual influence of predominant microbes in sourdough fermentation: focusing on flavor formation and gene transcription. *Foods* 11(15):2373. doi:10.3390/foods11152373. Used: Methods; Table 1 (peak areas).
- [S5] Reale A, Di Renzo T, Boscaino F, Nazzaro F, Fratianni F, Aponte M. 2019. Lactic acid bacteria biota and aroma profile of Italian traditional sourdoughs from the Irpinian area in Italy. *Front Microbiol* 10:1621. doi:10.3389/fmicb.2019.01621. Used: Methods; Table 2.
- [S6] Galoburda R, Straumite E, Sabovics M, Kruma Z. 2020. Dynamics of volatile compounds in triticale bread with sourdough: from flour to bread. *Foods* 9(12):1837. doi:10.3390/foods9121837. Used: abstract and Table 1 caption (relative %).
- [S7] Guerzoni ME, Vernocchi P, Ndagijimana M, Gianotti A, Lanciotti R. 2007. Generation of aroma compounds in sourdough: effects of stress exposure and lactobacilli–yeasts interactions. *Food Microbiol* 24(2):139–148. doi:10.1016/j.fm.2006.07.007. (abstract)
- [S8] Liu T, Li Y, Yang Y, Yi H, Zhang L, He G. 2020. The influence of different lactic acid bacteria on sourdough flavor and a deep insight into sourdough fermentation through RNA sequencing. *Food Chem* 307:125529. doi:10.1016/j.foodchem.2019.125529. (abstract)
- [S9] Wang X, Zhu X, Bi Y, Zhao R, Nie Y, Yuan W. 2020. Dynamics of microbial community and changes of metabolites during production of type I sourdough steamed bread made by retarded sponge-dough method. *Food Chem* 330:127316. doi:10.1016/j.foodchem.2020.127316. (abstract)

Koji
- [J1] Holt S, Melzer F, Persico Pivcevic CP, Olsen K, Nielsen DS, Tirelli L. 2026. Substrate dependent growth conditions and moisture dynamics drive aroma development in solid-state *Aspergillus oryzae* (koji) fermentation. *Front Microbiol* 17:1829344. doi:10.3389/fmicb.2026.1829344. Used: abstract; Methods; Results (VOC clusters 1, 4, 5); Discussion.
- [J2] McCarthy CO, Choi D, Nolden AA, Decker EA, Yu JH, Gibbons JG. 2026. Divergent volatile metabolomes and flavor attributes in rice fermented by *Aspergillus oryzae* and *Aspergillus flavus*. *Front Fungal Biol* 6:1666687. doi:10.3389/ffunb.2025.1666687. Used: Methods; Table 1 ("ppm").
- [J3] Kataoka R, Watanabe T, Yano S, Mizutani O, Yamada O, Kasumi T, Ogihara J. 2020. *Aspergillus luchuensis* fatty acid oxygenase *ppoC* is necessary for 1-octen-3-ol biosynthesis in rice koji. *J Biosci Bioeng* 129(2):192–198. doi:10.1016/j.jbiosc.2019.08.010. (abstract)
- [J4] Sandoval JF, Parker JK, Gallagher J, Rodriguez-Garcia J, Whiteside K, Bryant DN. 2026. Transforming the odor profile of perennial ryegrass protein and surplus bread crusts through solid-state fermentation. *npj Sci Food* 10:197. doi:10.1038/s41538-026-00831-6. Used: Methods; Results text (hexanal µg/kg); odorant table.
