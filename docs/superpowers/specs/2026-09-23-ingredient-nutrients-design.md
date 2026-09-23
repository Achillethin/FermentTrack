# Ingredient Nutrient Database & Fermentation Transformation Model — Design

**Date:** 2026-09-23
**Status:** Draft, awaiting Achille's review
**Builds on:** `2026-09-18-experiment-logging-design.md` (Ingredient / BatchIngredient tables), `docs/DEPENDENCIES.md` (vendoring rules, "don't overclaim" gate)

## Problem

A recipe today is a list of `(ingredient, quantity, free-text unit)` rows. It records *what* went in, but not *what's in it*. You can't ask "how much fermentable sugar did this kombucha start with?", "what's the brine salt %?", or the real goal of `fermentation` / `fermentgraph`: **"what does this recipe's nutrient profile turn into after fermentation?"**

To answer that, you need three layers, and they depend on each other in this order:

1. **Reference composition.** Nutrients per 100 g for each ingredient, taken from a public food-composition table.
2. **Batch composition (t = 0).** Recipe quantities in grams × layer 1 gives the initial nutrient vector `n₀`.
3. **Transformation model.** `n(t) = n₀ + A·ξ(t)`: scheme-specific stoichiometry `A` times the extents of reaction `ξ(t)`, where `ξ` comes from the vendored Monod twin and/or the batch's own measurements. Output comes with intervals.

Layers 1–2 are **Increment 1**, and its plan is written: `docs/superpowers/plans/2026-09-23-ingredient-nutrients-increment-1.md`. Layer 3 is **Increment 2**. This doc designs it, and it gets its own plan once Increment 1 has landed and the data layout is fixed.

---

## 1. Database discovery — which source

Licence and scope notes come from prior knowledge. **They were not re-verified online this session**, because the confidentiality rule means asking before any external call. Task 2 of the plan re-checks the chosen source's licence before any data is committed.

| Source | Coverage | Fermentation-relevant fields | Licence | Access | Verdict |
|---|---|---|---|---|---|
| **USDA FoodData Central: Foundation Foods + SR Legacy** | ~8k generic foods, analytically measured | Individual sugars (sucrose, glucose, fructose, lactose, maltose, galactose), starch, alcohol, protein, fat, fibre, sodium, water. It also contains **fermented endpoints** (sauerkraut, miso, kefir, yogurt, cheeses, soy sauce, fish sauce) | CC0 / US public domain | REST API (free key; `DEMO_KEY` for low volume) + bulk CSV | **Primary.** |
| **CIQUAL (ANSES, France)** | ~3.2k foods, 60+ components | Individual sugars, organic acids (total), salt; **French names** | Licence Ouverte / Etalab 2.0 (commercial OK with attribution) | XLSX/XML download, no API | **Secondary.** Add when French names or EU-specific foods are needed. The safety layer already ships `_fr` strings. |
| Open Food Facts | 3M+ branded products | Label-level only: total sugars, salt. No sugar breakdown | ODbL (share-alike on the database) | API + dump | Later, and only for branded ingredients. Share-alike needs a legal read first. |
| FooDB (already ingested in `fermentation/ingest/foodb_content.py`) | ~70k compounds | Secondary metabolites, flavour compounds | **CC BY-NC 4.0**: non-commercial, which conflicts with the Pro tier in `STRATEGY.md` | CSV dump | **No.** It is also compound-level data, gated by the fermentgraph trigger in `DEPENDENCIES.md`. |
| Phenol-Explorer | Polyphenols | Tea polyphenols, relevant to kombucha | Needs a check | CSV | Later, for a kombucha-polyphenol extension. |
| EuroFIR / paid national tables | Broad | Broad | Paid / restricted | — | No. |

**Why FDC wins:**
- Its licence is the least restrictive.
- It is the only free source with an API and a per-sugar breakdown. Kombucha depends on sucrose, dairy on lactose, and koji and sourdough on starch and maltose. Totals alone can't separate these substrates.
- It holds paired raw→fermented foods (cabbage→sauerkraut, milk→kefir, soybean→miso). That gives a free, if coarse, **endpoint validation set** for Increment 2.

**Sibling reuse:** `fermentation/ingest/usda_fdc.py` already calls FDC. It is **not reusable as-is**:
- It only queries SR Legacy, in 4 food groups. That leaves out dairy, fish, sugars and beverages.
- Its nutrient set has no individual sugars, starch or alcohol.
- It pulls `httpx` and that repo's heavy dependency tree, which `DEPENDENCIES.md` already avoids by vendoring.

Increment 1 keeps the **same FDC nutrient IDs** (1003 protein, 1004 fat, 1051 water, …) so the two repos' data joins cleanly. It also fixes one naming error: that module's comment calls them "NDB numbers", but they are FDC nutrient IDs.

## 2. Data model (Increment 1)

```
ingredients                (existing, unchanged)
ingredient_nutrients       (new)
  id               UUID PK
  ingredient_id    FK → ingredients.id
  nutrient         Text     -- closed set, see NUTRIENTS in fermenttrack/nutrients.py
  amount_per_100g  Float    -- always grams per 100 g edible portion
  source           Text     -- "usda_fdc"
  source_food_id   Text     -- FDC fdcId, as provenance
  source_version   Text     -- snapshot file name, e.g. "fdc_nutrients_v1"
  UNIQUE (ingredient_id, nutrient, source)
```

Decisions:

- **Missing ≠ zero.** A row exists only when FDC *reported* the value. SR Legacy often omits individual sugars, so a food with no `lactose` row has *unknown* lactose, not zero. Composition keeps these separate (`missing_from`). Modelling downstream must treat them as missing data, never as 0.
- **Every stored nutrient is in grams per 100 g.** mg and µg are converted when the snapshot is taken. Energy (kcal) is left out: it isn't conserved mass, and Increment 2 can recompute it from macros with Atwater factors.
- **The snapshot is committed, not fetched at runtime.** `scripts/fetch_fdc_snapshot.py` writes `src/fermenttrack/fdc_nutrients_v1.csv` (co-located, like `safety/risk_rules.yaml`). Migration 0006 seeds from it (0005 is the ingredient split). That means no API key at runtime, reproducible builds, and a reviewable diff. **The file is frozen once migrated.** A new snapshot is `_v2` plus a new migration, following the existing `INGREDIENT_SEED_DATA_V2` convention.
- **`canonical_id` stays reserved** for the fermentgraph export (experiment-logging spec, "Deferred"). FDC provenance lives on the nutrient rows, not in `canonical_id`.
- **Vague ingredients get split (decided by Achille, 2026-09-23).** Each generic seed row is retired (`is_active = False`, never deleted, so historical `BatchIngredient` rows keep their FK) and replaced by specific ingredients:

  | Retired | Replaced by |
  |---|---|
  | Rice/grain/soybean | White rice, Pearl barley, Soybeans |
  | Flour | White wheat flour, Whole wheat flour, Rye flour |
  | Fruit | Lemon, Strawberries, Raspberries, Apple |
  | Herbs | Mint, Basil |
  | Spices | Cinnamon, Turmeric, Cardamom |
  | Wine/cider/base alcohol | Red wine, White wine, Hard cider |
  | Black/green tea | Black tea leaves, Green tea leaves |
  | Fish | Anchovies, Mackerel |

  `Water` also gains `lacto_ferment`, because brine ferments (chilies in brine) need it. There is no "Other fruit" catch-all, because that would bring the vagueness back. A missing ingredient is added through a new seed migration. The API rejects logging a retired ingredient.
- **Some ingredients are still unmapped, and that's honest:** starters and cultures (negligible mass), tea leaves (FDC has brewed tea, not dry leaves), calcium chloride, and anything with no exact FDC SR Legacy match. Composition reports them as `unmapped`, which pulls `coverage` below 1.
- **Units become a closed set: `g, kg, mg, ml, L`.** The frontend's free-text unit field becomes a `<select>`. ml and L assume a density of 1.0. That is right for water, about 3% off for milk, and 40% off for honey. It's marked with a `ponytail:` comment, and per-ingredient density gets added when a recipe needs it. Any other unit already stored is reported as `unquantified` and never guessed.
- **The unique key `(ingredient_id, nutrient, source)` excludes `source_version`**, so a v2 snapshot migration must replace or UPDATE v1 rows rather than insert alongside them. A second source (e.g. CIQUAL) needs a precedence rule before the composition endpoint merges sources.

## 3. Batch composition (Increment 1)

This is a pure function, `compose(items) -> Composition`, in `fermenttrack/composition.py`. It is exposed as `GET /batches/{id}/composition`. It is **not** folded into `/preview`, because the experiment-logging spec keeps that endpoint to one page's needs.

Output per batch:
- `total_mass_g`: the sum of every convertible quantity.
- `mapped_mass_g`: the part of that mass whose ingredients have nutrient data.
- `coverage` = mapped / total.
- Per nutrient: `grams`, `per_100g`, and `missing_from`, the list of mapped ingredients that have no value for it.
- `salt_pct`: logged **added salt** (Salt rows) / total mass. This is the recipe's **brine salinity estimate**, the input the Monod twin's `salt_factor` needs. It is `null` when no Salt row is logged (unknown), and exactly 0 for a logged 0 g, and `null` whenever any recipe row has no usable quantity/unit (the denominator would be incomplete). The food's own sodium stays in `nutrients.sodium` and is deliberately left out: otherwise unsalted cabbage would read as about 0.05 % "salt".
- `unmapped` and `unquantified` ingredient names.

When `coverage < 1` or `missing_from` isn't empty, the figures are **lower bounds**. The API says so in the field docs and the UI says so in the card.

### 3.1 Salt pre-fill for salt-requiring ferments (decided by Achille, 2026-09-23)

When a batch's ferment type needs salt and no salt is logged yet, the composition response carries a `salt_suggestion`. The recipe form then **pre-fills** that amount when the user picks Salt. The user can edit it, or log `0 g` to record an unsalted batch on purpose.

| Ferment type | Default | Basis (logged `base`-role mass) | Why |
|---|---|---|---|
| lacto_ferment | **3 %** | vegetables + brine water | Inside the 2–5 % range `SALT-001` recommends. Note that it is below `BOT-001`'s 3.5 % threshold, so safety still depends on the pH dropping below 4.6 |
| miso | 21 % | **dry** soybeans + rice/barley | That works out to ~10–13 % of the finished miso, once the cooked soy has absorbed water. Salt is the main safeguard over months at room temperature |
| garum | 20 % | fish | Modern garum practice; high salt is the main pathogen barrier here |
| sourdough | 2 % | flour only (not water) | Baker's percentage |
| cheese, koji, kombucha, kefir, vinegar | none | — | Kombucha, kefir and vinegar use no salt, and koji-making adds none. Cheese is salted per curd mass, which the recipe doesn't know |

Rules:
- **A pre-fill, never an auto-inserted row.** Recipe rows must record what the user actually did. When the batch is created there is no base mass yet, so 3 % of it would be meaningless.
- **An explicit `0 g` is a known zero** (`salt_pct = 0`). "Salt not logged" stays unknown (`salt_pct = null`). This is the same missing ≠ zero rule as above.
- A suggestion exists only once some base mass has been logged, and disappears once any Salt row exists.

**Deliberately not done in Increment 1:** feeding `salt_pct` into the safety rule engine. It would be a better default than `TwinState`'s neutral fallback when no `salt_pct` measurement exists, but it changes hard-stop verdicts on a safety path. That's Achille's call, as a separate change with its own tests.

## 4. Transformation model (Increment 2, designed here, planned later)

### 4.1 Formulation

State: the nutrient mass vector `n ∈ ℝ^k` for the whole batch, in grams. It's extended with model-only species that FDC doesn't carry at t = 0: `lactic_acid`, `acetic_acid`, `gluconic_acid`, `co2_lost`, `free_amino_acids`.

```
n(t) = n₀ + A · ξ(t),    ξ(t) ≥ 0,   n(t) ≥ 0
```

Here `A` (k × r) holds mass-based stoichiometric coefficients, one column per reaction. They come straight from molar masses, with nothing fitted:

| Reaction | Per 1 g substrate | Schemes |
|---|---|---|
| Sucrose inversion (invertase) | −1 sucrose, −0.053 water, +0.526 glucose, +0.526 fructose | kombucha, kefir (water) |
| Lactose hydrolysis | −1 lactose, −0.053 water, +0.526 glucose, +0.526 galactose | cheese, kefir (milk) |
| Amylolysis | −1 starch, −0.111 water, +1.111 glucose | koji, miso, sourdough |
| Homolactic | −1 hexose, +1.000 lactic acid | lacto_ferment, cheese, sourdough |
| Heterolactic | −1 hexose, +0.500 lactic, +0.256 ethanol, +0.244 CO₂ | sourdough, kefir, lacto_ferment (early) |
| Alcoholic (yeast) | −1 hexose, +0.511 ethanol, +0.489 CO₂ | kombucha, kefir, sourdough |
| Acetic (Acetobacter) | −1 ethanol, −0.695 O₂, +1.304 acetic acid, +0.391 water | kombucha, vinegar |
| Gluconic (Komagataeibacter) | −1 glucose, −0.089 O₂, +1.089 gluconic acid | kombucha |
| Proteolysis | −1 protein, −~0.15 water, +~1.15 free amino acids (hydrolysis takes up water) | koji, miso, cheese (ripening), garum |

Each scheme is a sparse selection of columns. Mass leaves the system through CO₂. **Physical separation** is a different mechanism and is the dominant driver of change for some ferments: whey drainage for cheese, pressing, evaporation in long aging. It is modelled as a per-stage partition step, and it only runs when the batch logs a `mass_g` measurement at that stage. It is never assumed.

### 4.2 Where ξ(t) comes from, in order of trust

1. **Measurements.** Brix, gravity or refractometer drops give Δ(total sugars) directly. A refractometer Brix drop is only a clean Δsugars when there's no ethanol; alcoholic and acetic schemes need the gravity + refractometer correction. The SG → ethanol correlation is standard. pH gives acid production only weakly, because the buffer capacity is unknown, so it is a likelihood term, not an inversion.
2. **The vendored Monod twin** (`safety/baseline_model.py`). For `lactic`, `S(t)` and `P(t)` map to ξ_homolactic. `S₀` comes from the composition's fermentable sugars and `salt_pct` from the composition. This is the first real consumer of Increment 1.
3. **Literature priors** on rates or extents, per scheme. These are used for schemes the twin doesn't cover yet (kombucha's two-organism yeast→AAB cascade, koji, cheese ripening).

### 4.3 Uncertainty

- **v1 is forward Monte Carlo** with scipy only, which is already a dependency. Sample `n₀` from FDC's reported SE/n where present, else ±CV by nutrient class. Sample kinetic parameters from prior ranges. Push them through `A` and the twin, and report the 5/50/95% bands per nutrient per time point.
- **v2 is conditioning on measurements.** Bring in the posterior `p(ξ, θ | brix, pH, gravity)` for the batch itself. Batches nest inside cultures, so partial pooling of `μ_max`, yields and lag across batches of one culture is the natural hierarchical model. That's where the logged data starts paying off. This needs a new dependency (NumPyro or PyMC), so it's decided at v2 time, not now.
- **Calibration check before any UI claim.** Use PIT/coverage of the 90% bands against (a) FDC raw→fermented endpoint pairs and (b) the user's own logged brix and gravity trajectories.

### 4.4 Product gate (consistent with `DEPENDENCIES.md` / `STRATEGY.md`)

- **Input composition (Increment 1) is measured reference data, not a prediction.** It can ship to the UI right away, with its coverage label.
- **Transformed nutrients are model output.** The API ships them with intervals and a `status: "heuristic" | "endpoint_validated"` per scheme. The UI shows a scheme only once it is `endpoint_validated`, meaning its 90% band covers the FDC fermented endpoint for the paired foods. This is **not** gated on the fermentgraph ranker trigger, because textbook stoichiometry and cited kinetics are a different kind of evidence from a learned ranker. It keeps the same "don't show unvalidated output" discipline, though.
- **Out of scope** until there is evidence: vitamin synthesis (B12, K2, folate), bioactive peptides, antinutrient degradation (phytate), and compound/flavour profiles (fermentgraph territory). None of these has a reliable stoichiometry. Showing them would be the overclaiming `DEPENDENCIES.md` already caught once.

### 4.5 Backend layout for Increment 2 (sketch, not binding)

```
src/fermenttrack/transform/
  stoichiometry.py   # SPECIES, REACTIONS, A matrix per scheme — pure, tested by mass balance
  extents.py         # ξ(t) from twin trajectory and/or measurements
  predict.py         # Monte Carlo → bands; returns TransformationOut
GET /batches/{id}/nutrients/trajectory?hours=…   → bands per nutrient
```

The check that anchors `stoichiometry.py` is elemental balance: every column conserves C, H and O mass within 1% once water, CO₂ and O₂ are included, except proteolysis, which is excluded from the C/H/O assert — its coefficients depend on the average residue mass, and N isn't tracked. Every other column must balance within 1 %. That one assert catches every typo in a yield coefficient.

## 5. Open decisions for Achille

1. **Salt estimate into safety:** should recipe-derived `salt_pct` stand in when no measured `salt_pct` exists? Not in Increment 1 by default.
2. ~~Split the generic seed ingredients?~~ **Decided: yes**, see §2.
3. ~~Default salt?~~ **Decided: pre-fill per ferment type**, see §3.1.
4. **Hierarchical fitting dependency** (NumPyro vs PyMC) is decided at Increment 2 v2, not now.
