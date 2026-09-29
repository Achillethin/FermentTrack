# Sourdough Engine — Levain Styles, Rise, Acidity, Per-Starter Learning — Design

**Date:** 2026-09-28
**Status:** APPROVED by owner in chat (2026-09-28); implementing on `feat/sourdough-engine`
**Builds on:** `2026-09-24-fermentation-prediction-design.md` (kinetic ensemble, AMIS), `2026-09-28-population-pooling-design.md` (superseded by § 6 here)

## Problem and goals

The owner wants a sourdough engine a baker friend can use: every common levain/sourdough style, reaction kinetics that depend on the levain used, integrated in the backend and the app. Audience: both a serious home baker (when does my levain peak, when is bulk done, how sour) and a professional (TTA, lactic:acetic ratio, multi-stage builds, clock schedule), the latter behind a "Pro" toggle. Readings a baker may take: jar rise (%), pH, TTA, or nothing (timing only). All three slices ship: kinetics core, a stateless planner, tracked-batch integration. Owner addition: the model learns **each starter** (per user levain), with a general default that inherits a global class.

Non-goals: baking (oven spring, crumb), flavour volatiles, gluten rheology beyond a rise cap, food-safety claims (sourdough is not judged against pH 4.6 here).

## Decisions

| Question | Decision | Rejected, and why |
|---|---|---|
| Engine | **Extend `kinetic-v1`**: styles are data (organisms, ripe-starter populations, acids, defaults); new physics is small and opt-in (only when set, other ferments are bit-identical) | A standalone doubling-time calculator (no pH/sourness, cannot learn from readings); ML (no data) |
| Inoculum | Ripe-starter population per style (log CFU/g **in the starter**) + log10 of the seed's share of the build: an exact dilution | The profile's clamped `starter_fraction` shift (breaks at 1:20:20) |
| Buffer | **β_flour(ash) × flour share of the phase** (mmol/kg/pH): hydration and flour grade now move pH and TTA. French T-numbers are ash × 1000, so the flour grade is the model parameter | A per-type constant per kg of batch (a liquid levain then buffers like a stiff one) |
| Sourness | Heterolactic C2 branch split φ between ethanol and acetate: φ = φ_ref·(100/hydration)^0.8·2^((25−T)/10), clipped to [0, 0.95]. The 0.8 exponent reproduces the 2.4× FQ ratio between dough yield 160 and 280 (Minervini 2014); stiff/cool = more acetic | Fixed channel yields (hydration and temperature could not change sourness) |
| *K. humilis* | Maltose-negative: lives on glucose that *L. sanfranciscensis* excretes (maltose phosphorylase: half of each maltose leaves the cell as glucose) | Letting it ferment maltose (wrong; it would out-compete S. cerevisiae in the model) |
| Rise | Post-solve gas balance per member: CO₂ first saturates the dough water (Henry, 1.6×10⁻⁵ → 5×10⁻⁶ g/(kPa·g) from 0 to 50 °C), the excess inflates gas, gas leaks at k₀ + k₁·weak(pH) and stops being retained as the rise nears R_max(flour gluten); a cooling dough re-dissolves gas. Peak = argmax | A Gompertz curve fitted per style (descriptive only: no link to temperature, ratio, flour) |
| Phases | Levain build → mix (dilute state by levain share, add flour/water/salt/yeast) → bulk → proof or cold retard. One z-vector per member across phases (same organism parameters); each phase is one `simulate` with its own `y0` | One matrix for the whole bake (salt at mixing and the dilution into the dough are what bulk timing depends on) |
| Readings | `rise` (%, σ = 10 + 20 pp) and `tta` (mL 0.1 N NaOH / 10 g to pH 8.5, σ = 0.5 + 1.5) join pH in the AMIS likelihood (Student-t); all σ are estimates | Rise only (pH/TTA readers exist, and TTA identifies the buffer) |
| Planner | Stateless `POST /sourdough/plan` and `POST /sourdough/feeding-chart` (ratio → peak band, one stacked solve), both behind auth (anon sign-in), optional `culture_id` for a learned starter | A public endpoint (CPU on the free instance) |
| Batch | Nullable `batches.sourdough_plan` (JSON, the same schema as the planner). Mix/shape times come from logged stage changes, else from the plan. For a batch with a plan, **the style's organisms replace the type defaults** (custom attachments still add) | Re-deriving levain vs dough from the free-form recipe (not recoverable) |
| Learning | **Crossed hierarchy** (§ 6): global class → levain type + baker → starter → batch, additive in z-space, exact Gaussian conditioning on stored per-batch **likelihood summaries** (AMIS posterior with its own prior divided out) | The SEM plug-in (overconfident as n grows, pools prior information back into itself); a nested-only tree (a baker's second starter would learn nothing from the first) |

## 1. Styles (`prediction/sourdough.py`)

| key | Style | Type | Organisms (ripe log CFU/g) | Defaults |
|---|---|---|---|---|
| `home_starter` | Home wheat starter | I | *S. cerevisiae* 7.5, *L. plantarum* 8.7, *L. brevis* 8.7 | 100 %, 1:5:5, 24 °C |
| `levain_liquide` | Levain liquide | I | *L. sanfranciscensis* 9.2, *S. cerevisiae* 7.4 | 100–125 %, 1:3:3, 26 °C |
| `levain_dur` | Levain dur (stiff) | I | *L. sanfranciscensis* 9.0, *K. humilis* 7.3, *S. cerevisiae* 7.0 | 55 %, 1:3, 24 °C |
| `lievito_madre` | Lievito madre | I | *L. sanfranciscensis* 8.9, *K. humilis* 7.5 | 45 %, 1:1, 27 °C, young |
| `san_francisco` | San Francisco | I | *L. sanfranciscensis* 9.3, *K. humilis* 7.4 | 50 %, 1:2.5, 27 °C, 8 h |
| `rye_sour` | Rye sour (Roggensauer) | I | *L. sanfranciscensis* 9.0, *L. brevis* 8.7, *K. humilis* 7.2 | 90 % rye T130, 1:10, 28 °C |
| `type_ii` | Liquid sour (Type II) | II | *L. reuteri* 9.3 | 200 %, 1:10, 37 °C, acid only |
| `type_iii` | Dried sourdough (Type III) | III | none (acids) | dough additive, needs yeast |
| `poolish` / `biga` | Pre-ferments (Type 0) | 0 | *S. cerevisiae* from 0.1 % / 0.5 % yeast | 100 % / 50 %, 18–20 °C |

New organisms (priors in `organisms.py`, "est." where thin): *Kazachstania humilis* (Topt 27–28 °C, no growth > 35–36 °C, pH-insensitive 3.5–5.5, acetate stops it at ~140–175 mM; Gänzle 1998, Brandt 2004, Carbonetto 2020), *Lactobacillus brevis* (heterofermentative, maltose-positive, Topt ~32 °C), *Lactobacillus reuteri* (Type II, Topt ~39 °C; Gänzle & Vogel 2003). Pre-reclassification names, as for the existing lactobacilli. Migration 0016 adds their reference rows (no enzyme links yet: pathways show "not in the reference graph").

Flours (`FLOURS`): T45, T55, T65, T80, T110, T150, rye T85/T130/T170, with US names; per flour: ash, protein, starch, free sugars, a gluten factor (rise cap: 1.0 white → 0.35 whole rye) and an amylase factor (rye 2.0, whole wheat 1.3). A phase may blend flours (fractions); properties are mass-weighted.

## 2. Physics added to the engine

- `simulate(p, t_eval, y0=None)`: a phase starts from a given state.
- `EnsembleParams.c2_acetate` (N,) φ at 25 °C, None elsewhere; φ(T) in the rhs; applies to channels producing both lactic acid and ethanol. C2 is conserved in moles (1 mol ethanol ↔ 1 mol acetate).
- `Trajectories.extra`: derived series (rise, TTA, FQ) the likelihood can use; `inference.run` calls `spec.simulate_z(z, t_eval)` when the spec provides it.
- `Milestone.kind = "max"` (time of the maximum, only if the series has turned down by 3 %).
- TTA = 100 × base (mol/kg) to bring the charge balance from the current pH to 8.5.

## 3. Plan (shared by planner and batch)

```
style; starter: ripe | refrigerated (lag × 3)
levain: seed_g, flour_g, water_g, flour {key: share}, temperature_c, hours? (None = mix at the median peak)
dough?: flour_g, water_g, salt_g, flour, temperature_c, levain_g? (None = all), yeast_g, yeast: instant | fresh,
        dried_sour_g (Type III), bulk_hours? (None = until target_rise_pct, default 75)
proof?: temperature_c, hours
```

## 4. Outputs

`PredictionOut` plus `phases[]` (key, label, start_h, end_h, temperature_c) and `summary` (hydrations, seed ratio, levain % of dough flour). Series: `rise` (group rise, %), `ph`, `tta` and `fq` (group acidity), lactic/acetic acid, maltose/glucose, populations. Milestones: levain doubled, levain peak, bulk target rise, pH 4.2/4.0. The feeding chart returns, per ratio 1:r:r, the peak time band and pH at peak.

## 5. Validation (tests pin these)

| Behaviour | Source |
|---|---|
| Home starter 1:1:1 peaks in 4–8 h at 24–26 °C; 1:5:5 in 8–16 h at 22 °C and faster at 27 °C | King Arthur 2025; baker charts |
| Ripe white levain pH 3.7–4.3; whole-grain/rye TTA > white at the same pH | Minervini 2012; ash–buffer relation |
| Stiff (55 %) more acetic than liquid (125 %); 20 °C more acetic than 30 °C | Minervini 2014; review 2020 |
| *K. humilis* grows only with *L. sanfranciscensis* glucose; slows above 33 °C | Carbonetto 2020; Brandt 2004 |
| Salted bulk dough rises slower per cell than the unsalted levain; retard at 4 °C nearly stops rise | Gänzle 1998 (4 % NaCl) |
| Existing sourdough/other-type tests unchanged | — |

**Known calibration gap (2026-09-28):** the prior's median levain peak is ~1.5-2x slower than the fastest baker rules of thumb at low dilution (1:1:1 at 25.6 °C: median ~11 h, p05 ~6.5 h, vs "4-8 h"); at 1:4:4 the band (8.6-22.6 h) covers the ~12 h reported. The rise sub-model is phenomenological (saturation, retention cap, leak growing with cumulative acid exposure); its four parameters are the first thing jar readings recalibrate. Next step: fit the rise parameters to published dough-volume curves (Romano et al. 2007; Landis et al. 2021 rise data) instead of rules of thumb.

## 6. Learning per levain type, per baker, per starter (`prediction/population.py`, replaces the plug-in pooling)

Owner requirement: "Achille's classic levain" inherits the **classic levain** class *and* **Achille**; "Aymard's rye levain" inherits the **rye** class and **Aymard**. So the effects are crossed and additive, per organism and pooled parameter (`mu_max`, `t_opt`), in the **literature prior's z-units** u (the literature prior is exactly N(0, 1) there):

```
θ_batch = g + d_style + a_user + e_starter + ε      (all independent, zero-mean Gaussian)
var:      v_g   v_k      v_u      v_s        ω       = 0.30 + 0.20 + 0.10 + 0.30 + 0.10 = 1
```

- The variances sum to 1, so with no data anywhere a batch's prior is exactly the literature prior (**the general default inherits the global class**). A new starter of a known style and baker inherits that style's and that baker's learned effects; nothing is double counted because it is one joint Gaussian model.
- **Evidence per finished batch** (table `batch_evidence`): for each modelled organism × pooled param, the batch's **likelihood summary** (ℓ, λ): map its AMIS posterior samples to u, weighted mean/variance, divide out the prior the batch actually ran with (Gaussian division): λ = 1/v_post − 1/v_prior, ℓ = (m_post/v_post − m_prior/v_prior)/λ. A batch that narrowed the prior by < 10 % carries no information on that parameter and stores nothing. Rows keep culture, owner, style, organism, param, ℓ, λ: raw evidence, so variance components can be re-estimated later (REML) without re-running anything.
- **Prior for a new batch** of starter s (style k, baker j): exact Gaussian conditioning on all evidence rows y of that organism/param: Cov(y_b, y_b') = v_g + v_k[k_b = k_b'] + v_u[j_b = j_b'] + v_s[s_b = s_b'] + (ω + 1/λ_b)[b = b']; c_b = v_g + v_k[k = k_b] + v_u[j = j_b] + v_s[s = s_b]; mean cᵀΣ⁻¹y, variance 1 − cᵀΣ⁻¹c; mapped back through the literature split normal to a `Prior`. ponytail: O(n³) in the rows of one organism/param; switch to sufficient statistics per group past ~2000 rows.
- **Style** = the starter's levain type (`cultures.style`, e.g. `rye_sour`; falls back to the batch plan's style, then to the culture type for other ferments). **Baker** = the culture's `owner_id`. **Starter** = the culture.
- ponytail: the five variances are fixed fractions (est.); `scripts/` gains a REML estimator validated on synthetic data, to run once ≥ 5 starters have ≥ 3 batches. The old `population_priors` table is left in place, unused.

### 6.1 Revisions after the statistical review (2026-09-29)

- **Joint evidence.** A batch's likelihood summary is computed jointly over all pooled parameters (debiased weighted covariance C_post; Lambda = C_post^-1 - diag(1/v_prior), eigen-clipped); each parameter is stored with its conservative marginal precision 1/(Lambda^-1)_jj, so a ridge (mu_max x t_opt at one temperature) is not counted twice. The Monte Carlo variance of ell, diag(Lambda^-1 P_post Lambda^-1)/ESS, is added to 1/lambda.
- **Noise-aware gate.** A parameter is stored only if lambda v_prior > c/(1-c), c = 3 sqrt(2/ESS) (3 sd of a variance ratio's sampling error): pure Monte Carlo noise at production size leaves no rows. Nothing is learned from a tempered posterior, from readings the model flags as misfits, from a batch whose phase starts were not logged (sourdough), or below ESS 50; a finished batch whose display posterior is too thin gets one dedicated 480-member AMIS run.
- **Exact division.** Learned priors are exactly Gaussian in the literature z-units (`LiftedPrior`: value(z) = lit.value(m + sd z)), so prior-data conflict across the literature median divides out exactly.
- **Rise sub-model learned too.** phi_ref, rise_max, leak0, leak_acid are pooled under the pseudo-organism "(rise model)", so the rise model's error is not absorbed into mu_max.
- **t_opt** is learned only from batches spanning >= 4 °C.
- **Scope.** The global class and the baker effect are per ferment type (rows are filtered by type); only successful batches count (outcome stored); a missing style/baker label is a group of its own; baker's yeast is never pooled; a finished batch's own evidence is excluded from its displayed forecast.
- **Rise numerics.** The gas balance always steps on an internal 0.1 h grid (calibration grids no longer change the model); each phase is solved once (phase runner).
- **Bands.** Bulk-target times carry each member's own levain-peak offset when the mix is at the peak (not only the median one).

### 6.2 Re-estimating the hierarchy and validating forecasts (2026-09-29)

**Variance components** (`prediction/variance_components.py`, `scripts/estimate_variance_components.py`). Per ferment type × organism × parameter, the successful evidence rows follow ℓ_b = μ + d_k + a_j + e_s + ε_b + η_b with η_b ~ N(0, 1/λ_b) **known** (the likelihood summary is a noisy observation of θ_b): V = Σ θ_c Z_c Z_cᵀ + diag(ω + 1/λ_b). REML (not ML) over log-variances, L-BFGS-B with the analytic score; SEs from the observed information; 95 % log-scale Wald intervals, one-sided [0, θ̂ + 1.645 se] at or near the boundary. The intercept μ is **fixed** per group: g has one realisation per organism × parameter, so v_global is not identifiable there, and REML's contrasts annihilate 11ᵀ — the other four estimates are the same as with g random, and a literature median that is off for one organism cannot leak into v_style/v_starter. The **pooled** fit (per ferment type) shares the five variances across organism × parameter groups (assumed equal in u-space; groups independent), with g random of mean 0 exactly as in `population.py` — no fixed effect remains, so REML = ML — and is the only fit that estimates v_global (≥ 3 groups).

Identifiability (a refused component keeps its default, the others are estimated conditionally): ≥ 3 distinct levels per factor; ≥ 3 within-starter replicates (n − #starters) for ω; and the REML-projected matrices Q Z_c Z_cᵀ Q linearly independent — one batch per starter confounds starter with batch, one starter per baker confounds baker with starter, and every member of a confounded set is refused. Validation (`tests/test_variance_components.py`, 100 simulated designs of ~95 rows: 8 styles × 10 bakers, 2–3 starters per baker, 2–6 batches per starter, λ ~ Gamma(3, 2)): REML equals the ANOVA closed form on a balanced one-way design (SEs too); median relative error ~0.2 (batch), ~0.4 (starter), ~0.6 (style, 8 levels), ~0.8 (baker at 0.15, 10 levels), no gross bias; 95 % interval coverage 0.90–0.99; population.predictive with the estimates plugged in covers 87 % of held-out batches at 90 % (oracle variances: 90 %) — the plug-in ignores the estimates' own uncertainty.

**Forecast validation** (`scripts/validate_forecasts.py`, scores in `prediction/scoring.py`). Leave-future-out on finished batches with ≥ 3 readings: at each cut (a reading time), inputs are rebuilt as the app would have at that time (readings, temperatures and stage changes after the cut dropped; unfinished; learned priors from evidence recorded before the cut, never the batch's own); every later reading is scored against the posterior predictive (members + the likelihood's Student-t reading error): PIT, 50/90 % coverage, fair CRPS, skill vs the prior-only forecast and vs a climatology of earlier batches of the same type/style; 90 % intervals by bootstrapping batches. `band90` is the coverage of the drawn (latent) band and is expected below 0.9. Recipe, organisms, plan and expected temperature have no history and are taken as last edited.

Running: `FERMENTTRACK_DATABASE_URL=… python scripts/estimate_variance_components.py` (or `--csv export.csv`), and `… python scripts/validate_forecasts.py --out report.json [--variances '{…}']`.

**Decision rule.** Keep the fixed `VARIANCES` until (1) ≥ 5 starters have ≥ 3 successful batches each and the pooled fit converges with the components identifiable; (2) some default lies outside its component's 95 % interval (otherwise nothing is learned by switching); (3) `validate_forecasts.py --variances <proposal>` beats the current values on held-out readings: lower CRPS for every reading type with enough pairs (bootstrap interval of the skill difference above 0) and 90 % coverage within 0.85–0.95. Boundary or refused components keep their defaults. The proposal need not sum to 1: that constraint made the no-data prior equal the literature, and data now say how wide the population really is (Σ > 1: the literature range was too narrow). Switching then needs two small code changes: `VARIANCES` per ferment type (the fits are per type), and `learned_prior` with no rows returning N(0, Σv) instead of the literature (else a parameter's prior jumps from variance 1 to Σv at its first evidence row). Caveat: REML fitted on all evidence and then validated on the same batches is mildly optimistic; for a strict check re-estimate per cut from the evidence recorded before it. The "validated" label itself needs, per type, 90 % coverage in 0.85–0.95 and CRPS skill > 0 vs climatology.

## 7. API and app

- `GET /sourdough/catalog` (styles, flours, defaults: the UI's single source of truth), `POST /sourdough/plan`, `POST /sourdough/feeding-chart`.
- `POST/PATCH /batches` accept `sourdough_plan`; `GET /batches/{id}/prediction` uses the plan path for sourdough batches that have one.
- App: "Levain planner" screen (`frontend/src/sourdough/`, reached from the start screen and `#/levain`), style cards, feeding presets, flour grade (T-number + US name), temperature, start clock time; results: peak and bulk times with ranges and clock times, rise and pH charts, Pro toggle (TTA, lactic:acetic, acids, populations), feeding chart, "track this bake" (creates a batch with the plan). Batch view: plan card, new `rise` / `TTA` readings, rise and acidity charts.

## 8. Build order

1. Organisms + engine hooks (y0, C2 split, extra series, max milestone) — tests.
2. `sourdough.py` catalogue + plan compiler + chained simulation + derived series — calibration tests (§ 5).
3. Service output, planner and feeding-chart endpoints — API tests.
4. Hierarchical per-starter pooling + migration 0016 — math and router tests.
5. Batch integration (plan column, organisms, prediction path, readings).
6. Frontend planner and batch pieces; full suite; local run.

## References

Gänzle, Ehmann & Hammes 1998 AEM 64:2616 · Brandt, Hammes & Gänzle 2004 Eur Food Res Technol 218:333 · Carbonetto et al. 2020 Microorganisms 8:240 · Minervini et al. 2012 AEM 78:1251 · Minervini et al. 2014 AEM 80:3161 · Landis et al. 2021 eLife 10:e61644 · Gänzle & Vogel 2003 Int J Food Microbiol 80:31 · Romano et al. 2007 J Food Eng 83:142 · De Vuyst & Neysens 2005 Trends Food Sci Technol 16:43 · Stolz et al. 1993 FEMS Microbiol Lett 109:237 (maltose → glucose excretion) · King Arthur Baking 2025 (feeding ratios).

## Appendix A — API contract (frontend builds against this)

All routes need the usual `Authorization: Bearer <supabase jwt>`.

`GET /sourdough/catalog` →
```json
{"styles": [{"key": "levain_liquide", "name": "Levain liquide", "native_name": "Levain liquide",
             "type": "I", "seed": "starter", "description": "…one or two baker-facing lines…",
             "organisms": ["Lactobacillus sanfranciscensis", "Saccharomyces cerevisiae"],
             "defaults": {"hydration_pct": 100, "seed_ratio": 3, "temperature_c": 26,
                          "flour": "t65", "hours": null},
             "notes": ["…"], "sources": ["…"]}],
 "flours": [{"key": "t65", "name": "T65", "us_name": "Bread flour", "grain": "wheat",
             "ash_pct": 0.65, "protein_pct": 12.0}]}
```
`seed` is `starter` (ripe culture), `yeast` (poolish/biga: `seed_g` = grams of yeast) or `dried` (Type III: no build; use `dough.dried_sour_g`). `seed_ratio` r means feed 1 : r : r·hydration.

`POST /sourdough/plan` (body = the plan; the same JSON is stored on a batch as `sourdough_plan`):
```json
{"style": "levain_liquide", "starter": "ripe", "culture_id": null,
 "levain": {"seed_g": 20, "flour_g": 100, "water_g": 100, "flour": {"t65": 1.0},
            "temperature_c": 24, "hours": null},
 "dough": {"flour_g": 900, "water_g": 630, "salt_g": 20, "flour": {"t65": 0.9, "t150": 0.1},
           "temperature_c": 25, "levain_g": null, "yeast_g": 0, "yeast": "instant",
           "dried_sour_g": 0, "bulk_hours": null, "target_rise_pct": 75},
 "proof": {"temperature_c": 4, "hours": 14}}
```
`levain` is null only for `seed: dried`; `dough` and `proof` are optional (a levain-only plan answers "when does it peak"). `hours: null` = mix at the median peak; `bulk_hours: null` = end bulk at the median time to `target_rise_pct`. `starter`: `ripe` | `refrigerated` (longer lag).

→ `PredictionOut` (the batch forecast shape) plus:
```json
{"phases": [{"key": "levain", "label": "Levain", "start_h": 0, "end_h": 6.5, "temperature_c": 24},
            {"key": "bulk", "label": "Bulk", "start_h": 6.5, "end_h": 11.0, "temperature_c": 25},
            {"key": "proof", "label": "Cold retard", "start_h": 11.0, "end_h": 25.0, "temperature_c": 4}],
 "summary": {"style": "levain_liquide", "levain_hydration_pct": 100, "seed_ratio": "1:5:5",
             "levain_pct_of_flour": 20.0, "dough_hydration_pct": 72.0, "salt_pct_of_flour": 2.0,
             "total_flour_g": 1000}}
```
Series keys: `rise` (group `rise`, unit `%`), `ph` (group `ph`), `tta` (group `acidity`, unit `mL`), `fq` (group `acidity`, unit `mol/mol`, lactic:acetic), `lactic_acid`, `acetic_acid`, `ethanol` (group `products`), `maltose`, `hexoses` (group `substrates`), `pop:<organism>` (group `population`). Milestone keys: `levain_doubled`, `levain_peak`, `bulk_target`, `ph_below_4_2`, `ph_below_4_0`. All times are hours from the levain feed (t = 0); the app turns them into clock times from a start time the user picks.

`POST /sourdough/feeding-chart` `{"style", "flour": {"t65": 1}, "hydration_pct": 100, "temperature_c": 24, "starter": "ripe", "culture_id": null, "ratios": [1, 2, 3, 5, 8, 10]}` →
```json
{"temperature_c": 24, "rows": [{"ratio": 5, "label": "1:5:5",
  "peak_h": {"p05": 7.1, "p50": 9.4, "p95": 12.8}, "doubled_h": {"p05": …, "p50": …, "p95": …},
  "ph_at_peak": 4.1, "rise_at_peak_pct": 180}]}
```
A `null` inside a band means "not within 48 h".

Batches and cultures: `POST /cultures` accepts `style` (catalogue key, optional; the starter's levain type); `CultureOut.style`. `POST /batches` and `PATCH /batches/{id}` accept `sourdough_plan` (the plan object, or null to clear); `BatchOut.sourdough_plan`. New measurement types: `rise` (% above the level marked right after feeding/mixing) and `tta` (mL 0.1 N NaOH per 10 g). `GET /batches/{id}/prediction` returns `phases`/`summary` (empty/null otherwise) for sourdough batches with a plan; the mix and shape times follow the logged stage changes to `bulk_ferment` and `shape`.
