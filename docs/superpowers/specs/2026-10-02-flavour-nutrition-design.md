# Taste, Aroma and Nutrition Over the Fermentation — Design

**Date:** 2026-10-02
**Status:** APPROVED (2026-10-02). Increment A (nutrition, taste, lenses) IMPLEMENTED on `feat/taste-nutrition` — plan `docs/superpowers/plans/2026-10-02-taste-nutrition-increment-a.md`; increment B (aroma) pending curation.
**Builds on:** `2026-09-24-fermentation-prediction-design.md` (kinetic ensemble, AMIS, `PredictionOut`), `2026-09-28-sourdough-engine-design.md` (multi-phase bake path, TTA, FQ, `simulate(keep_states=True)`), `2026-09-23-ingredient-nutrients-design.md` (composition, lower-bound semantics), `2026-09-23-fermentation-biochemistry-design.md` (KEGG compound identity), `2026-09-25-frontend-design-system-pass.md` and `frontend/src/prediction/prediction.css` (chart tokens, dataviz method).

## Implementation notes (increment A, 2026-10-02)

- **Thresholds as panel distributions.** Taste thresholds are recognition thresholds in water with their between-person spread (Höhl et al. 2014, n = 70), so "P(above threshold)" reads as the share of people who would notice it in water. Sour uses the protonated-acid + H⁺ measure of Johanningsmeier et al. 2005.
- **Phase ramp** lives in `sensory.js` (`PHASE_HEX`, validated `--ordinal --mode dark --surface #191612`) rather than CSS tokens: blending a transition needs the hex values. A neutral reference-line tone (`--viz-ref-neutral`) keeps the amber `--viz-ref` for the pH 4.6 line.
- **Energy invariant** (§ 9) is tested in monosaccharide equivalents (3.75 kcal/g) on the raw solver states: on the EU label basis hydrolysis alone adds kcal (starch → glucose +11 % mass), and the zero-clipped display pools hide an RK23 overshoot at substrate exhaustion (vinegar: up to ~1–2 % extra acetic acid after the ethanol runs out). The overshoot is a pre-existing engine artifact, left for a separate engine change (an event at depletion or a step cap).
- **Sourdough planner** filters the taste/nutrition groups out of its Pro charts; the lenses are a batch-forecast feature.
- **Moved to increment B:** the dashed "plausible" tier in `ForecastChart` (it only exists with aroma compounds).
- **Measured cost** (dev core, prior-only forecasts, 160 members × 161 points): the derived layer takes 21–25 ms of 200–420 ms forecasts (6–11 %), mostly the weighted-quantile sorts; series that cannot pass their show-threshold skip the sort. Cached with the forecast; a what-if pays it again on 128 members.

## Problem and goals

The owner wants, next to the pH forecast, an overview of how **taste, aroma compounds and nutrients** evolve over a fermentation: "nutrition over time, and taste over time to know when to stop. Not precise at the day or the hour, but generally the dynamic." All three uses matter: deciding when to stop, knowing what you are eating, and understanding what is happening in the jar. The aroma side should show the complexity of a real ferment ("model as many odorants as you can"), not a token handful.

Goals:

1. **Nutrition over time** per 100 g of what is in the jar (energy, sugars, lactose, alcohol, acids, protein breakdown, carried-through fat/fibre/salt) with uncertainty bands, at start / now / end of window.
2. **Taste over time**: sweet, sour, umami, alcohol as activity relative to detection thresholds, plus a **taste phase** band (e.g. kombucha *sweet → balanced → tart → vinegary*) and loose milestones.
3. **Aroma over time**: ~85 curated odorants from microbial metabolism, the recipe's own ingredients and slow chemistry, grouped into aromatic series (fruity, buttery, sulfurous …), each with an evidence tier.
4. All of it conditioned by the same posterior as the forecast (your pH/gravity/TTA readings sharpen it), responsive to the what-if temperature and window, honest about uncertainty.

Constraints: numpy/scipy only, Render free tier (0.1 CPU, 512 MB), the forecast's solve must stay unchanged, never a food-safety claim.

Non-goals (this spec): a compound explorer page, micronutrients and bioactives (phytate, folate, vitamin C, GABA, biogenic amines), calibration from tasting ratings or TTA kits for non-sourdough types, bitterness, fizz (dissolved CO₂), spoilage odours, cheese ripening, baking (crust/crumb aroma), personal taste targets ("tell me when it is how I like it"). See § 10.

### Reversing two earlier decisions

- `docs/IDEATION_CONTEXT.md` killed a "Predictive Flavor Engine" because "KEGG → FlavorDB → perceived flavor is an inferential leap too far". This design does **not** predict perceived flavour. It predicts concentrations of identified compounds from mechanistic kinetics, and reports each against its detection threshold with a prior on that threshold (sensomics / odour activity value, Grosch 2001), as a **probability of being noticeable** and an **index of odour potential**. The inferential step that was rejected (compound list → "it tastes like X") is still not taken, and the UI wording forbids it (§ 7).
- The forecast spec and the sourdough spec list flavour / flavour volatiles as non-goals. This spec lifts that for the derived layer only; the kinetic model and its validation status are untouched.

## Decisions

| Question | Decision | Rejected, and why |
|---|---|---|
| Scope of the first spec | Nutrition + taste + aroma together, delivered in **two increments**: A (nutrition, taste, UI lens) needs no new data; B (aroma) ships once curation passes its tests | Nutrition+taste only (owner wants the compound side now); aroma first (blocks the cheap, grounded part on the slowest curation) |
| How the layers attach | **Post-hoc derived layer** (`prediction/derived.py`) computed from each ensemble member's trajectory after the existing solve. Odorants are **passive tracers**: they never feed back into growth, so they are integrated outside the ODE | New ODE states (only needed for feedback or observation; adds solve cost on 0.1 CPU); progress-indexed literature curves (blind to organism set and temperature beyond "progress", cannot extrapolate, digitising curves per type is most of the work) |
| Microbial drivers of aroma | A **diagnostic pass**: `engine.make_rhs` optionally reports per-organism growth (μⱼXⱼ) and substrate flux (vⱼ); `derived.py` re-evaluates the RHS once per output time on the raw states from `simulate(keep_states=True)`. The solve itself is unchanged | Reconstructing flux from pool differences (cannot attribute to organisms); new cumulative-flux ODE states (changes step selection, so existing outputs shift) |
| Aroma parameters | Own seeded N(0, I) columns drawn after inference (seed from the batch fingerprint): nothing observes them yet, so prior = posterior; these are the columns sub-project 6 will condition on tasting ratings | Threading them through AMIS now (no likelihood term would touch them) |
| Breadth vs honesty | ~12 **mechanism templates** with shared cited class parameters; a compound is mostly data. **Evidence tiers** per compound × ferment type: *calibrated* / *reported* / *plausible*. Non-negotiable for every compound: verified identity, cited threshold, cited mechanism | One kinetic model per compound (curation cost explodes); a hard "published time course or it doesn't ship" gate (owner wants breadth; tiers keep it honest) |
| Sweet/sour balance | **Sugar:acid ratio** (sucrose-equivalent sweetness : acid), the standard practical balance measure for juices and wines | A mixture-suppression formula (no specific cited model to stand behind) |
| Aroma readability | Compounds grouped into **aromatic series** with summed odour activity (the "aromatic series" approach of wine science, Peinado et al. 2004), headline by series, drill-down by compound; labelled an *index of odour potential* | One chart line per compound (30–40 per batch is unreadable) |
| Where in the UI | A **lens** inside the Forecast tab: *Process · Taste & aroma · Nutrition*, sharing the what-if temperature, window, status and crosshair | A 5th batch tab (`TabBar` uses `flex-1`; at 375 px five tabs overflow "Biochemistry"; the what-if state lives in `PredictionPanel` and would need lifting) |
| API | Same endpoint `GET /batches/{id}/prediction`, same cache entry; new series groups `nutrition`, `taste`, `aroma` and one optional `sensory` block | A separate endpoint (would re-derive the posterior, and what-ifs would diverge between tabs) |
| Versioning | `sensory.derived_version = "sensory-v1"` with its own `validated: false`, next to `model.version` (`kinetic-v1`) | One version for both (would conflate their validation status) |
| Data sourcing | Identity from KEGG, ChEBI, PubChem (open). Thresholds, descriptors and priors **hand-curated with citations** in `prediction/compounds.py` (as `organisms.py`). FooDB / FlavorDB used as research references, never redistributed in bulk (FooDB is CC BY-NC) | Bulk import of FooDB (licence blocks a paid tier; descriptors without thresholds do not support the method) |

## 1. Architecture and data flow

```
GET /batches/{id}/prediction            (same endpoint, cache entry, what-if, window)
  service._forecast()  or  bake.forecast()   ← unchanged up to the trajectory
    Trajectories (members × time: pools, biomass, pH, extra; raw states via keep_states)
    └─ derived.evaluate(segments, weights, recipe_composition, profile, seed)    ← NEW, pure numpy
         segments = [(Trajectories, EnsembleParams, phase info)]  (1 for a plain ferment,
                    one per phase for a sourdough plan: levain → bulk → proof)
         ├─ nutrition:  per-100 g series + label rows (start / now / end of window)
         ├─ taste:      activity series per dimension + taste-phase probabilities
         └─ aroma:      diagnostic pass → tracers per compound → series sums, P(noticeable)
    → series (groups nutrition / taste / aroma) through the existing quantile, relevance and
      milestone code; `sensory` block added to PredictionOut
```

**Files**

| File | Change |
|---|---|
| `prediction/derived.py` (new) | `evaluate(...)`: nutrition, taste, aroma; vectorised over members; no DB |
| `prediction/compounds.py` (new) | Curated data: compound records, mechanism-template class parameters, aromatic series, ingredient precursor map, sweetness factors, taste thresholds |
| `prediction/engine.py` | `make_rhs(p, max_evals, diagnostics=None)`: when a dict is passed, the RHS writes per-organism μⱼXⱼ and vⱼ into it. Default path unchanged |
| `prediction/profiles.py` | Per type: taste-phase vocabulary and boundary priors, precursor priors (milk citrate, cabbage glucosinolates and S-methylcysteine sulfoxide, fish TMAO), glutamate share of protein |
| `prediction/service.py`, `prediction/bake.py` | Call `evaluate` (≈ 20 lines each), merge series and the `sensory` block; `_group`/`LABELS` learn the new keys; `milestones[].lens` |
| `schemas.py` | `PredictionSeriesOut.group` gains `nutrition`, `taste`, `aroma`; `PredictionMilestoneOut.lens`; optional `PredictionOut.sensory` (§ 8) |
| `frontend/src/prediction/…` | Lens switch and summary card in `PredictionPanel.jsx`; new `TasteAroma.jsx`, `Nutrition.jsx`; small extensions to `ForecastChart.jsx`, `Milestones.jsx`, `prediction.css` (§ 6) |

No migration: the curated data lives in code, like the organism kinetics. The `compounds` DB table is only extended by the later explorer (sub-project 4).

**Inputs not yet threaded.** `_initial_state` turns the recipe into ODE pools only; fat, fibre, sodium and the non-fermentable carbohydrate come from `composition.py`'s per-nutrient totals (with `missing_from` and coverage), passed into `evaluate`. Ingredient names are passed for the aroma precursor map.

**Sourdough plans.** `bake.forecast` stitches per-phase trajectories, each phase with its own `EnsembleParams`. `evaluate` runs the diagnostic pass per phase segment and carries tracer concentrations across a boundary with the **same dilution** the bake module applies to the pools at mixing (levain share), adding the new flour's precursors. The existing TTA and FQ series are reused for sourdough taste (§ 3).

**Compute and payload.** Tracers are linear in their own concentration with known coefficients; exact per interval, milliseconds at 480 members. The diagnostic pass is one RHS evaluation per output time (≈ 161–200, versus 100–1500 in the solve). Target: the derived layer adds < 10 % to forecast time on a dev core. Compound-level series are sent on a 41-point grid, series sums and everything else on the full grid: about +150 KB per response, ~5 MB across the 32-entry output cache.

## 2. Nutrition

All values per 100 g of **what remains**: pools are per kg of starting batch, and the CO₂ that escapes is subtracted from the mass (all CO₂ assumed lost; ethanol evaporation ignored; both stated as assumptions). Layout follows the EU nutrition declaration (Reg. (EU) 1169/2011) plus rows that matter for ferments.

| Row | Computed from | Notes |
|---|---|---|
| Energy (kJ / kcal) | Annex XIV factors: carbohydrate 4 kcal (17 kJ)/g, protein 4 (17), fat 9 (37), alcohol 7 (29), organic acid 3 (13), fibre 2 (8) | Factors are conventions: no extra uncertainty, bands come from the ensemble |
| Fat | composition, carried through | Unknown → "—"; partial coverage → "≥" |
| Carbohydrate | starch + sucrose + hexoses + lactose + maltose + non-fermentable carbohydrate (constant) | |
| of which sugars | sucrose + hexoses + lactose + maltose | |
| of which lactose | lactose pool | Dairy only. No "lactose-free" reference: thresholds differ by country |
| Fibre | composition, carried through | |
| Protein | protein + peptides + free amino acids (total constant) | |
| of which free amino acids | amino-acid pool | Shows how far protein has been broken down |
| Salt | sodium × 2.5 (EU convention) | |
| Alcohol (% ABV) | ethanol g/kg ÷ 7.89 (density ~1 assumed) | Reference line at 0.5 % ABV: the US (TTB) level above which kombucha is regulated as an alcoholic beverage; limits vary by country and the label says so |
| Organic acids (% as lactic; as acetic for kombucha and vinegar) | Σ lactic, acetic, gluconic in molar equivalents | Labelled "acids made by the ferment": a titration kit also counts the matrix's own buffering. Sourdough plans show the engine's TTA instead |

Output: one series per row (groups `nutrition`, units `kcal/100 g`, `g/100 g`, `% ABV`), and `sensory.nutrition_label` rows at start / now / end of window, each with p05 / p50 / p95 and a `lower_bound` flag.

## 3. Taste

**Dimensions.** Each is a concentration divided by a detection threshold drawn from a log-normal prior (median from the curated source, ×/÷ ~3 for matrix effects), reported as a series (× threshold, log axis) and as P(above threshold) per time:

| Dimension | Quantity | Threshold source (curated) |
|---|---|---|
| Sweet | sucrose equivalents: sucrose 1, hexoses 0.8–1.3 (glucose/fructose mix: the model lumps them and yeasts consume glucose first, leaving fructose), lactose 0.2–0.4, maltose 0.3–0.5 | sucrose detection threshold |
| Sour | organic acids, per-acid thresholds (sourness follows total/protonated acid more than pH: Neta et al. 2007); sourdough plans use TTA | per-acid detection thresholds |
| Umami | free amino acids × glutamate share of the protein source (prior per type: soy, fish, milk, wheat) | MSG detection threshold |
| Alcohol | ethanol | ethanol perception threshold (wide prior) |
| Salty | constant | shown in the summary only, not as a curve |

**Taste phases.** Per type, an **ordered** vocabulary in `profiles.py` with boundary priors (nobody has measured "balanced" for this palate, so the boundaries are uncertain too). Each member is assigned a phase at every grid time; the output is P(phase | t) from the same weights.

| Type | Phases | Driven by |
|---|---|---|
| Kombucha | sweet → balanced → tart → vinegary | sugar:acid ratio; acetic acid noticeable |
| Vinegar | boozy → sharp → vinegar | ethanol vs acetic |
| Lacto-ferment | fresh → tangy → sour | acid activity |
| Kefir | milky → tangy → sour | acid activity, lactose left |
| Cheese (curd) | sweet milk → fresh tang | acid activity |
| Sourdough (plan) | mild → tangy → sharp | TTA, with FQ splitting creamy (lactic) from sharp (acetic) |
| Miso, garum (exploratory) | mild → savoury → deep savoury | umami activity, salt |
| Koji | none (no taste phases: a koji is an ingredient) | — |

**Loose milestones** reuse the existing kinds and gain `lens: "taste"` or `"nutrition"`: "Sweetness fading", "Vinegar note likely noticeable", "ABV over 0.5 %", "Lactose down by half". Displayed rounded to whole days past 48 h.

**Not modelled, and said so:** bitterness (tea polyphenols, hops), fizz (dissolved CO₂ in bottled ferments), umami synergy with nucleotides (IMP/GMP).

## 4. Aroma

### 4.1 Tracer kinetics

For compound *i*, per member:

```
dCᵢ/dt =  Σⱼ ( aᵢⱼ · μⱼXⱼ  +  bᵢⱼ · vⱼ )                 microbial: growth-linked + per g substrate fermented by j
        +  rᵢ(T) · Pᵢ                                     precursor chain (ingredient or amino-acid precursor Pᵢ)
        +  chemᵢ(T, pools)                                chemistry: esterification, Strecker / Maillard
        −  [ k⁰ᵢ · Q10ᵢ^((T−25)/10)  +  Σⱼ cᵢⱼ · Xⱼ ] · Cᵢ    loss: evaporation/chemical + microbial conversion
```

- Drivers μⱼXⱼ and vⱼ come from the diagnostic pass (§ 1); X, pools, pH and T from the trajectory.
- Precursors are linear first-order pools (`dPᵢ/dt = −rᵢ(T)·Pᵢ − microbial uptake`), initialised from `profiles.py` priors and the **ingredient precursor map** (cabbage → glucosinolates, S-methylcysteine sulfoxide; garlic → alliin; tea → glycosidically bound terpenes; milk → citrate, lactones; flour, soy, fish → lipids; rice → 2-acetyl-1-pyrroline; spices → their terpenes). Amino-acid precursors are shares (prior) of the engine's free-amino-acid pool.
- Esterification (ethanol + acetic acid ⇌ ethyl acetate + water; also ethyl lactate) uses forward and reverse first-order rates with a prior, linearised per interval on the known pools.
- **Integration**: on each interval the drivers are linear in time and the loss is a constant rate, so the solution is exact (exponential integrator), stable on coarse grids (a 3-year miso at ~1 point per week). If the step-halving test (§ 9) fails for a type, the diagnostic pass runs on a finer internal grid.
- Non-negativity is enforced at runtime; mass balance is a test invariant, never a runtime clamp.
- Organisms without curated aroma yields (including custom overrides) and ingredients without a precursor entry contribute nothing, and are listed in `sensory.not_modelled_aroma`.

**Output per compound:** concentration (mg/kg), odour activity value (OAV = C / threshold, threshold log-normal with a matrix factor), P(OAV > 1), tier, descriptor, provenance. Acetic acid and ethanol reuse the engine's pools.

### 4.2 Mechanism templates and candidate compounds

~85 candidates. Curation (§ 5) assigns tiers per ferment type and may drop any that fail the identity / threshold / mechanism requirement.

| Template | Compounds | Mainly in |
|---|---|---|
| Ehrlich pathway (yeast; amino acid → aldehyde → fusel alcohol or acid; Hazelwood et al. 2008) | 3-methylbutanal, 2-methylbutanal, 2-methylpropanal, phenylacetaldehyde, methional; 3-methylbutanol, 2-methylbutanol, 2-methylpropanol, 2-phenylethanol, methionol; 3-methylbutanoic, 2-methylbutanoic, 2-methylpropanoic acid | kombucha, sourdough, kefir, miso, vinegar |
| Yeast esters and medium-chain fatty acids (Saerens et al. 2010) | ethyl acetate, isoamyl acetate, 2-phenylethyl acetate, isobutyl acetate, ethyl butanoate, ethyl hexanoate, ethyl octanoate, ethyl decanoate, ethyl 2-methylbutanoate, ethyl 2-methylpropanoate; hexanoic, octanoic, decanoic acid | yeast-containing types |
| Pyruvate overflow (LAB citrate metabolism, Hugenholtz 1993; yeast; AAB) | acetaldehyde, diacetyl, 2,3-pentanedione, acetoin, 2,3-butanediol | all |
| Chemical esterification | ethyl acetate (chemical share), ethyl lactate | ethanol + acids |
| Lipid oxidation and lipoxygenase (ingredient lipids, mould) | hexanal, (Z)-3-hexenal, (Z)-3-hexenol, (E)-2-nonenal, nonanal, 2-pentylfuran, (Z)-4-heptenal; 1-octen-3-ol, 1-octen-3-one, 3-octanone, 3-octanol | flour, soy, fish, cabbage, koji |
| Brassica glucosinolates (myrosinase; isothiocyanate vs nitrile) | allyl isothiocyanate, allyl cyanide, 3-butenyl isothiocyanate, 4-methylthio-3-butenyl isothiocyanate | lacto-ferments with brassicas |
| Sulfur (S-methylcysteine sulfoxide, methionine, alliin) | methanethiol, dimethyl sulfide, dimethyl disulfide, dimethyl trisulfide, S-methyl thioacetate; diallyl disulfide, allyl methyl disulfide | lacto-ferments, garum, dairy |
| Terpenoids from tea, spices, herbs (some released by yeast β-glucosidase) | linalool, geraniol, citronellol, methyl salicylate, β-damascenone, β-ionone; geranial, neral, zingiberene; carvone, limonene | kombucha, spiced lacto-ferments |
| Phenolics (hydroxycinnamic acid decarboxylation / reduction) | 4-vinylguaiacol, 4-vinylphenol; 4-ethylguaiacol, 4-ethylphenol (inactive until a *Brettanomyces* or *Candida* organism exists) | sourdough, miso, kombucha |
| Slow Maillard / Strecker chemistry (months) | HEMF, furaneol, norfuraneol, maltol, sotolon, 2,5-dimethylpyrazine, 2,3,5-trimethylpyrazine | miso, garum |
| Milk-derived | δ-decalactone, δ-dodecalactone, butanoic acid, 2-heptanone, 2-nonanone | kefir, cheese |
| Fish- and rice-derived | trimethylamine; 2-acetyl-1-pyrroline | garum; rice koji and miso |
| Engine pools | acetic acid, ethanol | all |

### 4.3 Evidence tiers

| Tier | Evidence (for this compound in this ferment type) | Kinetics | Test | UI |
|---|---|---|---|---|
| Calibrated | a published time course | template, priors tuned to the curve | shape + magnitude: peak median within ×/÷ 3 of the published value, peak time in the published window, or the published direction of change | solid |
| Reported | reported present (key-odorant study, end-point concentration), no time course | template, magnitude anchored to the reported end point | end point within the reported range ×/÷ 3 at the typical time | solid, "reported" badge |
| Plausible | pathway or precursor present in this batch, not reported in this ferment | template, wide priors | non-negative, mass balance | dashed, collapsed by default, excluded from series sums, the summary card and milestones |

### 4.4 Aromatic series

Each compound belongs to one or two series: fruity, floral, green, buttery, malty, sulfurous, pungent, vinegary, cheesy, solvent, mushroom, caramel, roasty, fishy, phenolic, herbal. A series' value is the sum of its calibrated and reported compounds' OAVs, per member; the output is the series band and P(sum > 1). Perception is not additive (masking, synergy), so the UI calls this an **index of odour potential**.

## 5. Curation and verification (the largest task)

Three passes, written to `docs/superpowers/specs/<date>-aroma-curation.md` (every number cited, estimates marked "est."), then encoded in `compounds.py`:

1. **Identity, threshold, descriptor table** for all candidates: KEGG / ChEBI / PubChem IDs; orthonasal odour threshold in water with its range (candidate sources: Czerny et al. 2008, van Gemert 2011, primary papers); descriptor vocabulary (Czerny et al. 2008 aroma language; Flavornet). Taste thresholds and sweetness factors for § 3 in the same pass.
2. **Evidence matrix**: compound × ferment type → tier, with the key-odorant / time-course study behind each calibrated or reported cell; producers and mechanism per compound.
3. **Template calibration**: class parameters (yields per g substrate or per g growth, conversion rates, Q10, precursor priors) set so the prior median reproduces the calibrated-tier time courses; pinned tests per type.

Web literature searches (papers, PubChem, FooDB/FlavorDB as references) are needed; **the owner is asked before they run** (confidentiality rule: the repo lives on a Nestlé OneDrive, although this is a side project). An independent scientific review of the curation doc precedes encoding, as for the forecast (2026-09-24) and the enzymes (2026-09-25).

## 6. UI

**Placement.** A segmented pill control at the top of the Forecast tab content: **Process · Taste & aroma · Nutrition** (Process = today's view, unchanged). The what-if temperature, window, status line, disclaimer and warnings stay shared; milestones are filtered by `lens`; one time crosshair is shared by every chart in a lens. The batch tab bar (`BatchView.jsx`) is unchanged.

```
┌ In the jar ────────────────────────────────────────────────┐
│ Now · day 5    ■ Tart (likely)  fruity · vinegary · solvent  │
│                4.1 g sugar · 0.3 % ABV · 28 kcal /100 g      │
│ End · day 14   ■ Vinegary       vinegary · solvent           │
└──────────────────────────────────────────────────────────────┘
( Process | Taste & aroma | Nutrition )
milestones (this lens) · what-if °C · window
── Taste & aroma ──
Taste phase  [ sweet ░▒ balanced ▒▓ tart ▓█ vinegary ]  | now
Taste chart  sweet / sour / umami / alcohol × threshold (log), line at 1
Aroma strip  fruity   ▁▃▅▇▇▆▅▄▃      height = chance noticed
             buttery  ▃▇▅▂▁           shade  = × threshold
             vinegary    ▁▂▄▆▇██
  ▸ a row opens: compounds chart + compound cards
── Nutrition ──
Table per 100 g: Start | Now (d5) | End (d14); charts below
```

**Components**

- `PredictionPanel.jsx`: lens state; the **"In the jar" summary card** (now and end of window: most likely taste phase with its probability, the top three noticeable aroma series, sugar / ABV / kcal), shown in every lens; `Milestones` receives the lens-filtered list (the pH 4.6 milestone stays the Process hero). Without a `sensory` block (failure, older API), only the Process lens exists.
- `TasteAroma.jsx`:
  - **Taste phase band**: phases are ordinal, so a one-hue **ordinal ramp** (`--viz-ord-*`), never categorical. Where the most likely phase has P < 0.6, the transition is drawn as a blend of the two neighbouring ramp steps (imprecision shown without a new hue). Names inside segments when they fit, else in the tooltip ("day 6: balanced 55 %, tart 35 %, sweet 10 %").
  - **Taste chart**: existing `ForecastChart`, fixed slots 1–4 (sweet, sour, umami, alcohol) via `CANON.taste`, log scale, chart-wide reference line at 1 "detection threshold".
  - **Aroma strip**: heat strip, one row per series present (sorted by peak, labelled left), ~41 contiguous time columns, 2 px gaps between rows. **Bar height = P(noticeable)**, **shade = median × threshold** in 4 sequential bins (×1, ×10, ×100, ×1000+) of a second hue (`--viz-seq-*`), with a scale legend. No opacity-on-ramp, no texture.
  - **Drill-down**: a row opens a `ForecastChart` of its compounds (OAV, log, line at 1; at most 7 compounds plus a summed "others (n)"; plausible tier dashed with a legend entry, behind "Show plausible compounds (n)") and compound cards: name (PubChem link), descriptor, tier badge (outline, not status colours), made by / removed by, threshold, peak (median and range), sources.
  - A "Not modelled for aroma" note (organisms, ingredients, bitterness, fizz, spoilage).
- `Nutrition.jsx`: an HTML table (rows of § 2 × Start / Now / End of window); each cell the median with the 5–95 % range in muted text below it (stacked to fit 375 px), "≥" for lower bounds, a muted change vs start; then charts from the existing group:unit split (`groupCharts`): kcal/100 g, g/100 g, % ABV with the 0.5 % line where ethanol is relevant.
- `ForecastChart.jsx`: chart-wide reference lines (no series key) and dashed lines for `tier: "plausible"`.
- `prediction.css`: `--viz-ord-*` and `--viz-seq-*` tokens beside the existing ones (dark-only app, surface `#191612`).

**Accessibility and states:** every new chart has an aria summary and a "Show as table" twin (phase band and aroma strip especially); aroma rows are focusable, Enter opens the drill-down; identity never by colour alone; refetch holds the previous render at reduced opacity; text wears text tokens, never series colours.

## 7. Honesty and labelling

- `sensory.derived_version: "sensory-v1"`, `sensory.validated: false`, shown in the panel as the forecast does.
- Wording: "may be noticeable", "above detection threshold"; never "tastes like", "smells like", "becomes". Milestone example: "Vinegar note likely noticeable ~day 10 (7–14)".
- One new disclaimer line in the Taste & aroma lens: "Taste and aroma show which compounds may be above their detection threshold, not how it will taste to you. Spoilage off-odours are not modelled: trust your nose and your pH reading over this view."
- Nutrition: "Model estimate, not a lab analysis; not for labelling products for sale" (repeated next to the ABV line).
- Nothing here feeds the Safety Advisory; the words "safe" and "spoiled" never appear.
- Exploratory types keep their banner; their aroma compounds are mostly *reported* or *plausible*, and the lens says so.
- Scope stated in the lens: sourdough aroma is the dough before baking; cheese is the curd stage.
- Assumptions added to the existing list: CO₂ escapes, ethanol evaporation ignored, thresholds in water, perception not additive, glucose and fructose lumped.

## 8. API contract

`GET /batches/{id}/prediction` (unchanged query: `temperature_c`, `horizon_h`) → `PredictionOut` with:

- `series[]`: new `group` values `nutrition` (units `kcal/100 g`, `g/100 g`, `% ABV`), `taste` (unit `× threshold`), `aroma` (unit `× threshold`; keys `aroma:<series>` on the full grid, `odor:<compound>` on a 41-point grid), each series optionally with `tier`.
- `milestones[].lens`: `process` | `taste` | `nutrition` (existing milestones: `process`).
- `sensory` (optional; absent if the derived layer failed):
  - `derived_version`, `validated`, `disclaimer`
  - `taste_phases`: `{vocabulary: [..ordered], t_h: [...], prob: {phase: [...]}}` (named to avoid the sourdough `phases` field)
  - `nutrition_label`: `[{key, label, unit, start, now, end}]`, each value `{p05, p50, p95, lower_bound}` or `null` (unknown)
  - `aroma_series`: `[{key, label, compounds: [compound keys]}]`
  - `compounds`: `[{key, name, kegg, chebi, pubchem, descriptor, series: [..], tier, made_by: [{organism, how}], removed_by, threshold_mg_kg: {p50, range}, sources: [..]}]`
  - `noticeable`: `{now: {...}, end: {...}}` per series and taste dimension: P(above threshold), for the summary card
  - `not_modelled_aroma`: `{organisms: [..], ingredients: [..], notes: [..]}`

Errors unchanged (404, 422, 503). If `derived.evaluate` raises, the forecast is returned without `sensory`, with the warning "Taste & nutrition could not be computed for this batch", and the error is logged.

## 9. Testing and validation

| Level | Tests |
|---|---|
| Pure units | energy factors on known compositions; ABV; per-100 g with CO₂ mass loss; P(above threshold) against the analytic log-normal CDF; tracer integrator against the analytic solution (constant coefficients) and `solve_ivp` (time-varying); taste-phase probabilities sum to 1; step-halving changes outputs < 10 % |
| Invariants (prior draws, every type) | non-negative; molar mass balance per precursor (products ≤ precursor consumed); batch **absolute** energy never increases (per 100 g may rise as CO₂ leaves); the diagnostic pass's ∫Σvⱼ dt matches the substrate the pools lost within 5 % |
| No regression | kinetic series identical with and without the derived layer; the existing suite passes untouched |
| Data lint | every compound has identity IDs, a cited threshold, a mechanism, sources; a calibrated/reported tier needs a source tagged with that type; every number cited or "est." |
| Calibration (pinned, like `test_sauerkraut`) | nutrition and taste against the forecast's trajectory sources and curation sources; aroma per tier (§ 4.3) |
| API | schema includes the new fields; `sensory` absent when `evaluate` raises; derived-layer time < 10 % of the forecast on a dev core |
| Frontend | `validate_palette.js --ordinal --mode dark --surface #191612` (phase ramp) and the sequential check (aroma ramp) pass; Playwright (or the CDP harness) screenshots of each lens at 375 / 500 / 1100 px, looked at for collisions and overflow; `npx vite build`; keyboard pass (lens switch, aroma rows, table toggles) |
| Review gates | independent review of `derived.py` (ds-reviewer) and of the curation (scientific check) before merge |

**Validation trigger.** Nutrition can be validated against measured sugar, ABV and acidity from real batches (`scripts/validate_forecasts.py` style, leave-future-out). Taste and aroma cannot be validated without sensory data: they stay `validated: false` until sub-project 6 collects tasting ratings, then a leave-future-out check on those ratings decides.

## 10. Build order and later sub-projects

**Increment A** (no new data): engine diagnostics hook → `derived.py` nutrition and taste → `compounds.py` taste data (thresholds, sweetness factors) → service/bake/schema wiring → `Nutrition.jsx`, taste parts of `TasteAroma.jsx`, lens and summary card → tests, palette validation, screenshots, review.

**Increment B** (aroma): curation passes 1–2 (web search after owner OK) → review → templates and tracers → curation pass 3 calibration → aroma strip and drill-down → tests, review.

**Later sub-projects** (each its own spec): 4 compound explorer ("understand my ferment": microbe → pathway → compound → descriptor, extending the KEGG `compounds` table); 5 micronutrients and bioactives (a new FDC snapshot with vitamins and minerals, phytate → mineral availability, folate, vitamin C, GABA, biogenic amines); 6 calibration from the user (TTA kits for every type, 1–5 tasting ratings with an ordinal likelihood on the aroma/taste z-columns, then population learning); also a taste line on Today cards and taste in Compare.

## References (methods; each verified during curation before it is cited in code)

Regulation (EU) No 1169/2011, Annex XIV (energy conversion factors) · US TTB guidance on kombucha (0.5 % ABV) · Luedeking & Piret 1959 · Grosch 2001 Chem Senses 26:533 (key odorants, odour activity values) · Czerny et al. 2008 Eur Food Res Technol 228:265 (odour thresholds in water, aroma language) · van Gemert 2011, *Odour thresholds* (compilation) · Peinado et al. 2004 Food Chem 84:585 (aromatic series) · Neta, Johanningsmeier & McFeeters 2007 J Food Sci 72:R33 (sour taste) · Hazelwood et al. 2008 Appl Environ Microbiol 74:2259 (Ehrlich pathway) · Saerens et al. 2010 Microb Biotechnol 3:165 (yeast esters) · Hugenholtz 1993 FEMS Microbiol Rev 12:165 (citrate metabolism in LAB) · Minervini et al. 2014 (sourdough FQ; as cited in the sourdough spec). Compound-specific sources: the curation doc (§ 5).
