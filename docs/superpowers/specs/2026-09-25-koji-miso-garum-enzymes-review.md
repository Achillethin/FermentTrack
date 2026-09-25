# Koji, miso and garum enzyme kinetics: scientific review and revised model

**Date:** 2026-09-25 · **Status:** implemented (`prediction/enzymes.py`, `engine.py`, `model.py`, `profiles.py`), tests in `tests/test_prediction_enzymes.py`
**Builds on:** `2026-09-24-fermentation-prediction-design.md` § 3 (enzymes) · **Pathway enzymes in KEGG:** `2026-09-25-biochemistry-v4-curation.md`

The owner asked to keep the koji, miso and garum forecasts, with enzyme activity depending on temperature, backed by a solid scientific review. An independent literature review of the first model (one lumped "koji enzyme" pool) found it could not be defended. The model was rebuilt around its recommendations and calibrated against ten published checkpoints.

## 1. What the review found in the first model

| # | Item | Verdict |
|---|---|---|
| 1 | One lumped koji enzyme pool | **Not defensible.** Amylases, endo-proteases and peptidases differ ~10× in heat stability and in salt tolerance, in opposite directions: amylase is heat-labile but salt-tolerant, protease more heat-stable but strongly salt-sensitive (Su et al. 2005; Hasegawa & Funakoshi 2016). |
| 2 | Temperature curve from Oguro et al. 2019 (66/100/92/77 % at 40/50/60/70 °C) used as activity | **Conceptual error.** Those are glucose *yields* over a short run, with heat inactivation already folded in. Used as a sustained rate, 60 °C looked as good as 50 °C for weeks. |
| 3 | Inactivation first order, Q10 1.5 | **Wrong shape above ~45 °C.** It gave a 23-day half-life at 60 °C. In mash, α-amylase is gone after 96 h at 55 °C, and protease extract keeps 20 % after 4 h at 55 °C. Denaturation needs Ed ≈ 100–300 kJ/mol plus a slow low-temperature term. |
| 4 | One linear salt factor | **Wrong.** Protease has ~3 % left at 18 % NaCl; amylase is "quite stable" in NaCl; fish enzymes keep ~50 % at 25 %. |
| 5 | Fish enzymes never decayed | Inconsistent with autolysis data (maximum at 60 °C, lost within days there). |
| 6 | Protein → free amino acids in one step | **Mis-specified.** Miso reaches ~55–60 % soluble N but only ~20 % free (formol) N at 90 days (Ohnishi 1982); fish sauce reaches amino N/TN ≈ 0.5. Two steps are needed. |
| 7 | Enzyme production independent of koji temperature | Protease is made more at ~30 °C and amylase at 35–40 °C (Narahara et al. 1982; Kitano et al. 2002); miso makers use this deliberately (Kusumoto et al. 2021). |
| 8 | *A. oryzae* growth optimum 32.5 °C, max 44 °C | Probably too cool: 38 °C on steamed rice (Narahara 1982); sake koji runs at 38–43 °C. |
| 9 | Glucose share of koji amylolysis 0.8 | Use 0.9 (maltose not detected; glucose 9.4× isomaltose, Akamatsu et al. 2024). |
| 10 | Citation | Miso koji practice is Kusumoto et al. 2021 *J Fungi* 7:579, not Ito & Matsuyama 2021 (which covers soy sauce). Fixed in the miso profile. |

## 2. Revised model

Per enzyme class *c* (activity *E* on a 0–1 "fully grown koji" scale; fish: 1 = fresh whole fish with viscera):

```
rate     = k · E · A(T) · f_salt(s) · access · substrate          first order in substrate
A(T)     = exp[−Ea/R · (1/T − 1/323.15)]                          catalysis, 50 °C = 1
dE/dt    = production − kd(T) · E
kd(T)    = ln2/t½ · exp[Ed/R · (1/T_ref − 1/T)]                   heat denaturation
           + floor · 2^((T − 25)/10)                              slow loss at 20–35 °C
f_salt   = r + (1 − r) / (1 + (s/s50)²)                            s = water-phase NaCl %
```

Protein breaks down in two steps: **protein → soluble peptides** (endo-proteases, fish enzymes), then **peptides → free amino acids** (peptidases; fish peptidases). Up to 85 % of protein can be solubilised. The forecast shows *soluble protein* (peptides + free amino acids, which corresponds to soluble N / total N) and *free amino acids* (formol N / total N). It also shows each enzyme's activity over time.

Medians and 90 % ranges (all log-normal priors):

| Class | k (1/h at 50 °C) | Ea kJ/mol | t½ at T_ref | Ed kJ/mol | slow loss at 25 °C (1/h) | salt s50 % (floor) |
|---|---|---|---|---|---|---|
| Amylase (α-amylase + glucoamylase), starch → 90 % glucose | 0.18 (0.08–0.4) | 55 (40–70) | 3 h at 60 °C (1–10) | 160 (110–230) | 1e-3 | 40 (0) |
| Endo-protease, protein → peptides (+10 % thermostable, NP II) | 0.08 (0.03–0.2) | 50 (35–65) | 12 h at 55 °C (3–60) | 200 (150–300) | 2e-4 | 12 (0) |
| Peptidase, peptides → free amino acids | 0.08 (0.03–0.2) | 50 (35–65) | 24 h at 60 °C (6–100) | 200 (150–300) | 5e-4 | 13 (0) |
| Fish enzymes, both steps (peptidase k 0.004) | 0.005 (0.002–0.012) | 50 (35–65) | 120 h at 60 °C (24–480) | 160 (120–220) | 3e-5 | 25 (0) |

**Koji production while the mould grows** (Luedeking–Piret, shifted by bed temperature with fixed CTMI gains, est.):
- amylase follows growth × CTMI(15, **37**, 46 °C);
- protease and peptidase follow growth × CTMI(15, **30**, 42 °C);
- protease keeps being made after growth stops, at 0.005/h per unit of mycelium (alkaline protease still rising at 72 h, Chancharoonpong et al. 2012).

At 30 °C a koji ends with about 0.55 amylase and 0.86 protease at 48 h; at 38 °C, about 0.77 amylase and 0.52 protease.

**Access:** 1 in a slurry or brine (garum, amazake); 0.5 in a paste (miso, ~47 % moisture; proteolysis scales with moisture, Chiou 2001; without it no single peptidase salt curve fits both Su 2005 and Ohnishi 1982); 0.05 in the solid koji bed.

**Other changes:**
- *A. oryzae* growth optimum is now 35.5 °C (33–38) and its maximum 45 °C (43–47). μmax was re-set so that koji still reaches 90 % growth in ~40–50 h at 30 °C.
- Miso starts with koji enzymes at 0.4 (0.25–0.7) of a fully grown koji, the koji share of the mash.
- Garum starts with fish enzymes at 1.0 (0.3–2.0), since gutted fish carries less.
- New milestones:
  - miso: 50 % of the protein solubilised; free amino acids at 15 % of the protein;
  - garum: 50 % of the protein solubilised; free amino acids at 30 % of the protein.

## 3. Literature checkpoints (median parameters unless noted)

| # | Checkpoint | Published | Model | Test |
|---|---|---|---|---|
| 1 | Rice koji saccharification, koji:water 1:2, 24 h (Akamatsu et al. 2024) | ~60 % at 50 °C; ~10 % at 15 °C | 59 %; 11 % | `test_1_…` |
| 2 | 8 h yields vs 50 °C (Oguro et al. 2019), now an emergent result | 66 / 100 / 92 / 77 % at 40 / 50 / 60 / 70 °C | 64 / 100 / 98 / **44** | `test_2_…` |
| 3 | Shio-koji, 13 % salt, 96 h (Hasegawa & Funakoshi 2016) | amylase ≈ 0 at 55 °C; protease loses less; 45 °C loses less than 55 °C | amylase 0 % / protease 9 % left at 55 °C; 16 % / 57 % at 45 °C | `test_3_…` |
| 4 | Koji + 1.5 vol water, 5 % NaCl, 48 h (Su et al. 2005) | amino N / soluble N 0.43 at 45 °C; 45 °C beats 55 °C | 0.40; soluble 49 % vs 42 % | `test_4_…` |
| 5 | Shinshu miso, 21.7 % salt, 32 °C 25 d → 20 °C, 90 d (Ohnishi 1982) | soluble N 55–60 %, formol N ~20 % | 51 %, 17 % | `test_5_…` |
| 6 | Warm vs unheated miso (Kusumoto et al. 2021) | ~3 months at 30 °C ≈ ~1 year ambient (ratio 3–5) | ratio **2.6** against a constant 15 °C | `test_6_…` |
| 7 | Koji enzyme timing at 30 °C (Chancharoonpong et al. 2012) | protease still rising after growth | 72 h > 48 h | `test_7_8_…` |
| 8 | Koji temperature vs enzyme mix (Narahara 1982; Kitano 2002) | protease(30 °C) > protease(38 °C); amylase not suppressed warm; growth faster at 38 °C | protease 86 vs 52 %; amylase 54 vs 77 % (prior forecast, 48 h) | `test_7_8_…` |
| 9 | Fish sauce, 25 % salt, 30–35 °C, 180 d (Udomsil et al. 2011, 2022) | amino N / TN ≈ 0.5–0.6; most N soluble | 0.58–0.67; soluble 79–82 % | `test_9_…` |
| 10 | Fish sauce 50 vs 35 °C, 15 d (Lopetcharat & Park 2002) | 50 °C clearly faster | soluble 43 % vs 25 % | `test_10_…` |
| — | Koji garum, 12 weeks (review § 3) | 60 °C front-loads; 45–50 °C ends richer in free amino acids | 60 °C: AA ~26 %, most of it within a week; 45 °C: AA ~80 % (prior forecast) | `test_koji_garum_…` |

**Where the model is short:**
- At 70 °C it under-predicts the Oguro yield (44 against 77). One first-order denaturation cannot match both the low-temperature stability miso needs and the 70 °C point; starch probably protects amylase at high temperature. Nothing in the app runs at 70 °C.
- The warm-brewing ratio is 2.6 against 3–5. Real "ambient" miso sees a cold winter and a warm summer rather than a constant 15 °C, and Ea 50 kJ/mol stays within the published range.

## 4. What stays exploratory

Koji, miso and garum keep `confidence: "exploratory"`. Miso could move to "indicative" now that checkpoints 5 and 6 pass, once real batches confirm it.

Not modelled:
- glutaminase and glutamate (GahB is ~90 % of koji glutaminase, salt-sensitive and alkaline-optimal; the review gives its parameters);
- Maillard browning, which matters for hot garum;
- halophilic bacterial proteinases in traditional fish sauce;
- koji self-heating and bed moisture (access and glucoamylase induction depend on it);
- a salting knock-down of neutral protease at mixing.

The koji production gains (37 °C amylase, 30 °C protease) are estimates anchored on orderings, not measured magnitudes.

## 5. Sources

Akamatsu et al. 2024 *Heliyon* 10:e33664 · Oguro et al. 2019 *J Biosci Bioeng* 127:570 · Hasegawa & Funakoshi 2016 *Aichi Center Res Rep* 5:108 · Su et al. 2005 *J Agric Food Chem* 53:1521 · Ohnishi 1982 *Nippon Shokuhin Kogyo Gakkaishi* 29:85 · Kusumoto et al. 2021 *J Fungi* 7:579 · Chancharoonpong et al. 2012 *IJBBB* 2:228 · Narahara et al. 1982 *J Ferment Technol* 60:311 · Kitano et al. 2002 *J Biosci Bioeng* 93:563 · Mishiro et al. 2000 *J Brew Soc Jpn* 95:74 · Ito & Matsuyama 2021 *J Fungi* 7:658 · Bombara et al. 1994 *J Food Biochem* 18:31 · Watanabe et al. 2007 *BBB* 71:2557 · Matsushita-Morita et al. 2010, 2013 · Gao et al. 2018 *Food Chem* 240:377 · Chiou et al. 2001 *J Food Sci* 66:1080 · Siringan et al. 2006 *Food Chem* and *J Sci Food Agric* · Lopetcharat & Park 2002 *J Food Sci* 67:511 · Udomsil et al. 2011 *J Agric Food Chem* 59:8401; 2022 *J Food Sci* 87:5375 · Gildberg 2001 *Bioresour Technol* 76:119 · te Biesebeke et al. 2002 *FEMS Yeast Res* 2:245 · Bechman et al. 2012 *J Food Sci* 77:M318.

The Taka-amylase half-life, "LAP stable to 60 °C" and the Narahara details come from search snippets and abstracts only; they are used as orderings, not magnitudes.
