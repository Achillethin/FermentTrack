# 05 — Mechanism-template parameters (table C)

Research slice: class-level kinetics for the aroma tracer templates (spec § 4.1–4.2).
Rules of BRIEF.md apply: every value below was read in the source named in the row
(full text or abstract); figure read-offs are marked "fig., ±~10 %". Values recalled but not
opened are in table E only.

Tracer term legend: **a** = a_ij (per g biomass made), **b** = b_ij (per g substrate fermented),
**r** = r_i (precursor release, 1/h), **P0** = precursor pool initial value (ingredient prior),
**k0/Q10** = abiotic loss, **c** = c_ij (conversion by organism, per g cells per h),
**chem** = chemistry term.

Status: done (2026-10-05). Usable class parameters: Ehrlich, esters, pyruvate overflow (yeast acetaldehyde, citrate split), abiotic ester hydrolysis, glucosinolate and SMCSO/alliin pools, ferulic acid pool, Henry constants. Mostly qualitative (rates are estimates, table E): LOX/mould C8, tea glycosides, HCA decarboxylation rates, slow Maillard/Strecker, open-vessel k0, diacetyl chemistry.

---

## 1. Ehrlich pathway (yeast; fusel aldehydes → alcohols / acids)

**Structural findings that decide the tracer form**

- Branched-chain fusel alcohols are mostly *de novo* products of sugar metabolism, not of medium
  amino acids: with ¹³C-leucine / ¹³C-valine (each 1.3 % of YAN, fully consumed), isotopic
  enrichment of isoamyl alcohol was only 2–8 % and of isobutanol 5–15 % across 70–425 mg N/L, and
  ">90 % of the acids and higher alcohols (and their acetate ester derivatives) were derived from
  intermediates produced by the carbon central metabolism" (Rollero et al. 2017, Abstract; Results,
  Figs 3–6). **→ model isoamyl alcohol / isobutanol as b_ij (per g sugar fermented), not as
  precursor-limited r_i·P_i.** The free-amino-acid pool modulates the yield (below) but does not
  cap it, which matters for nitrogen-poor media (tea, brine).
- Yield vs nitrogen is non-monotonic, maximum at moderate YAN (~140–250 mg N/L) (Rollero 2017
  Discussion; Godillot 2023 Table 2 and § 3.1.2.1).
- Reduction vs oxidation split (Hazelwood et al. 2008, section "Reduction or oxidation"):
  fermentative glucose batch cultures convert amino acids "almost entirely" to fusel alcohol;
  for phenylalanine ~90 % 2-phenylethanol and <10 % phenylacetate; anaerobic: "almost complete
  conversion of phenylalanine to phenylethanol"; aerobic glucose-limited chemostat (respiratory):
  "predominantly to fusel acids" with very low fusel alcohols. **→ alcohol:acid split ≈ 0.9:0.1
  for fermentative yeast (Crabtree, sugar excess) ; shift toward acid only in respiratory
  conditions** (relevant to kombucha's aerobic surface, but no number for mixed regimes).
- Higher alcohols are weakly volatile: "their losses by evaporation are negligible" under CO₂
  stripping in 10 L wine fermenters (Godillot 2023, § 3.1.2) → k0 ≈ 0 for fusel alcohols.

**Table C — Ehrlich**

| template | parameter | value | units | spread | organism / conditions | source (where) | maps to |
|---|---|---|---|---|---|---|---|
| Ehrlich | isoamyl alcohol (3-methylbutanol + 2-methylbutanol as assayed) final, total production | 84.6–144.1 (group means) | mg/L at 200 g/L sugar fermented | group SD 9–49 mg/L; overall ~85–145 | *S. cerevisiae* EC1118, synthetic must 200 g/L glc+fru, pH 3.3, 18–28 °C, YAN 70–210 + 50–150 mg N/L added | Godillot et al. 2023, Table 2 (bottom, total production) | b (÷ 200 g sugar → **0.42–0.72 mg/g sugar**, derived) |
| Ehrlich | isobutanol (2-methylpropanol) final, total production | 35.4–79.9 (group means) | mg/L at 200 g/L sugar | SD 6.5–36.7 | same | Godillot 2023, Table 2 | b (**0.18–0.40 mg/g sugar**, derived) |
| Ehrlich | isobutanol temperature effect | 35.4 (18 °C) → 60.1 (23 °C) → 79.9 (28 °C) | mg/L | SD 6.5, 19.8, 27.4 | same | Godillot 2023, Table 2 | b(T): ≈ ×2.3 per 10 °C (derived) |
| Ehrlich | isoamyl alcohol temperature effect | 106 (18 °C), 118 (23 °C), 114 (28 °C) | mg/L | SD 17–49 | same | Godillot 2023, Table 2 | b(T): ≈ flat (optimum 23 °C) |
| Ehrlich | isoamyl alcohol vs YAN | 109 (70), 126 (140), 98 (210 mg N/L) | mg/L | SD 11–37 | same | Godillot 2023, Table 2 | b modulated by free-AA pool (non-monotonic) |
| Ehrlich | propanol (threonine/2-oxobutanoate route; N marker) | 33.8–57.6 | mg/L | SD 6–14 | same; rises with added N | Godillot 2023, Table 2 | b (0.17–0.29 mg/g, derived); not on candidate list |
| Ehrlich | isobutanol, low vs high phytosterol | 0.339 → 0.540 | mM | single conditions | EC1118, SM425, 24 °C, 2 vs 8 mg/L phytosterols | Rollero 2017, Results ("Overall, the phytosterol availability…") | b (lipid modulation ×1.2–1.6) |
| Ehrlich | fraction of fusel alcohol from exogenous Leu/Val | isoamyl alcohol 2–8 %; isobutanol 5–15 % | % ¹³C enrichment | across 70–425 mg N/L and 2–8 mg/L phytosterol | EC1118, 24 °C, synthetic must | Rollero 2017, Results, Figs 3–6 | justifies b over r·P |
| Ehrlich | alcohol : acid split (fermentative) | ≈ 90 : <10 (Phe → 2-PE : phenylacetate) | mol/mol | qualitative elsewhere | *S. cerevisiae* batch on glucose | Hazelwood et al. 2008, "Reduction or oxidation" section | split of b (or of c for aldehyde) |
| Ehrlich | evaporation of higher alcohols | negligible | — | — | CO₂-stripped 10 L tanks, 18–28 °C | Godillot 2023, § 3.1.2 | k0 ≈ 0 |

Gaps (Ehrlich): no opened source gives per-g-sugar yields of 2-phenylethanol, methionol, the fusel
aldehydes (transient) or the branched fusel acids for *S. cerevisiae*, nor any yield for
*K. humilis* / *Z. rouxii* in a defined medium → table E. *K. marxianus* relative 2-PE output is in § 2.

---

## 2. Yeast esters and medium-chain fatty acids

**Structural findings**

- Acetate esters are made from the corresponding alcohol + acetyl-CoA (Atf1/Atf2); their
  ¹³C-labelling equals that of the parent fusel alcohol (Rollero 2017, Results, Figs 4, 6) →
  ester flux can be written as a fraction of the parent-alcohol flux. Godillot 2023 measured that
  fraction directly: **isoamyl acetate / isoamyl alcohol (molar, total production) = 0.0062–0.0150**,
  increasing with YAN (0.0079 at 70 → 0.0143 at 210 mg N/L) and with N added (0.0062 → 0.0150),
  with no significant temperature effect (Table 2; § 3.2.4).
- MCFA ethyl esters are limited by acyl-CoA (fatty-acid) supply, not by Eeb1/Eht1 expression
  (Saerens et al. 2008, Abstract) → b_ij per g sugar with lipid/UFA modulation; more UFA in the
  medium lowers ethyl ester production (same abstract).
- Release to the medium falls with chain length: ~100 % ethyl hexanoate, 54–68 % ethyl octanoate,
  8–17 % ethyl decanoate (Saerens et al. 2010, Introduction, citing Nykänen & Nykänen 1977) →
  multiply b by this "excreted fraction".
- Temperature: conflicting direction across sources. Godillot 2023: total *production* (liquid +
  gas) of ethyl hexanoate/octanoate falls 18 → 28 °C (biological, not only evaporative;
  § 3.1.2.4–5). Saerens 2008 (Abstract): higher temperature → *greater* ethyl octanoate and
  decanoate (beer-type conditions). Use a wide prior on the T-slope, centred near zero.
- Evaporative loss with CO₂ stripping is large for esters: isoamyl acetate lost ~14 % at 18 °C and
  ~30 % at 28 °C; ethyl hexanoate/octanoate up to 60 % at 28 °C (Godillot 2023, § 3.1.2.3–3.1.2.5,
  Table 2; at 30 °C, 30 % acetate esters and 50 % ethyl esters per Mouret et al. 2014a as cited in
  Godillot's Introduction — secondary).

**Table C — esters / MCFA**

| template | parameter | value | units | spread | organism / conditions | source (where) | maps to |
|---|---|---|---|---|---|---|---|
| esters | isoamyl acetate, total production | 1.22–1.94 (group means) | mg/L at 200 g/L sugar | SD 0.23–0.71 | *S. cerevisiae* EC1118, synthetic must, 18–28 °C, YAN 70–210 (+50–150) mg N/L | Godillot 2023, Table 2 (bottom) | b (**0.006–0.010 mg/g sugar**, derived) |
| esters | isoamyl acetate vs T (total) | 1.32 (18 °C), 1.78 (23 °C), 1.47 (28 °C) | mg/L | SD 0.23–0.51 | same | Godillot 2023, Table 2 | b(T): optimum ~23 °C |
| esters | isoamyl acetate : isoamyl alcohol | 0.0062–0.0150 | mol/mol (total production) | SD 0.003–0.005 | same; rises with N | Godillot 2023, Table 2 (column "Ratio IsoA") | ester flux = ratio × parent-alcohol flux |
| esters | ethyl hexanoate, total production | 0.42–0.58 (group means) | mg/L at 200 g/L sugar | SD 0.05–0.12 | same | Godillot 2023, Table 2 | b (**0.0021–0.0029 mg/g**, derived) |
| esters | ethyl octanoate, total production | 0.39–0.63 (group means) | mg/L at 200 g/L sugar | SD 0.03–0.19 | same | Godillot 2023, Table 2 | b (**0.0019–0.0032 mg/g**, derived) |
| esters | ethyl hexanoate vs T (total) | 0.578 (18), 0.520 (23), 0.417 (28 °C) | mg/L | SD 0.05–0.08 | same | Godillot 2023, Table 2 | b(T): ≈ −28 % per 10 °C (derived) |
| esters | evaporative loss share (CO₂-stripped) | isoamyl acetate 14 % (18 °C) – 30 % (28 °C); ethyl hexanoate/octanoate up to 60 % (28 °C) | % of total production | — | 10 L tanks, CO₂ from 200 g/L sugar | Godillot 2023, § 3.1.2.3–5 | loss ∝ CO₂ flow (see § 11) |
| esters | excreted fraction | ethyl hexanoate ~100 %; ethyl octanoate 54–68 %; ethyl decanoate 8–17 % | % of synthesised | range | *S. cerevisiae* | Saerens et al. 2010, Introduction (citing Nykänen & Nykänen 1977) | multiplier on b |
| esters | beer concentration ranges | ethyl acetate 8–32; isoamyl acetate 0.3–3.8; 2-phenylethyl acetate 0.10–0.73; ethyl hexanoate 0.05–0.21; ethyl octanoate 0.04–0.53 | mg/L | range | lager beer | Saerens 2010, Table 1 (Meilgaard 1975; Dufour & Malcorps 1994) | sanity bounds for b |
| esters | wine concentration ranges | ethyl acetate 22.5–63.5; isoamyl acetate 0.1–3.4; isobutyl acetate 0.01–1.6; 2-phenylethyl acetate 0–18.5; ethyl butanoate 0.01–1.8; ethyl hexanoate 0.03–3.4; ethyl octanoate 0.05–3.8; ethyl decanoate 0–2.1 | mg/L | range | wine | Saerens 2010, Table 2 (Swiegers & Pretorius 2005) | sanity bounds for b |
| esters | ethyl acetate, *K. marxianus*, aerobic, iron-sufficient (basal) | 0.024 | g/g glucose | single run | *K. marxianus* DSM 5422, 20 g/L glucose mineral medium, aerated 1 L reactor, DO ≥ 40 % | Hoffmann et al. 2021, Table 1 and Results (reference runs) | b (**24 mg/g sugar**) |
| esters | ethyl acetate, *K. marxianus*, O₂-limited / Fe-limited | 0.042 / 0.182 | g/g glucose | single runs | same, induction by O₂ or Fe limitation | Hoffmann 2021, Table 1 | b (upper tail) |
| esters | max biomass-specific ethyl acetate synthesis | 502 (Fe-limited); 38 (basal) | mg/(g biomass · h) | — | *K. marxianus* DSM 5422 | Hoffmann 2021, Results | cap on b·v |
| esters | acetaldehyde yield, *K. marxianus* Fe-/O₂-limited | 0.016 / 0.024 | g/g glucose | — | same | Hoffmann 2021, Table 1 | b (acetaldehyde) |
| esters | *K. marxianus* vs *S. cerevisiae* in cider (relative) | ethyl acetate ×9–12; 2-phenylethanol ×0.3–0.5; isoamyl acetate ×0.9–1.9 | ratio of HS-SPME µg/L | triplicates | Fuji apple juice, static; *K. marxianus* Fim-1 vs *S. cerevisiae* S288C and SY | Zhang et al. 2022, Table 1 | species multiplier on b (semi-quantitative) |

MCFA (hexanoic, octanoic, decanoic acid): the only opened source with values (Liu et al. 2021,
Table 2 — 24–48 / 22–99 / 12–77 mg/L in Cabernet Sauvignon wines, HS-SPME) is an order of magnitude
above usual wine levels; **not used** — see table E.

---

## 3. Pyruvate overflow: acetaldehyde, diacetyl, acetoin, 2,3-butanediol

**Structural findings**

- Citrate → oxaloacetate → pyruvate; the extra pyruvate goes either to lactate or (via
  α-acetolactate) to acetoin/diacetyl/butanediol. In four *L. lactis* biovar *diacetylactis*
  strains, 50–70 % (molar) of citrate- or pyruvate-derived carbon went to lactate and the remaining
  30–50 % mainly to α-acetolactate or acetoin; "Diacetyl was not found as a direct metabolite of
  citrate or pyruvate metabolism" (Verhue & Tjan 1991, Abstract) → model diacetyl as **chem** from
  an α-acetolactate pool, not as b.
- The acetoin/butanediol route switches on under mild aeration or excess pyruvate from citrate;
  homolactic at high growth rate, low pH, high lactose (Starrenburg & Hugenholtz 1991, Abstract).
  Citrate utilisation is maximal at pH 5.5–6.0 for *L. lactis* and *Leuconostoc* (same).
- *Leuconostoc*: at pH 4.3 (resting cells) "all of the citrate utilized was recovered as acetoin";
  9× more acetoin at initial pH 4.5 than 6.3; 10 mM glucose or lactose "totally inhibited acetoin
  production" (Cogan et al. 1981, Abstract) → *Leuconostoc* acetoin is pH-gated and sugar-repressed;
  in sugar-rich vegetable ferments expect ~0 until sugar is gone.
- Yeast acetaldehyde: early peak then partial re-use (Li & Mira de Orduña 2017, Abstract) → b_ij
  (production) plus c_ij (re-uptake).

**Table C — pyruvate overflow**

| template | parameter | value | units | spread | organism / conditions | source (where) | maps to |
|---|---|---|---|---|---|---|---|
| overflow | citrate in cow's milk | 9.04 (mean) | mmol/L | 3.88–16.12 (n = 506); SD 1.65 in a 134 517-record MIR set | bovine milk, LU/FR/DE (Grelet), Walloon herds (Chen) | Grelet et al. 2016, Abstract; SD from Chen et al. 2024, Results | P0 (≈ 1.7 g/L citric acid, derived) |
| overflow | citrate by lactation stage | 11.3 / 9.7 / 10.1 | mmol/L | SED 0.64 | early / mid / late lactation, 24 cows, same diet | Garnsworthy et al. 2006, Abstract | P0 |
| overflow | citrate (pyruvate) → lactate vs C4 | 50–70 % lactate; 30–50 % α-acetolactate/acetoin | mol % | 4 strains | *L. lactis* bv. *diacetylactis*, late-log cells, modified M17 | Verhue & Tjan 1991, Abstract | split of citrate flux into the C4 pool (stoichiometric max 0.5 mol C4 per mol citrate) |
| overflow | citrate → acetoin at low pH | "all of the citrate utilized" | — | — | *Leuconostoc lactis* NCW1 resting cells, pH 4.3; repressed by 10 mM glucose/lactose | Cogan et al. 1981, Abstract | b/r gated by pH and sugar |
| overflow | pH optimum of citrate utilisation | 5.5–6.0 | pH | — | *L. lactis*, *Leuconostoc* spp. | Starrenburg & Hugenholtz 1991, Abstract | r_citrate(pH) |
| overflow | acetaldehyde production yield (resting cells) | 0.4–42 | mg/g glucose | 26 strains; peak 2.2–189.4 mg/L | *S. cerevisiae* and non-*Saccharomyces* wine yeasts, resting-cell model, no SO₂ | Li & Mira de Orduña 2011, Abstract | b (acetaldehyde) |
| overflow | residual acetaldehyde after fermentation | *S. cerevisiae* 14–34; *C. vini*, *H. anomala*, *H. uvarum*, *M. pulcherrima* < 10; *C. stellata*, *Z. bailii*, *S. pombe* 24–48 | mg/L | 26 strains | grape must, anaerobic | Li & Mira de Orduña 2017, Abstract | b − c (net) |
| overflow | acetaldehyde range in wine | "a few" to ~60; higher at 30 °C | mg/L | 86 strains | *S. cerevisiae*, synthetic medium and must | Romano et al. 1994, Abstract | b |
| overflow | acetaldehyde degradation | all 26 strains degrade it as sole substrate; rate uncorrelated with production | qualitative | — | resting cells | Li & Mira de Orduña 2011, Abstract | c (yeast) exists, no constant |

No opened source gives a first-order constant for α-acetolactate → diacetyl decarboxylation, or for
diacetyl reduction by yeast/LAB (Kobayashi et al. 2005 formulated the decarboxylation vs ethanol,
pH and T — the abstract has no numbers) → table E. AAB oxidation of acetaldehyde: no number found.

---

## 4. Chemical esterification / hydrolysis (acid-catalysed, abiotic)

Ramey & Ough 1980 (model wine: tartaric acid 7.5 g/L adjusted with NaOH, 10–14 % ethanol, initial
esters ~3–30 mg/L, 5 temperatures 4.4–37.8 °C, 200 days): hydrolysis is pseudo-first-order in ester,
rate rises with [H⁺] in the wine pH range, ethanol 10–14 % has "little effect"; acetate esters of
higher alcohols hydrolyse faster than ethyl esters except ethyl decanoate (too fast to quantify
reliably). **Ethyl acetate and ethyl lactate were not studied.** Values below are from the
publisher-scan PDF via OCR; Table I (k at each temperature) did not OCR.

| template | parameter | value | units | spread | organism / conditions | source (where) | maps to |
|---|---|---|---|---|---|---|---|
| chem | k_hydrolysis, isoamyl acetate | 32.6 × 10⁻⁹ (12 % EtOH) | s⁻¹ | SD 1.2 × 10⁻⁹ | model wine, pH 3.58 | Ramey & Ough 1980, Table IV | k0 (≈ 0.0028 d⁻¹, t½ ≈ 250 d, derived) |
| chem | k_hydrolysis, isobutyl acetate | 40.0 × 10⁻⁹ (pH 3.58); 135.9 × 10⁻⁹ (pH 2.95) | s⁻¹ | SD 1.9 × 10⁻⁹ | same | Ramey & Ough, Tables IV–V | k0(pH) |
| chem | k_hydrolysis, 2-phenylethyl acetate | 46.6 × 10⁻⁹ | s⁻¹ | SD 7.0 × 10⁻⁹ | same, pH 3.58 | Ramey & Ough, Table IV | k0 |
| chem | k_hydrolysis, ethyl butanoate | 18.2 × 10⁻⁹ (pH 3.58); 64.1 × 10⁻⁹ (2.95); 9.5 × 10⁻⁹ (4.10) | s⁻¹ | SD 1.1 × 10⁻⁹ | same | Ramey & Ough, Tables IV–V | k0(pH) |
| chem | k_hydrolysis, ethyl hexanoate | 25.8 × 10⁻⁹ (3.58); 82.1 × 10⁻⁹ (2.95); 4.1 × 10⁻⁹ (4.10) | s⁻¹ | SD 2.6 × 10⁻⁹ | same | Ramey & Ough, Tables IV–V | k0(pH) |
| chem | k_hydrolysis, ethyl octanoate | 44.5 × 10⁻⁹ (3.58); 74.5 × 10⁻⁹ (2.95); 48.8 × 10⁻⁹ (4.10) | s⁻¹ | SD 8.7 × 10⁻⁹ | same | Ramey & Ough, Tables IV–V | k0 |
| chem | E_a (hydrolysis) | ethyl butanoate 16.8; ethyl hexanoate 12.7; ethyl octanoate 10.4; isobutyl acetate 14.8; isoamyl acetate 16.5; hexyl acetate 14.8; 2-phenylethyl acetate 12.0 | kcal/mol | SD 0.19–0.85 | 4.4–37.8 °C | Ramey & Ough, Table II | Q10 ≈ 1.8–2.5 near 25 °C (derived) |
| chem | pre-exponential A | 52 100; 80.0; 2.38; 3530; 61 000; 4380; 37.3 (same ester order as E_a row) | s⁻¹ | — | same | Ramey & Ough, Table II (OCR; alignment checked: A·exp(−E_a/RT) reproduces Table IV k at ≈ 19–21 °C) | k0 |
| chem | second-order k_H⁺ | ethyl butanoate 0.613; ethyl hexanoate 0.646; isobutyl acetate 1.19; isoamyl acetate 1.24; hexyl acetate 1.51; 2-phenylethyl acetate 1.18 | × 10^? M⁻¹ s⁻¹ (exponent illegible in OCR) | — | same | Ramey & Ough, Table VI | chem: k ∝ [H⁺]; use only the ratios |
| chem | esterification equilibrium | K = [ester][H₂O]/([acid][alcohol]) = 4 | dimensionless (neat-mixture basis) | — | cited, not measured | Ramey & Ough 1980, Introduction (citing Berthelot & Saint-Gilles) | chem (forward/reverse ratio) — dilute-aqueous K needed, see table E |

Implication: abiotic hydrolysis/formation has t½ of months at pH 3–3.6 and ~20 °C, so it only
matters for miso, garum and long vinegar ageing; it is negligible on kombucha/kefir/sourdough time
scales. The temperature series (Table IV/V conditions) is not legible in the OCR; that the pH 3.58,
12 % EtOH rows correspond to ~21 °C is an inference from Table II.

---

## 5. Brassica glucosinolates (myrosinase → isothiocyanate / nitrile)

**Structural findings**

- Release is fast and complete on fermentation time scales: in sauerkraut at 20 °C glucosinolates
  "were degraded dramatically between Day 2 and 5 of fermentation and by Day 7 there was no
  detectable amount" (Palani et al. 2016, Abstract); white cabbage fermented 7 d at 25 °C contained
  "only traces" (Martinez-Villaluenga et al. 2009, Abstract); kimchi: total GSL degraded 91–100 % in
  over-fermented samples, individual GSL 1–100 % already in moderately fermented ones (Kim et al.
  2022, Highlights and Results) → r_GSL of order 0.5–1 d⁻¹ after a 1–2 d lag (est. from those time
  points, not a fitted constant).
- The ITC yield from sinigrin in sauerkraut is low: products of sinigrin degradation (AITC + allyl
  cyanide) were < 5 % of native sinigrin, vs > 70–96 % for glucoraphanin products; ITC and cyanides
  never exceeded 2.5 µmol/100 g (units as in abstract: "2.5 microM") (Ciska & Pathak 2004,
  Abstract) → either a large loss term for AITC/allyl cyanide (volatility, reaction) or a low
  release-to-volatile yield; **the tracer needs k0 for AITC of order ≥ 0.3 d⁻¹ or a product yield
  ≈ 0.05** (est.).
- Partition ITC vs nitrile: aglucon → ITC spontaneously; nitriles (and epithionitriles from alkenyl
  GSL such as sinigrin) are favoured by specifier proteins (ESP, NSP) and "at pH values lower than 4"
  (Púčiková et al. 2025, Introduction — review statement). In red cabbage, acidification (lemon
  juice / vinegar) of homogenates "reduced nitrile and epithionitrile formation … thereby increasing
  ITC levels" and inhibited SMCSO product formation (Hanschen 2024, Abstract). Seasonal ESP induction
  gave up to 40-fold more ITC in summer than autumn red cabbage; white cabbage hydrolysis showed no
  strong seasonal shift (Púčiková et al. 2025 Food Chem, Abstract). Nitriles + epithionitriles
  averaged 82 ± 4 % of hydrolysis products in the autumn-regime red cabbage seedlings (Púčiková et al.
  2025 JAFC, Results). → ITC fraction is a wide prior (0.1–0.9); no Fe²⁺ number found.

**Table C — glucosinolates**

| template | parameter | value | units | spread | organism / conditions | source (where) | maps to |
|---|---|---|---|---|---|---|---|
| GSL | total GSL, white cabbage head | 42.0 (mean) | µmol/g DW | 19.7–67.8 across 25 genotypes | *B. oleracea* var. *capitata*, 25 lines and hybrids | Fabjan et al. 2026, Results (Fig. 2; Suppl. Table S2) | P0 |
| GSL | sinigrin (→ AITC, allyl cyanide), white cabbage | 11.1 ± 1.2 | µmol/g DW | mean ± SE, 25 genotypes | same | Fabjan 2026, Results (Fig. 2) | P0 (sinigrin) |
| GSL | glucobrassicin / glucoiberin / progoitrin / glucobrassicanapin | 8.2 ± 0.7 / 7.9 ± 0.8 / 4.7 ± 0.8 / 3.3 ± 0.5 | µmol/g DW | mean ± SE | same | Fabjan 2026, Results | P0 (non-volatile or minor volatile products) |
| GSL | glucobrassicin, white cabbage cv. Taler | 1.83 (summer) – 2.54 (winter) | µmol/g DW | 2 seasons | Spain | Martinez-Villaluenga 2009, Abstract | P0 |
| GSL | dominant GSL in white cabbage | glucoiberin, sinigrin, glucobrassicin | — | — | cv. Taler | Martinez-Villaluenga 2009, Abstract | P0 composition |
| GSL | 4-methylthio-3-butenyl GSL (→ 4MTB-ITC), radish root | 54.8 ± 11.3 (Japanese common; 44.1–75.2); 109.6 (Japanese pungent); 35.3 (Chinese); 19.9 (European garden radish) | µmol/g (powdered root; basis not stated in text) | 15.9–135.7 across cultivars | 17 cultivars, 2005 harvest | Ishida et al. 2012, Table 3 and Results | P0 (4MTB-GSL) |
| GSL | 4MTB-GSL share of total radish GSL | 92.0–96.7 | % | 6 Japanese common cultivars | same | Ishida 2012, Table 3 | P0 composition |
| GSL | total GSL, kimchi cabbage (*B. rapa*) | 2.70–57.88 (literature range quoted); 0.44–3.61 measured in 20 commercial non-fermented kimchi | µmol/g DW | — | Korea | Kim et al. 2022, Introduction and Results | P0 |
| GSL | GSL loss during fermentation | 2–5 d steep loss, none detectable at 7 d (20 °C); traces at 7 d (25 °C); 91–100 % lost in over-fermented kimchi | time course | — | sauerkraut, kimchi | Palani 2016; Martinez-Villaluenga 2009; Kim 2022 | r (myrosinase + LAB) |
| GSL | sinigrin → (AITC + allyl cyanide) recovered | < 5 | % of native sinigrin | — | stored sauerkraut | Ciska & Pathak 2004, Abstract | yield × (1 − loss) |
| GSL | glucoraphanin → products recovered | > 70–96 | % of native | — | same | Ciska & Pathak 2004, Abstract | yield (non-volatile analogue) |
| GSL | nitriles + epithionitriles share | 82 ± 4 | % of hydrolysis products | — | red cabbage seedlings, autumn regime | Púčiková 2025 (JAFC), Results | ITC/nitrile split |
| GSL | acid effect on split | acidification ↓ nitrile/epithionitrile, ↑ ITC; stops amine formation | qualitative | — | red cabbage homogenate + lemon juice/vinegar | Hanschen 2024, Abstract | split(pH) |

AITC degradation in water/brine: Tsao et al. 2000 (Abstract) only says AITC is "relatively stable"
in buffered water at pH 5–7 and less stable at pH 9; no half-life opened → table E.

---

## 6. Sulfur (S-methylcysteine sulfoxide, methionine, alliin)

| template | parameter | value | units | spread | organism / conditions | source (where) | maps to |
|---|---|---|---|---|---|---|---|
| sulfur | SMCSO, white cabbage | 3.2–10.2 | µmol/g FW | commercial heads over 3 months | white cabbage; red 3.9–10.3 | Friedrich et al. 2022, Abstract | P0 (SMCSO) |
| sulfur | SMCSO as share of dry matter | ≈ 1 | % DM | — | white and red cabbage | Friedrich 2022, Abstract | P0 cross-check |
| sulfur | main VOSC released from SMCSO on tissue disruption | S-methyl methanethiosulfinate; DMTS and DMDS form from it on heating, "less abundant in fresh homogenates" | qualitative | — | cabbage homogenates | Friedrich 2022, Abstract | product split: MMTSO → DMDS/DMTS is chem (slow at ferment T) |
| sulfur | acidification and SMCSO hydrolysis | "Acidification inhibited formation of products from SMCSO" | qualitative | — | red cabbage + lemon juice/vinegar | Hanschen 2024, Abstract | r_SMCSO gated by pH (falls as LAB acidify) |
| sulfur | SMCSO stability in storage | stable over 8 months at 0 °C; VOSC formation declined with cystine lyase | qualitative | — | white and red cabbage | Andernach et al. 2024, Abstract | P0 constant over raw-material age |
| sulfur | alliin, fresh garlic bulbs | ≈ 0.9 | % (of fresh bulb) | "in the range of" | *Allium sativum*, several origins | Iberl et al. 1990, Abstract | P0 (alliin) |
| sulfur | allicin after complete alliinase conversion | ≈ 0.4 | % | — | same | Iberl 1990, Abstract | alliin → allicin yield ≈ 0.45 g/g (derived; stoichiometric max 0.5 mol/mol) |
| sulfur | methionine → methionol (yeast) | methionol ×~140, 3-methylthiopropanoic acid ×~487 vs control | fold change | triplicates | *S. cerevisiae* LMD17, synthetic must 210 g/L sugar, Met as sole N (250 mg YAN/L), 20 °C | Jiménez-Lorenzo et al. 2026, Results (Fig. 7 text) | methionol is precursor-limited → r·P (Met share of free-AA pool), unlike branched-chain fusels |
| sulfur | methionine → methional by LAB | enzymatic (aminotransferase + α-keto acid decarboxylase), strain-dependent; only 1 of the screened strains (*L. lactis* IFPL730) high | qualitative | — | LAB screen | Amárita et al. 2001, Abstract | c/b for LAB: default 0, strain flag |

No opened source gives conversion rates of SMCSO or methionine to methanethiol/DMDS/DMTS in a
fermenting vegetable, or thiosulfinate → diallyl disulfide rates → table E.

---

## 7. Lipid oxidation, lipoxygenase and mould C8 volatiles

Only qualitative parameters were found in opened sources; every rate for this template is an
estimate (table E).

| template | parameter | value | units | spread | organism / conditions | source (where) | maps to |
|---|---|---|---|---|---|---|---|
| lipid | driver of unsaturated aldehydes in wheat dough | LOX activity and the 9- vs 13-hydroperoxide ratio set the aldehyde profile; carotenoids (lutein) suppress it | qualitative | cultivar-dependent | wheat flour doughs, Japanese cultivars (Norin61 high LOX, high 9-HPOD) | Narisawa et al. 2024, Abstract | r (LOX release, cultivar prior) |
| lipid | microbial removal of n-aldehydes (pentanal, hexanal, nonanal) | lowered by lactobacilli and leuconostocs; lactococci "generally did not" lower them | qualitative | strain-dependent, 151 LAB strains screened | pea/chickpea/mung bean protein + coconut oil emulsion | Engels et al. 2022, Results (Fig. 3, Fig. 5 node 2) | c_ij > 0 for *Lactobacillus*/*Leuconostoc*; c ≈ 0 for *Lactococcus* |
| mould | 1-octen-3-ol biosynthesis gene in rice koji | ppoC is required ("1-octen-3-ol was not detected" in ΔppoC koji); ppoA/ppoD deletion slightly raised it | qualitative | — | *Aspergillus luchuensis*, rice koji, awamori | Kataoka et al. 2020a; 2020b, Abstracts | a/b for *A. oryzae* by analogy (est.) |
| mould | 1-octen-3-ol formation needs cell disruption | volatiles "scarcely formed from intact" conidia; released after freeze–thaw; order 1-octen-3-ol > 3-octanone > 2-octen-1-ol > 1-octen-3-one | qualitative | — | *A. flavus* conidia, 10⁹/mL | Miyamoto et al. 2014, Results | product split among C8 volatiles |
| mould | 1-octen-3-ol, maximum | 187.47 ± 0.92 (*A. sojae*); 265.55 ± 2.79 (*T. atroviride*) | µg/kg | SD | tomato pomace fermentation | Güneşer & Yüceer 2017, Abstract | end-point anchor for koji-type substrates (different substrate) |

---

## 8. Terpenoid glycosides (tea)

| template | parameter | value | units | spread | organism / conditions | source (where) | maps to |
|---|---|---|---|---|---|---|---|
| terpene | total glycosidically bound volatiles, black tea | 105–366 | µg/g made tea | 136 sampling sites | Keemun black tea, Qimen; linalool-oxide glycosides > geranyl > benzyl > 2-phenylethyl glycosides | Zhou et al. 2026, Abstract | P0 (bound pool, shares by aglycone) |
| terpene | primeverosides during black-tea rolling | decrease (glucopyranosides "did not change much") | qualitative | — | tea processing | Cui et al. 2016, Abstract | P0 lower in black than green/oolong tea |
| terpene | free alcoholic aroma compounds vs total | ≈ 12 and 17 % of the whole oolong aroma; no glycoside decreased during oolong manufacture | % | 2 cultivars | oolong | Wang et al. 2001, Abstract | P0 large relative to free pool |
| terpene | acid release of linalool from linalyl-β-primeveroside | "slowly released … in a weakly acidic environment" with isomerisation to geraniol, nerol, α-terpineol | qualitative | — | white-tea withering model | Yan et al. 2024, Abstract | chem (acid hydrolysis, slow) + product split |

No opened source quantifies yeast/AAB β-glucosidase release of tea terpenes in kombucha → table E.

---

## 9. Hydroxycinnamic acids → vinylphenols

| template | parameter | value | units | spread | organism / conditions | source (where) | maps to |
|---|---|---|---|---|---|---|---|
| phenolic | total (free + bound) ferulic acid, sourdoughs | 0.18 ± 0.008 – 0.52 ± 0.04 | mg/g DM | 3 sourdoughs | French bakers' sourdoughs | Boudaoud et al. 2021, Results (Table 3) | P0 (bound + free) |
| phenolic | total ferulic acid, doughs | 0.24–0.28 | mg/g DM | ± 0.009–0.01 | doughs leavened with sourdough and/or yeast | Boudaoud 2021, Results | P0 |
| phenolic | free ferulic acid, wheat bran | 0.01 ± 0.001 | mg/g DM | 4 samples | ethanol/water extraction | Boudaoud 2021, Results | P0 (free share small; release needs feruloyl esterase) |
| phenolic | ferulic acid released during fermentation | 60–90 % of the ferulic acid in wheat / wheat-malt beer hydrolysed during fermentation; Pof⁺ yeast → more 4-vinylguaiacol | % | — | brewer's yeast, wort with wheat | Coghe et al. 2004, Abstract | r (esterase release by yeast) + b/c (Pof⁺ decarboxylation) |
| phenolic | share of LAB isolates that decarboxylate HCA | 12 % (6 of 50; all *L. plantarum*, padA⁺) | % of isolates | — | kimchi LAB | Rosimin & Kim 2015, Abstract | c_ij(*L. plantarum*) with P(active) ≈ 0.12 |
| phenolic | reduction vs decarboxylation | *L. plantarum* 299v: ferulic → dihydroferulic acid only; caffeic → dihydrocaffeic or 4-vinylcatechol/4-ethylcatechol; *L. rhamnosus* GG inactive | qualitative | strain-level | 37 °C, 24 h, MRS-type | Rogozinska et al. 2021, Abstract | split of HCA conversion (vinyl vs dihydro) |

Soybean HCA contents and per-cell decarboxylation rates: not found in an opened source → table E.

---

## 10. Slow chemistry in long ferments (Strecker, HEMF, furanones, pyrazines)

No opened source gives Strecker/Maillard rate constants or Arrhenius parameters at 15–35 °C, HEMF
yields of *Z. rouxii*, or month-scale furaneol/maltol/pyrazine formation rates. One usable precursor
anchor and one structural finding:

| template | parameter | value | units | spread | organism / conditions | source (where) | maps to |
|---|---|---|---|---|---|---|---|
| slow chem | free methionine in high-salt liquid soy sauce | peak 0.18 at 60 d; 0.17 at 230 d; cysteine 0.0048 → 0.0092 (30 → 230 d) | g/100 mL | — | industrial high-salt liquid-state soy sauce, 30–230 d | Zhou et al. 2026 (Food Chem X), Results (free amino acids) | P (methional/Strecker precursor) |
| slow chem | key odorants by omission test | methional, HDMF, HEMF, 4-hydroxy-5-methyl-3(2H)-furanone, 4-ethylguaiacol, 4-methoxyphenol (p ≤ 0.001) | qualitative | — | same | Zhou 2026, Table 2 | which slow-chem compounds matter in miso/garum analogues |

---

## 11. Volatility loss

**Henry's-law solubility constants** H^s_cp at 298.15 K from Sander 2023 (compilation v5.0.0,
henrys-law.org species pages, opened 2026-10-05; first "L" = literature-review row where present,
else the first measured row; n = number of entries on the page). Dimensionless gas/liquid ratio
K_aw = 1/(H·R·T) (derived). The temperature coefficient d ln H/d(1/T) of 5 500–7 200 K for most
esters/alcohols gives K_aw × ≈ 1.9–2.3 per +10 °C near 25 °C (derived).

| compound | H^s_cp [mol m⁻³ Pa⁻¹] (row used) | d ln H / d(1/T) [K] | n, median (min–max) on page | K_aw (derived) |
|---|---|---|---|---|
| acetaldehyde | 0.13 (Burkholder et al. 2019, L) | 5900 | 46, 0.13 (0.017–0.39) | 3.1 × 10⁻³ |
| ethyl acetate | 0.065 (Burkholder 2019, L) | 5600 | 49, 0.058 (0.022–0.36) | 6.2 × 10⁻³ |
| isoamyl acetate | 0.021 (Brockbank 2013, L) | 6700 | 28, 0.022 (0.0088–0.088) | 1.9 × 10⁻² |
| ethyl butanoate | 0.025 (Brockbank 2013, L) | 6100 | 31, 0.027 (0.012–0.045) | 1.6 × 10⁻² |
| ethyl hexanoate | 0.019 (Plyasunov et al. 2004, L) | 7200 | 10, 0.015 (0.0069–0.019) | 2.1 × 10⁻² |
| ethyl octanoate | 0.017 (Plyasunov 2004, L) | — | 4, 0.011 (0.0078–0.017) | 2.4 × 10⁻² |
| ethyl lactate | 17 (HSDB 2015, V = estimate) | — | 2 | 2.4 × 10⁻⁵ |
| diacetyl | 0.73 (Burkholder 2019, L) | 5700 | 20, 0.72 (0.14–49) | 5.5 × 10⁻⁴ |
| 3-methylbutanol | 0.82 (Brockbank 2013, L) | 8000 | 19, 0.69 (0.12–0.82) | 4.9 × 10⁻⁴ |
| 2-methylpropanol | 0.83 (Burkholder 2019, L) | 7200 | 31, 0.76 (0.22–0.99) | 4.9 × 10⁻⁴ |
| 2-phenylethanol | 17 (Brockbank 2013, L) | 7200 | 21, median 31 | 2.4 × 10⁻⁵ |
| 3-methylbutanal | 0.024 (Wieland et al. 2015, M) | 6100 | 16, 0.032 (0.0098–0.11) | 1.7 × 10⁻² |
| hexanal | 0.045 (Brockbank 2013, L) | 6400 | 36, 0.046 (0.0043–0.30) | 9.0 × 10⁻³ |
| (E)-2-nonenal | 0.058 (Roberts & Pollien 1997, M) | — | 1 | 7.0 × 10⁻³ |
| 1-octen-3-ol | 0.19 (Wu et al. 2022a, M) | 7900 | 3, 0.19 (0.13–0.25) | 2.1 × 10⁻³ |
| allyl isothiocyanate | 0.021 (Souchon et al. 2004, M) | — | 4, 0.041 (0.021–0.23) | 1.9 × 10⁻² |
| methanethiol | 0.0038 (Burkholder 2019, L) | 3400 | 25, 0.0033 (0.002–0.14) | 0.11 |
| dimethyl sulfide | 0.0053 (Burkholder 2019, L) | 3500 | 52, 0.0053 (0.00079–0.17) | 7.6 × 10⁻² |
| dimethyl disulfide | 0.0058 (Burkholder 2019, L) | 3700 (Brockbank) | 20, 0.008 (0.0036–0.087) | 7.0 × 10⁻² |
| dimethyl trisulfide | 0.012 (Plyasunova et al. 2004, L) | — | 3, 0.014 (0.012–0.021) | 3.4 × 10⁻² |
| diallyl disulfide | 0.0075 (Mazza 1980, M) | — | 1 | 5.4 × 10⁻² |
| linalool | 0.20 (Leng et al. 2013, M) | 4400 | 14, 0.35 (0.015–0.69) | 2.0 × 10⁻³ |
| trimethylamine (neutral form) | 0.099 (Burkholder 2019, L) | — | 17, 0.097 (0.033–0.94) | 4.1 × 10⁻³ (protonated at food pH → ≈ 0) |
| acetic acid (neutral form) | 40 (Burkholder 2019, L) | 6200 | 34 | 1.0 × 10⁻⁵ |

Methional and 4-vinylguaiacol pages did not parse; ethanol entries on the page were inconsistent
(n = 4, 0.047–0.83) → not used.

**Loss forms supported by opened data**

- *CO₂-stripped ferments* (yeast types): loss rate = (Q_CO₂/V)·K_aw·C. Order-of-magnitude check
  (derived): 200 g/L sugar → ≈ 2.1 mol CO₂/L ≈ 52 L gas per L at 25 °C; with K_aw(isoamyl acetate)
  = 0.019 a compound present throughout would lose 1 − e^(−1.0) ≈ 63 %; Godillot 2023 measured
  14–30 % (production is progressive and ethanol lowers K_aw), so the form is right within ×2–4.
  Higher alcohols (K_aw ≈ 5 × 10⁻⁴) lose < 3 % → "negligible", as Godillot found.
- *Open still vessels* (kombucha, vinegar, lacto-ferments under airlock): needs a surface mass-
  transfer coefficient; none opened → k0 is an estimate (table E). K_aw above ranks compounds:
  thiols/sulfides and esters lose fastest, alcohols, acids, furanones and 2-phenylethanol slowest.

---

## E. Unverified leads (not to be used as data)

| # | value / claim | why I believe it | what to search |
|---|---|---|---|
| E1 | Dilute-aqueous equilibrium for ethyl acetate hydrolysis (K = [AcOH][EtOH]/[EtOAc] of order 10 M?) | Guthrie-type thermochemistry papers exist (Can J Chem 1980, doi 10.1139/v80-201 — paywalled, not opened) | "Guthrie equilibrium constant hydrolysis ethyl acetate aqueous 25 °C"; also ethyl lactate |
| E2 | Ethyl lactate forms chemically in wine/sourdough over months | wine-ageing reviews; Ramey & Ough excluded it | "ethyl lactate formation kinetics wine storage temperature" |
| E3 | α-acetolactate → diacetyl first-order constant rises with T, falls with pH (Kobayashi 2005 formulated it vs ethanol, pH, T) | abstract only, no numbers | Kobayashi et al. 2005 J Biosci Bioeng 99:502 full text; Haukeli & Lie 1978 J Inst Brew |
| E4 | Yeast diacetyl reduction ≈ first-order, faster with more active cells; brewing models (de Andrés-Toro et al. 1998 Math Comput Simul 48:65) give Arrhenius parameters for diacetyl and ethyl acetate | model known from search snippets only | de Andrés-Toro 1998 parameter table; Krogerus & Gibson 2013 J Inst Brew 119:86 |
| E5 | Diacetyl in cultured buttermilk/cream ~1–5 mg/kg with acetoin 10–100× higher | memory of dairy texts; Hugenholtz 1993 FEMS Microbiol Rev 12:165 (not opened) | "diacetyl acetoin concentration buttermilk Lactococcus diacetylactis mg/kg" |
| E6 | Wine MCFA: hexanoic ~1–5, octanoic ~2–10, decanoic ~0.5–3 mg/L | general wine literature recall; the one opened paper (Liu 2021) is 10× higher | "octanoic decanoic acid synthetic must fermentation mg/L temperature" |
| E7 | 2-phenylethanol 10–100 mg/L and ethyl acetate 20–60 mg/L in dry wine from ~200 g/L sugar (→ 0.05–0.5 and 0.1–0.3 mg/g) | Saerens Table 2 range for ethyl acetate supports the latter; 2-PE from recall | Rollero et al. 2015 Appl Microbiol Biotechnol 99:2291 Tables |
| E8 | Fusel/ester yields of *K. humilis*, *Z. rouxii*, *Brettanomyces* in tea or dough media | sparse literature | "Kazachstania humilis volatile compounds sourdough"; "Zygosaccharomyces rouxii isoamyl alcohol yield" |
| E9 | AITC half-life in water at 20–30 °C, pH 3.5–6: days to weeks | Tsao 2000 says "relatively stable" pH 5–7 | Ohta et al. 1995 Biosci Biotechnol Biochem "decomposition rate allyl isothiocyanate aqueous" |
| E10 | White cabbage dry matter ≈ 8–10 % (for µmol/g DW → FW) | Friedrich 2022 numbers imply DM 5–15 % (derived from SMCSO 1 % DM and 3.2–10.2 µmol/g FW) | food composition table (e.g. Souci–Fachmann–Kraut, USDA) |
| E11 | Myrosinase Km/Vmax for sinigrin in cabbage; Fe²⁺ promotes nitriles | classic enzymology | "myrosinase kinetics sinigrin cabbage Km"; "ferrous iron nitrile glucosinolate hydrolysis" |
| E12 | SMCSO → methanethiol/DMDS/DMTS yields in fermenting cabbage; methionine γ-lyase rates in LAB | qualitative only in opened sources | "dimethyl disulfide sauerkraut fermentation time course S-methylcysteine sulfoxide" |
| E13 | Allicin → diallyl disulfide in water: hours–days | recall | "allicin stability aqueous half-life temperature diallyl disulfide formation" |
| E14 | Hexanal in wheat dough after mixing 0.1–1 mg/kg; LAB/yeast reduce it to hexanol within hours | recall | "hexanal dough mixing lipoxygenase µg/kg yeast reduction hexanol" |
| E15 | 1-octen-3-ol in rice koji, µg per g koji | Kataoka 2020 measured it by SPME (no number in abstract) | Kataoka et al. 2020 J Biosci Bioeng 129:192 full text |
| E16 | Bound linalool/geraniol in tea infusions and release by kombucha yeasts | none opened | "kombucha linalool geraniol β-glucosidase release" |
| E17 | Soybean ferulic/p-coumaric acid content; 4-vinylguaiacol yields in sourdough | none opened | "4-vinylguaiacol sourdough Lactobacillus plantarum ferulic acid conversion yield" |
| E18 | Strecker aldehyde formation Arrhenius parameters near ambient; HEMF by *Z. rouxii* (mg/L); furaneol/maltol/pyrazine rates in miso over months | none opened (enzyme for HEMF reported in J Biosci Bioeng 2017, PMID 27865643, abstract not opened) | "HEMF production Zygosaccharomyces rouxii mg/L"; "miso volatile compounds aging months 2,5-dimethylpyrazine" |
| E19 | Open-vessel liquid/gas-film mass-transfer coefficients for jars (k0 for evaporation) | physics; no food-specific source opened | "volatile loss open container mass transfer coefficient aroma stripping" |
| E20 | Gas–liquid partition coefficients in must/wine vs T and ethanol (Morakul et al. 2010 JAFC 58:10219) | abstract opened, no numbers | full text Tables |

---

## Sources (all opened; "abstract" = numbers taken from the abstract only)

1. Amárita F, Fernández-Esplá D, Requena T, Peláez C (2001) Conversion of methionine to methional by *Lactococcus lactis*. FEMS Microbiol Lett 204:189–195. doi:10.1111/j.1574-6968.2001.tb10884.x (abstract)
2. Andernach L, Witzel K, Hanschen FS (2024) Effect of long-term storage on glucosinolate and S-methyl-l-cysteine sulfoxide hydrolysis in cabbage. Food Chem 430:136969. doi:10.1016/j.foodchem.2023.136969 (abstract)
3. Boudaoud S, Sicard D, Suc L, Conéjéro G, Segond D, Aouf C (2021) Ferulic acid content variation from wheat to bread. Food Sci Nutr 9:2446–. doi:10.1002/fsn3.2171 (full text)
4. Chen Y, Atashi H, Grelet C, Gengler N (2024) Weighted single-step GBLUP … milk citrate predicted by mid-infrared spectra. JDS Commun 6:90–. doi:10.3168/jdsc.2024-0607 (full text)
5. Ciska E, Pathak DR (2004) Glucosinolate derivatives in stored fermented cabbage. J Agric Food Chem 52:7938–7943. doi:10.1021/jf048986+ (abstract)
6. Coghe S, Benoot K, Delvaux F, Vanderhaegen B, Delvaux FR (2004) Ferulic acid release and 4-vinylguaiacol formation during brewing and fermentation. J Agric Food Chem 52:602–608. doi:10.1021/jf0346556 (abstract)
7. Cogan TM, O'Dowd M, Mellerick D (1981) Effects of pH and sugar on acetoin production from citrate by *Leuconostoc lactis*. Appl Environ Microbiol 41:1–8. doi:10.1128/aem.41.1.1-8.1981 (abstract)
8. Cui J, Katsuno T, Totsuka K, et al. (2016) Characteristic fluctuations in glycosidically bound volatiles during tea processing. J Agric Food Chem 64:1151–1157. doi:10.1021/acs.jafc.5b05072 (abstract)
9. Engels W, Siu J, van Schalkwijk S, Wesselink W, Jacobs S, Bachmann H, Bonnarme P, Landaud S (2022) Metabolic conversions by lactic acid bacteria during plant protein fermentations. Foods 11:1005. doi:10.3390/foods11071005 (full text)
10. Fabjan P, Mikulič-Petkovšek M, Kastelec D, Podržaj A, Rudolf-Pilih K (2026) Glucosinolate variation, heterosis, and prediction of hybrid performance from parental values in white cabbage. Front Plant Sci 17:1703515. doi:10.3389/fpls.2026.1703515 (full text)
11. Friedrich K, Wermter NS, Andernach L, Witzel K, Hanschen FS (2022) Formation of volatile sulfur compounds and S-methyl-l-cysteine sulfoxide in *Brassica oleracea* vegetables. Food Chem 383:132544. doi:10.1016/j.foodchem.2022.132544 (abstract)
12. Garnsworthy PC, Masson LL, Lock AL, Mottram TT (2006) Variation of milk citrate with stage of lactation and de novo fatty acid synthesis in dairy cows. J Dairy Sci 89:1604–1612. doi:10.3168/jds.S0022-0302(06)72227-5 (abstract)
13. Godillot J, Baconin C, Sanchez I, Baragatti M, Perez M, Sire Y, Aguera E, Sablayrolles J-M, Farines V, Mouret J-R (2023) Analysis of volatile compounds production kinetics: a study of the impact of nitrogen addition and temperature during alcoholic fermentation. Front Microbiol 14:1124970. doi:10.3389/fmicb.2023.1124970 (full text)
14. Grelet C, Bastin C, Gelé M, et al. (2016) Development of Fourier transform mid-infrared calibrations to predict acetone, β-hydroxybutyrate, and citrate contents in bovine milk. J Dairy Sci 99:4816–4825. doi:10.3168/jds.2015-10477 (abstract)
15. Güneşer O, Yüceer YK (2017) Biosynthesis of eight-carbon volatiles from tomato and pepper pomaces by fungi. J Biosci Bioeng 123:451–459. doi:10.1016/j.jbiosc.2016.11.013 (abstract)
16. Hanschen FS (2024) Acidification and tissue disruption affect glucosinolate and S-methyl-l-cysteine sulfoxide hydrolysis … in red cabbage. Food Res Int 178:114004. doi:10.1016/j.foodres.2024.114004 (abstract)
17. Hazelwood LA, Daran J-M, van Maris AJA, Pronk JT, Dickinson JR (2008) The Ehrlich pathway for fusel alcohol production: a century of research on *Saccharomyces cerevisiae* metabolism. Appl Environ Microbiol 74:2259–2266. doi:10.1128/AEM.02625-07 (full text)
18. Hoffmann A, Kupsch C, Walther T, Löser C (2021) Synthesis of ethyl acetate from glucose by *Kluyveromyces marxianus*, *Cyberlindnera jadinii* and *Wickerhamomyces anomalus* depending on the induction mode. Eng Life Sci 21:154–168. doi:10.1002/elsc.202000048 (full text)
19. Iberl B, Winkler G, Müller B, Knobloch K (1990) Quantitative determination of allicin and alliin from garlic by HPLC. Planta Med 56:320–326. doi:10.1055/s-2006-960969 (abstract)
20. Ishida M, Nagata M, Ohara T, Kakizaki T, Hatakeyama K, Nishio T (2012) Small variation of glucosinolate composition in Japanese cultivars of radish. Breed Sci 62:63–. doi:10.1270/jsbbs.62.63 (full text)
21. Jiménez-Lorenzo R, Duncan JD, Nolleau V, Farines V, Sablayrolles J-M, Bloem A, Camarasa C (2026) Cysteine, methionine, and pantothenic acid remodel the *S. cerevisiae* transcriptome and volatile sulfur compound metabolome during alcoholic fermentation. FEMS Yeast Res 26:foag022. doi:10.1093/femsyr/foag022 (full text)
22. Kataoka R, Watanabe T, Yano S, Mizutani O, Yamada O, Kasumi T, Ogihara J (2020a) *Aspergillus luchuensis* fatty acid oxygenase ppoC is necessary for 1-octen-3-ol biosynthesis in rice koji. J Biosci Bioeng 129:192–198. doi:10.1016/j.jbiosc.2019.08.010 (abstract)
23. Kataoka R, Watanabe T, Hayashi R, Isogai A, Yamada O, Ogihara J (2020b) Awamori fermentation test and 1-octen-3-ol productivity analysis using fatty acid oxygenase disruptants of *A. luchuensis*. J Biosci Bioeng 130:489–495. doi:10.1016/j.jbiosc.2020.06.006 (abstract)
24. Kim S-Y, Yang J, Dang Y-M, Ha J-H (2022) Effect of fermentation stages on glucosinolate profiles in kimchi. Food Chem X 15:100417. doi:10.1016/j.fochx.2022.100417 (full text)
25. Kobayashi K, Kusaka K, Takahashi T, Sato K (2005) Method for the simultaneous assay of diacetyl and acetoin in the presence of α-acetolactate. J Biosci Bioeng 99:502–507. doi:10.1263/jbb.99.502 (abstract; no numbers)
26. Li E, Mira de Orduña R (2011) Evaluation of the acetaldehyde production and degradation potential of 26 enological *Saccharomyces* and non-*Saccharomyces* yeast strains in a resting cell model system. J Ind Microbiol Biotechnol 38:1391–1398. doi:10.1007/s10295-010-0924-1 (abstract)
27. Li E, Mira de Orduña R (2017) Acetaldehyde kinetics of enological yeast during alcoholic fermentation in grape must. J Ind Microbiol Biotechnol 44:229–236. doi:10.1007/s10295-016-1879-7 (abstract)
28. Liu P, Ivanova-Petropulos V, Duan C, Yan G (2021) Effect of unsaturated fatty acids on intra-metabolites and aroma compounds of *S. cerevisiae* in wine fermentation. Foods 10:277. doi:10.3390/foods10020277 (full text; MCFA values not used)
29. Martinez-Villaluenga C, Peñas E, Frias J, et al. (2009) Influence of fermentation conditions on glucosinolates, ascorbigen, and ascorbic acid content in white cabbage cultivated in different seasons. J Food Sci 74:C62–C67. doi:10.1111/j.1750-3841.2008.01017.x (abstract)
30. Miyamoto K, Murakami T, Kakumyan P, Keller NP, Matsui K (2014) Formation of 1-octen-3-ol from *Aspergillus flavus* conidia is accelerated after disruption of cells independently of Ppo oxygenases. PeerJ 2:e395. doi:10.7717/peerj.395 (full text)
31. Narisawa T, Sakai K, Nakajima H, et al. (2024) Effects of fatty acid hydroperoxides produced by lipoxygenase in wheat cultivars during dough preparation on volatile compound formation. Food Chem 443:138566. doi:10.1016/j.foodchem.2024.138566 (abstract)
32. Palani K, Harbaum-Piayda B, Meske D, Keppler JK, Bockelmann W, Heller KJ, Schwarz K (2016) Influence of fermentation on glucosinolates and glucobrassicin degradation products in sauerkraut. Food Chem 190:755–762. doi:10.1016/j.foodchem.2015.06.012 (abstract)
33. Púčiková V, Witzel K, Rohn S, Hanschen FS (2025a) Season-dependent variation in the contents of glucosinolates and S-methyl-l-cysteine sulfoxide and their hydrolysis in *Brassica oleracea*. Food Chem 465:142100. doi:10.1016/j.foodchem.2024.142100 (abstract)
34. Púčiková V, Kluge SI, Witzel K, Rohn S, Hanschen FS (2025b) Temperature and light regimes shape seasonal variation in glucosinolate hydrolysis in red cabbage. J Agric Food Chem 73:20094–. doi:10.1021/acs.jafc.5c06284 (full text)
35. Ramey DD, Ough CS (1980) Volatile ester hydrolysis or formation during storage of model solutions and wines. J Agric Food Chem 28:928–934 (full text, scanned PDF at rameywine.com; DOI not recorded)
36. Rogozinska M, Korsak D, Mroczek J, Biesaga M (2021) Catabolism of hydroxycinnamic acids in contact with probiotic *Lactobacillus*. J Appl Microbiol 131:1464–1473. doi:10.1111/jam.15009 (abstract)
37. Rollero S, Mouret J-R, Bloem A, Sanchez I, Ortiz-Julien A, Sablayrolles J-M, Dequin S, Camarasa C (2017) Quantitative ¹³C-isotope labelling-based analysis to elucidate the influence of environmental parameters on the production of fermentative aromas during wine fermentation. Microb Biotechnol 10:1649–1662. doi:10.1111/1751-7915.12749 (full text)
38. Romano P, Suzzi G, Turbanti L, Polsinelli M (1994) Acetaldehyde production in *Saccharomyces cerevisiae* wine yeasts. FEMS Microbiol Lett 118:213–218. doi:10.1111/j.1574-6968.1994.tb06830.x (abstract)
39. Rosimin AA, Kim KS (2015) Production of volatile phenols by kimchi *Lactobacillus plantarum* isolates and factors influencing their phenolic acid decarboxylase gene expression profiles. Food Res Int 78:231–237. doi:10.1016/j.foodres.2015.10.004 (abstract)
40. Saerens SMG, Delvaux F, Verstrepen KJ, Van Dijck P, Thevelein JM, Delvaux FR (2008) Parameters affecting ethyl ester production by *Saccharomyces cerevisiae* during fermentation. Appl Environ Microbiol 74:454–461. doi:10.1128/AEM.01616-07 (abstract)
41. Saerens SMG, Delvaux FR, Verstrepen KJ, Thevelein JM (2010) Production and biological function of volatile esters in *Saccharomyces cerevisiae*. Microb Biotechnol 3:165–. doi:10.1111/j.1751-7915.2009.00106.x (full text)
42. Sander R (2023) Compilation of Henry's law constants (version 5.0.0) for water as solvent. Atmos Chem Phys 23:10901–12440. doi:10.5194/acp-23-10901-2023 (species pages at henrys-law.org opened; primary rows cited by the compilation's reference keys)
43. Starrenburg MJ, Hugenholtz J (1991) Citrate fermentation by *Lactococcus* and *Leuconostoc* spp. Appl Environ Microbiol 57:3535–3540. doi:10.1128/aem.57.12.3535-3540.1991 (abstract)
44. Tsao R, Yu Q, Friesen I, Potter J, Chiba M (2000) Factors affecting the dissolution and degradation of oriental mustard-derived sinigrin and allyl isothiocyanate in aqueous media. J Agric Food Chem 48:1898–1902. doi:10.1021/jf9906578 (abstract)
45. Verhue WM, Tjan FS (1991) Study of the citrate metabolism of *Lactococcus lactis* subsp. *lactis* biovar *diacetylactis* by means of ¹³C NMR. Appl Environ Microbiol 57:3371–3377. doi:10.1128/aem.57.11.3371-3377.1991 (abstract)
46. Wang D, Kubota K, Kobayashi A, Juan IM (2001) Analysis of glycosidically bound aroma precursors in tea leaves. 3. Change in the glycoside content of tea leaves during the oolong tea manufacturing process. J Agric Food Chem 49:5391–5396. doi:10.1021/jf010235+ (abstract)
47. Yan H, Lin Z, Li W, et al. (2024) Unraveling the enantiomeric distribution of glycosidically bound linalool in teas and their acidolysis characteristics and pyrolysis mechanism. J Agric Food Chem (online ahead of print). doi:10.1021/acs.jafc.4c00037 (abstract)
48. Zhang Z, Lan Q, Yu Y, Zhou J, Lu H (2022) Comparative metabolome and transcriptome analyses of the properties of *Kluyveromyces marxianus* and *Saccharomyces* yeasts in apple cider fermentation. Food Chem Mol Sci 4:100095. doi:10.1016/j.fochms.2022.100095 (full text)
49. Zhou H, Zhu J, Yang J, et al. (2026) Metabolic profiling of glycosidically bound volatiles associated with specific aroma of Keemun black tea. Food Chem 504:148016. doi:10.1016/j.foodchem.2026.148016 (abstract)
50. Zhou Y, Xin R, Guan W, Guo P, Zhou S, Wu C, Liu Y (2026) Investigation on the dynamic change of key odor compounds, free amino acids and chroma during soy sauce fermentation. Food Chem X 36:103934. doi:10.1016/j.fochx.2026.103934 (full text)
