# Fermentation Forecast — Kinetic Ensemble Model, Estimated Temperature, Forecast Panel — Design

**Date:** 2026-09-24
**Status:** DRAFT for owner review (implemented on branch `personal-/gifted-brahmagupta-zi8cqz`)
**Builds on:** `2026-09-23-ingredient-nutrients-design.md` and `2026-09-23-usda-food-catalog-design.md` (recipe × USDA → starting composition), `2026-09-23-fermentation-biochemistry-design.md` (organism set per batch, KEGG enzyme graph), `docs/DEPENDENCIES.md` §1 (the vendored Monod twin), `docs/STRATEGY.md` Direction 3 (honesty constraint).

## Problem and goals

The owner asked for (1) an **estimated fermentation temperature** the front end can set per batch, and (2) **predictive modelling of how a fermentation evolves** ("PINNs, Monod, graph neural networks, or the best model you find necessary"), with (3) a good interface for it.

Goals: a forecast for every fermentation type the app knows (pH, sugars, acids, ethanol, CO₂, microbial populations, koji growth and enzyme activity), with honest uncertainty bands, milestones ("pH below 4.6 in ~3 days (2–5)"), a what-if temperature control, and automatic calibration on the readings the user logs. Constraints: no training data exists (zero past batches), readings are sparse (0–10 manual points; sometimes an iSpindel stream), the backend runs on Render's free tier (0.1 CPU, 512 MB), numpy/scipy only.

Non-goals: food-safety decisions (the Safety Advisory keeps evaluating measured values only), cheese ripening, flavour prediction, vessel geometry.

## Decisions

| Question | Decision | Rejected, and why |
|---|---|---|
| Model family | **Mechanistic multi-species kinetic ODE** (Monod growth, Pirt / Luedeking–Piret substrate and product fluxes, Rosso CTMI temperature and CPM pH cardinal models, gamma-concept water activity, undissociated-acid and ethanol inhibition, Baranyi–Roberts lag), with literature priors | **PINN:** the forward problem is a non-stiff ODE with < 30 states that `solve_ivp` solves in milliseconds; with 0–10 points the inverse problem is information-limited, and PINNs at best match classical ODE + estimation (Grossmann et al. 2024; regularised PINNs "very close to" NLS, Wang 2026), with known failure modes on stiff kinetics and noisy sparse data (Krishnapriyan et al. 2021; Ji et al. 2021) and torch does not fit the 512 MB instance. **GNN:** needs hundreds to thousands of labelled samples (Andersen et al. 2025 used ≥100 per dataset); with zero batches its weights are untrained noise. Both stay on the later path (§9). |
| Role of the KEGG graph | **Structure, not learning:** the batch's organism set (type defaults or per-batch overrides from `/biochemistry`) decides which kinetic modules exist; each organism pathway is checked against the organism's KEGG enzymes and reported as provenance (`in_reference_graph`) | A GNN over the graph (no data); inferring kinetics from EC numbers alone (the graph lacks invertase, phosphoketolase, gluconate dehydrogenase, § 8) |
| Uncertainty | **Prior ensemble** (every uncertain quantity is a literature median + ~90 % range, sampled in standard-normal z-space) and **adaptive multiple importance sampling** (AMIS, Cornuet et al. 2012) on the batch's readings, Student-t errors, likelihood tempering if the readings sit outside the model's range | Plain importance sampling (collapses: 2/256 effective members after two pH points in a prototype); Laplace (sloppy parameters, overconfident); EnKF (Gaussian, handles lag/thresholds poorly); MCMC (too slow per request). Tempered SMC was the research recommendation; AMIS reached the same coverage at ~4 solves instead of ~9 (§ 5) |
| Compute | All members integrated at once as one stacked ODE (vectorised numpy, RK23); per-request, cached on an input fingerprint (inputs + hour); what-if re-simulates a 96-member resample of the cached posterior | Compute on write + store (needs a table and invalidation; the cache is simpler and correct because the key covers every input). Revisit if Render latency is a problem (§ 7) |
| Temperature | New nullable `batches.expected_temperature_c` (−5…60 °C; 60 is the ceiling for koji garum, and the bound catches Fahrenheit room temperatures), set on create or `PATCH /batches/{id}`. Past = logged temperature readings; future = the estimate (or the what-if). An estimate carries an uncertain offset (±1.5 °C) in the ensemble | Treating the estimate as a measurement (it is not; logged readings stay `Measurement` rows); feeding it to the Safety Advisory (it evaluates measured values only) |
| Koji, miso, garum | Modelled, but flagged **`confidence: "exploratory"`** with a visible banner: enzyme- and halophile-driven, little published kinetics | Omitting them (the owner asked for forecasts of "the ferments"); presenting them like the established types |
| API | One read endpoint `GET /batches/{id}/prediction?temperature_c=&horizon_h=` | Folding into `/preview` (its docstring forbids it) |

## 1. Model

State per ensemble member (g per kg of batch ≈ g/L for liquids): sucrose, hexoses (glucose + fructose + galactose), lactose, maltose, starch (enzyme-accessible), protein, free amino acids, ethanol, lactic, acetic and gluconic acid, cumulative CO₂, koji enzyme activity (0–1 = a fully grown koji); per organism ln(biomass) and the Baranyi lag state ln q.

Per organism *j* (`engine.py`):

```
μ_j   = μmax·γT(T)·γpH(pH)·γHA·γaw·γEtOH·γO2 · f_sub · q/(1+q) · (1 − X/Xmax)
v_j   = μ_j·X/Y + m·γT·γpH'·γHA'·γaw·γEtOH·γO2 · f_sub · q/(1+q) · X     (g substrate/kg/h)
dlnX/dt = μ_j − k_d·[(1 − stress) + 0.5·(1 − f_sub)]
dlnq/dt = μmax·γT·stress                                                   (Baranyi & Roberts 1994)
```

- γT: CTMI (Rosso et al. 1993). γpH: CPM (Rosso et al. 1995). γHA: `(1 − [HA]/MIC)₊` for undissociated lactic and acetic acid (Presser et al. 1997). γaw: `(aw − aw_min)/(1 − aw_min)` (Zwietering et al. 1992); halophiles (*T. halophilus*, *Z. rouxii*) use a cardinal model with their optimum below aw 1. aw from water-phase NaCl: `ln aw = −2·m·φ(m)·0.018` (NaCl osmotic coefficients). γO2 = 0 for obligate aerobes in closed ferments; for kombucha/vinegar a surface oxygen-transfer factor (Cvetković et al. 2008).
- **Acid production outlasts growth:** the non-growth flux (γpH', γHA') uses a pH minimum 0.3 lower and 2.5× the acid MIC (Brandt et al. 2004: *L. sanfranciscensis* stops growing at pH 4.0, stops acidifying at ~3.8; Luedeking–Piret β, Passos et al. 1994). This is what lets sauerkraut reach 1.5–2 % acidity.
- **Channels:** each organism's flux is split across its routes (e.g. *A. aceti*: ethanol → acetic acid, glucose → gluconic acid) by substrate availability, at fixed mass yields (alcoholic 0.47 ethanol + 0.45 CO₂; homolactic 0.90; heterolactic 0.45 lactic + 0.12 ethanol + 0.10 acetic + 0.22 CO₂; acetic oxidation 1.20; gluconic 1.05). Disaccharides and starch count as hexose equivalents (360/342, 180/162). Yeast invertase splits sucrose (Km 10 g/L).
- **Enzymes:** koji enzyme activity grows with mould growth (Luedeking–Piret) and decays first-order (Q10 1.5). Starch and protein hydrolysis are first order in substrate, scaled by an enzyme temperature curve fitted to rice-koji saccharification (66/100/92/77 % of best at 40/50/60/70 °C, Oguro et al. 2019), a salt factor (A. oryzae proteases keep ~30–60 % at 12–18 % NaCl, Ito & Matsuyama 2021) and an access factor (0.05 in the solid koji bed: free glucose barely rises there, te Biesebeke et al. 2002). Flour amylases (sourdough) and fish proteases (garum) are matrix enzymes. 80 % of protein is hydrolysable.
- **Koji mould** grows logistically on the starch it digests (standard solid-state model) and respires (0.8 g CO₂/g).
- **pH** is not a state: it is solved from the charge balance of lactic (pKa 3.86), acetic (4.76) and gluconic (3.70) acid against a ladder of matrix buffer groups (pKa 3.5…7.5) sized to the matrix buffer capacity, with a net strong-ion term set so the matrix starts at its own pH; acids carried in by a starter then lower the starting pH. Davies ionic-strength correction on the acid pKa (capped at I = 0.5). Safeguarded Newton, warm-started.
- **Gravity / Brix:** `SG = 1 + Σ kⱼ·cⱼ/998.2` (sucrose 0.384, ethanol −0.18, lactic 0.22, acetic 0.14 …) and refractometer Brix with ethanol reading 0.44 °Bx per % w/w; an ensemble offset stands for untracked solids and device bias.

## 2. Inference and uncertainty (`inference.py`)

1. Draw 160 members z ~ N(0, I) (one column per parameter, plus one for untracked dissolved solids); simulate all at once.
2. No readings: report weighted quantiles (5/50/95 %) of that ensemble (`status: "prior_only"`).
3. Readings: log-likelihood with Student-t (ν = 4) errors, σ² = measurement² + model discrepancy² (pH 0.15 + 0.15; gravity 0.002 + 0.003; Brix 0.3 + 0.8). While the effective sample size is below 30 % of N (max 3 rounds): fit a diagonal Gaussian to the weighted members (variance × 1.5, clipped to [0.05, 1]), draw 160 more, and re-weight **all** members against the mixture of every proposal so far (deterministic-mixture weights keep the estimate unbiased).
4. If ESS < 15 the likelihood is tempered (largest exponent keeping ESS ≥ 15) and a warning says the readings sit outside what the model explains.
5. Output: weighted 5/50/95 % bands per series on a 161-point grid; milestone first-crossing times per member (linear interpolation; never reached = +∞, so a quantile beyond the horizon is `null`) and the weighted probability of reaching it.

Readings used: `pH` (1.5–9), `gravity` (0.95–1.2 SG; a stream with any value > 1.5 is treated as °Plato and converted, per stream not per reading), `brix` (0–60) — density only for clear-liquid types (kombucha, vinegar). Streams with more than 30 points are binned (≥ 6 h bins): correlated iSpindel readings must not make the bands falsely tight. `temperature` readings are forcing, not observations.

## 3. Inputs (`service.py`)

- **Starting composition:** recipe quantity × USDA per-100 g values. Glucose/fructose/galactose → hexoses; sugars without a breakdown go to the type's default (lactose for dairy); starch estimated as carbohydrate − fiber − sugars when SR Legacy omits it (flours, rice — stated in the assumptions); salt as water-phase % (drives aw). Unmapped items (starters, tea) count as mass, assumed ~90 % water. For koji and miso, a recipe below 35 % / 45 % water is taken as dry weights of soaked-and-cooked grains/beans (water added, with a warning). No quantified recipe with fermentable substrate → a typical recipe for the type, with a warning.
- **Starter:** a `starter`-role ingredient's mass share carries over the starter's acids and shifts inocula (log₁₀ of logged vs typical share, clamped −1.5…+1); none logged → a typical share, stated.
- **Organisms:** `_resolve_batch_organisms` (defaults or overrides). Unknown organisms are listed as not modelled; obligate aerobes in closed ferments are shown as not growing; the koji mould in miso/garum contributes only its enzymes.
- **Temperature schedule:** piecewise linear through logged readings (exact), the estimate (or type default) where nothing was logged, and the forecast temperature from now on. Readings outside −5…60 °C are ignored with a "°F?" warning.

## 4. Priors (`organisms.py`, `profiles.py`)

Every organism has cited priors for μmax, cardinal T/pH, acid MICs, aw minimum, ethanol tolerance, yields, non-growth flux, carrying capacity, lag and death rate; "est." marks reasoned estimates. Key sources: *S. cerevisiae* Salvadó et al. 2011, Luong 1985; *L. plantarum* Passos et al. 1993/1994, Aryani et al. 2016; *Leuconostoc* Dols et al. 1997, McDonald et al. 1990; *L. sanfranciscensis* Gänzle et al. 1998, Brandt et al. 2004; *L. lactis* Boonmee et al. 2003, Chen et al. 2015, Åkerberg et al. 1998; *K. marxianus* Ospanova et al. 2026, Tinôco & da Silveira 2021; *Acetobacter* Moreno-Zambrano et al. 2018, de Ory et al. 1998, El-Askri et al. 2022; *T. halophilus* Justé et al. 2014, Röling & van Verseveld 1997; *Z. rouxii* Jansen et al. 2003; *A. oryzae* te Biesebeke et al. 2002, Bechman et al. 2012, Oguro et al. 2019, Ito & Matsuyama 2021. Weakly supported (estimates): *K. xylinus*, *L. kefiri*, *L. kefiranofaciens*, *T. halophilus*, *Z. rouxii* growth rates, all lag times, Ks, salt effects on koji enzymes.

Per-type matrices: buffer capacity derived from titratable acidity vs pH (cabbage ~35, milk ~35, dough ~20, sweet tea ~2 mmol/kg/pH; Hong et al. 2016, Salaün et al. 2005), starting pH, typical recipe, inoculum (natural 10⁴–10⁶ LAB/g on cabbage, Plengvidhya et al. 2007; a SCOBY or vinegar mother brings pellicle-level acetic acid bacteria), carrying-capacity overrides (nitrogen-poor tea keeps yeast at 10⁶–10⁷), oxygen factor.

**Calibration to published trajectories.** Parameters without a direct measurement (dry mass per CFU, kombucha/vinegar oxygen factors, invertase rate, koji μmax) were set so the prior median lands in the published range, and the tests pin that down:

| Type | Published behaviour | Source | Test |
|---|---|---|---|
| Sauerkraut (18 °C) | pH ≤ 3.9 by ~day 7, 3.4–3.7 at day 14; LAB → 10⁸–10⁹ CFU/g; 1.5–2.3 % acidity; *Leuconostoc* → *L. plantarum* succession | Plengvidhya et al. 2007; Pederson & Albury | `test_sauerkraut` |
| Kombucha (24 °C) | pH ~5 → ~3 by day 12; acetic acid rising over 2 weeks; ethanol a few g/L; sucrose ~4 g/L/day | Jayabalan et al. 2007; Chen & Liu 2000 | `test_kombucha` |
| Sourdough (25–30 °C) | pH → 3.8–4.2 in 8–16 h; LAB ~10⁹, yeast ~10⁷ CFU/g | Minervini et al. 2012 | `test_sourdough` |
| Cheese (30–32 °C) | pH 6.6 → 5.2–5.4 in ~4–6 h | Poudel et al. 2022 | `test_cheese_acidification` |
| Kefir (20–25 °C) | pH 4.2–4.6 at 24 h, 0.8–1 % lactic | Irigoyen et al. 2005 | `test_kefir` |
| Vinegar (static, mother) | 1–3 g/L/day; 4 % in 3–8 weeks | El-Askri et al. 2022 (est.) | `test_vinegar` |
| Koji (30 °C) | harvest at 40–48 h; little free glucose in the bed | Ito & Matsuyama 2021; te Biesebeke et al. 2002 | `test_koji` |
| Miso | pH → 4.8–5.3 over months; starch in weeks, protein over months | Allwood et al. 2021 | `test_miso` |

## 5. Validation so far (and what it does not show)

- **Self-consistency of calibration** (synthetic batches drawn from the prior, noisy pH readings, 90 % band coverage of the hidden truth's future, 8–24 trials each): sauerkraut 0.93 (2 readings) / 0.96 (6), kombucha 1.00, cheese 0.88, kefir 1.00, sourdough 0.84 — bands narrow by 25–45 % vs the prior. Sourdough's slight under-coverage comes from estimating tail quantiles with ~110 effective members; more members would fix it at a CPU cost.
- **Not validated against real batches.** `model.validated` is `false` and the UI says so. The validation trigger (before any "validated" label): for batches with ≥ 3 readings, predict later readings from earlier ones (leave-future-out), requiring 85–95 % interval coverage and a CRPS better than a type-average curve.

## 6. API contract

`GET /batches/{id}/prediction` → `PredictionOut` (`schemas.py`): `model` (name, version `kinetic-v1`, method, members, effective_members, confidence, validated, sources), `now_h`, `horizon_h`, `horizon_options_h`, `temperature` (forecast_c, source override|expected|measured|type_default, type_default_c, range_c, readings), `status` (prior_only|calibrated), `series[]` (key, label, unit, group ph|density|substrates|products|growth|population, `t_h`, `p05`, `p50`, `p95`), `observations[]` (key, t_h, value, used), `milestones[]` (key, title, note, label, threshold, `t_h` p05/p50/p95 or null, probability), `reference_lines[]` (the pH 4.6 line where it applies), `organisms[]` (modelled, growing, role, note, series_key, pathways with EC numbers and `in_reference_graph`, sources), `initial` (recipe|typical_recipe + values), `assumptions[]`, `warnings[]`, `disclaimer`. Query: `temperature_c` (−5…60, what-if from now on, nothing saved), `horizon_h` (0…8760). Errors: 404, 422.

`PATCH /batches/{id}` (`target`, `expected_temperature_c`; only fields present change, null clears). `POST /batches` accepts `expected_temperature_c`. Migration 0012 adds the column (nullable; batch_alter_table so the downgrade works on SQLite).

## 7. Honesty, labelling, performance

- The disclaimer is always visible: "Model estimate from literature kinetics, not a measurement … Never use this to decide food safety: measure pH." Milestones are worded as thresholds ("pH below 4.6 — the food-safety acidity threshold; confirm with a pH reading"), never "safe by". The Safety Advisory is untouched and still evaluates measured values only.
- Status line distinguishes "literature priors only" from "calibrated on N of your readings"; exploratory types carry a banner; not-modelled organisms, typical-recipe fallbacks, dry-weight assumptions, ignored readings and tempered calibration are all warnings.
- Performance: 0.05–0.5 s per forecast on a dev core (≤ 4 ensemble solves), what-if ~0.1 s, cached repeats instant; expect ~10× on Render's 0.1 CPU. The solve runs in the threadpool (the event loop stays free). The cache holds outputs and posterior z/weights only (~KB–MB), 64 entries.

## 8. Limitations and open questions

1. **Kombucha yeasts** are mostly *Brettanomyces*/*Zygosaccharomyces*; *S. cerevisiae* kinetics stand in. **Oxygen** (vessel surface/volume) drives kombucha and vinegar; the model cannot see it (a vessel-geometry field would help).
2. **Reference-graph gaps** (suggested curation, EC numbers unverified against KEGG): invertase 3.2.1.26 (kombucha, sourdough yeast), phosphoketolase 4.1.2.9 (heterolactic LAB), glucose dehydrogenase 1.1.5.2 (gluconic acid), maltose phosphorylase 2.4.1.8 (*L. sanfranciscensis*), phospho-β-galactosidase 3.2.1.85 (*L. lactis*), cellulose synthase 2.4.1.12 (*K. xylinus*). The UI marks such pathways "not yet in the reference graph".
3. Koji self-heating, cheese whey drainage/salting/ripening, and sugar-driven water activity (sweet miso) are not modelled.
4. **Owner decisions:** keep koji/miso/garum as exploratory forecasts or hide them? Feed `expected_temperature_c` into the Safety Advisory when no temperature was logged (currently not, by design)? Add a vessel-geometry field?

## 9. Later path (triggers, in the style of `docs/DEPENDENCIES.md`)

- **Hierarchical priors** — trigger: ~20–30 batches of a type with ≥ 3 readings. Fit a population distribution over per-batch posterior shifts (rate, lag, endpoint) with covariates (temperature, salt, sugar, starter share); it becomes the next batch's prior. Real learning, no neural network (Pouillot et al. 2003).
- **Hybrid / universal differential equation** — trigger: hundreds of batches, ideally with dense iSpindel data, and Stage A in place. A tiny neural residual on μ (μ = μ_mech·exp(NN)), trained offline, exported as numpy weights; ships only if it beats Stage A on held-out batches (Psichogios & Ungar 1992; Rackauckas et al. 2020).
- **GNN** — only once thousands of batches with varied organism sets exist, as a predictor of parameter priors; baseline is regression on guild indicators.
- **PINN** — only for a spatial problem with dense sensors (salt/acid diffusion into vegetable pieces, O₂ under a pellicle, heat in a koji bed), and only if it beats finite-volume + estimation.

## References (models and methods)

Baranyi & Roberts 1994 Int J Food Microbiol 23:277 · Rosso et al. 1993 J Theor Biol 162:447 · Rosso et al. 1995 AEM 61:610 · Zwietering et al. 1992 J Food Prot 55:973 · Presser et al. 1997 AEM 63:2355 · Luedeking & Piret 1959 · Cornuet, Marin, Mira & Robert 2012 Scand J Stat 39:798 (AMIS) · Price et al. 2020 J Food Sci 85:918 (buffer capacity models) · Salaün et al. 2005 Int Dairy J 15:95 · Cvetković et al. 2008 J Food Eng 85:387 · Grossmann et al. 2024 IMA J Appl Math 89:143 · Krishnapriyan et al. 2021 NeurIPS · Ji et al. 2021 J Phys Chem A 125:8098 · Andersen et al. 2025 Nat Commun · Pouillot et al. 2003 Int J Food Microbiol 81:87 · Rackauckas et al. 2020 arXiv:2001.04385. Organism and trajectory sources: § 4 and the `sources` fields in code.
