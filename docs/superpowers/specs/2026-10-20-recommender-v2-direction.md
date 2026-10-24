# Recommender v2 — Direction

**Date:** 2026-10-20
**Status:** DRAFT for owner confirmation. The decisions (V1–V19) come from a grilling session with the owner on 2026-10-20.
**Builds on:**
- `2026-10-07-fermentation-recommender-design.md` (the v1 recommender on `feat/recommender-spec`; its § 17 holds the build notes);
- `2026-09-24-fermentation-prediction-design.md`, `2026-09-28-sourdough-engine-design.md` (the engine and its learning hierarchy);
- `2026-10-05-aroma-curation.md` (the 85-compound catalogue).

## 1. Why v1 feels weak (measured 2026-10-20 on the committed grid)

| # | Cause | Evidence |
|---|---|---|
| 1 | **The score saturates.** Cards rank by P(OAV > 1) read at its own argmax over time. | At the documented median duration, 149 of 294 recipe × series cells (51 %) have E > 0.9. At the peak almost every card has E ≈ 1.00, so cards differ by ~10⁻³, the float16 step near 1: the order is rounding noise. "fruity" returns three sourdough starters; miso is noticeable on 11 of 16 series. |
| 2 | **Almost no variants.** | `ingredient_use_levels_v1.csv` has 16 rows and one flavouring (fresh ginger, lacto). The grid's 71 single operators are 1 add, 42 swaps, 28 temperature moves. |
| 3 | **A tiny library and no notion of what goes together.** | 13 non-sourdough recipes over 8 types. Carrot + garlic returns kombucha + 5 % carrot + 5 % garlic, because "fewest to buy" rewards the smallest edit. The carrot-sticks recipe is still a draft. |
| 4 | **Nothing learns from users yet.** | The calibration gate needs ≥ 30 tasted linked batches; at n = 30 over 3 types even a perfect model passes 17 % of the time (§ 17.11). The owner expects < 20 active users in the next 3 months. |
| 5 | **Forecast errors show up as recommender bugs.** | Only 1–11 % of kimchi members reach pH 4.6 by 72 h, so kimchi windows collapse (both offline-evaluation misses). The levain peak median is 1.5–2× slower than bakers' rules (strict xfail). |

## 2. Decisions

| # | Topic | Decision |
|---|---|---|
| V1 | Audiences, in order | **Pantry-first lacto fermenters**, then **bakers' timing**, then **aroma tinkerers / experimenters** ("sorcerer's apprentices"), all three in scope |
| V2 | Meaning of an aroma target | **Characteristic**: a large share of the batch's perceived aroma (§ 3.1). Experimental cards also say "more than the parent". P(noticeable) is only a floor |
| V3 | v1 branch | Merge all of `feat/recommender-spec` |
| V4 | Growth of ingredients and recipes | **Curation** (research agents + owner review), not community: < 20 users won't fill it |
| V5 | Expected users | < 20 active in 3 months: the per-user loop goes ahead of any cross-user calibration |
| V6 | First push | Merge **and** the score fix together (§ 4, release 1), not v1 as-is |
| V7 | Pantry input | The list is **what I have**; the user stars 1–2 **must-use** items (hard filter); rank by pantry coverage, then least to buy |
| V8 | Lacto recipes | A **lacto composer** (§ 3.3), lacto only; other types keep library + operators |
| V9 | "Adjust next time" | The tasting asks **sourness vs what you wanted**; the loop moves **stop time and temperature only** (not salt, not aromatics). Each taster has a sour-tolerance offset, pooled across tasters |
| V10 | Bakers' "ready by" | Input: when the levain must be ready to mix. Levers: feed ratio × levain temperature. Oven-time planning later, through the existing planner |
| V11 | Release 1 scope | Merge, character score, golden query set, pantry ranking, ingredient → tagged-type ranking. The composer is release 2 |
| V12 | Experimental ranking | **Upside** (P90 of the character score), with a **"this experiment would teach us"** badge for high expected information gain (§ 3.4) |
| V13 | Side-by-side jars | A built-in flow: split one base into 2–3 jars, one change each, paired "which is more X?" tastings, reusing the compare view |
| V14 | Experimenter extras | Friendly aroma words ("funky"), "avoid" targets, amounts up to 2× the sourced maximum (labelled "beyond documented amounts"), **and** mixed ferment types |
| V15 | (merged into V14) | — |
| V16 | Mixed-type mechanisms | **Both**: sequential (a finished ferment as ingredient or starter) and concurrent (two types' cultures in one jar) |
| V17 | Safety of mixes | Every stage passes **its own type's gate**; the jar carries the lines of **every barrier it relies on**; salt never below the stricter type. One-jar mixes pass every involved type's gate and keep "measure pH by 48 h" (film yeasts can raise pH) |
| V18 | Release order | § 4; side-by-side jars and "restart from last batch's brine" move into release 3 |
| V19 | First mixed recipes | **Koji lacto ferment** (koji hot sauce; koji kraut or kimchi) and **another type's culture in a jar** (e.g. wine yeast in a hot sauce) |

## 3. Design

### 3.1 Character score (V2)

Per member *n*, series *s*, time *t*, the engine already gives Lₙ,ₛ(t) = log₁₀ of the series' summed odour activity (`derived._aroma_block`).

- **Perceived intensity** above threshold, Fechner-style: Iₙ,ₛ = max(0, Lₙ,ₛ).
- **Character share:** cₙ,ₛ = Iₙ,ₛ / Σₛ′ Iₙ,ₛ′ (0 when nothing is above threshold).
- **Target score:** Cₙ = Σ_{s∈A} cₙ,ₛ, the share of the batch's perceived aroma that the targets carry.
- **Floor:** a target whose P(noticeable) < 0.5 at the read time scores 0 and the card says "unlikely noticeable".
- **Tastes** don't share with aroma: a taste target scores σ((L − L_clear)/τ), where L_clear is the profile ladder's "clearly X" boundary (e.g. the acid ladder's `sour` step on `acidity_pct`), not the detection threshold.
- **Proven** ranks by E[C]; **Experimental** by the weighted P90 of C (V12) and shows the difference from the parent ("more fruity than the parent").
- **Read time:** the window's peak is the argmax of E[C] inside [taste from, stop by]. It no longer pushes every score to 1.

ponytail: the Fechner share is a modelling choice; Stevens' law (I ∝ OAV^0.5) is the alternative if the golden set or tastings disagree. One grid rebuild adds per-series quantiles of c and I (`build_recommender_grid.py`, ~8.5 min on 4 workers).

**As built (release 1, 2026-10-20 → 24).** Two numbers per target, because one can't do both jobs:
- **E = P(characteristic)**, member by member: an aroma series is noticeable *and* among the member's 3 strongest (`score.character_margins`); a taste is past 10× its threshold (`score.clear_taste`). It drives the shown Low / Med / High ("likely to stand out"). Cells with E > 0.9 at d_med fell from 149 to 21 of 294.
- **C = the expected share** Σₙ wₙ cₙ,ₛ above (grid schema 4, `score.character_share`; a taste's C is its E). It ranks Proven, Community and breaks Experimental ties, and places the window's peak. E alone still saturated among the recipes that have a note at all: kimchi, kraut, two misos and the fish sauce all had E 0.76–0.92 for "sulfurous", while their sulfur shares are 0.24, 0.21, 0.17, 0.16, 0.14. Ranking by C puts kimchi and kraut first, the textbook answer.
- **Floors:** a target scores C = 0 when P(noticeable) < 0.5 at the read time ("unlikely noticeable") or its share is below 0.05 (a trace: miso's 2 % "mushroom"); with targets, a card scoring 0 is **not served** (no kombucha for "fishy"). Lead notes carry 0.15–0.35 on this grid.
- **On the card:** the share as words, from a band in the API (dominant ≥ 0.30, large ≥ 0.15, smaller ≥ 0.05, trace), never a number before the calibration gate.

### 3.2 Pantry and ingredient-type ranking (V7, V11)

- Starred items are must-include (the v1 filter). The rest of the list is what the user has.
- **Type compatibility first:** candidates of a type the listed ingredients are tagged for (`Ingredient.fermentation_systems`, e.g. Carrot and Garlic → `lacto_ferment`) rank above candidates that need operator (v) to bring the ingredient into a type it isn't tagged for.
- Then pantry coverage (share of the recipe's non-staple mass the pantry covers), then fewest to buy, then the v1 keys.

### 3.3 Lacto composer (V8, release 2)

A lacto recipe is assembled from parts, each a rule or a curated number:
- one or more base vegetables (tagged `lacto_ferment`);
- the **method by vegetable**: dry-salting for vegetables that release enough water (cabbage, napa), brine otherwise (carrot, cucumber, pepper, bean), with brine water added to the mass;
- **salt** from the gate's 2–5 % rule (default 2.5 % brine / 2 % dry, per the curation);
- **aromatics** at sourced use levels (T3 rows from the lacto research round);
- **temperature and window** from the model.

Composed recipes are Experimental-provenance with a "composed from sourced rules" label; the gate runs on every one.

### 3.4 Expected information gain badge (V12)

With the ordinal tasting model of v1 § 15.1, P(rating ≥ k | n) = σ((Lₙ,ₛ − θ_k)/τ_obs), the gain of one tasting of series *s* at time *t* is EIG = H[Σₙ wₙ p(r | n)] − Σₙ wₙ H[p(r | n)]. It is computed per entry and series at grid build and stored. The badge shows on variants in the top quartile of EIG among served cards.

### 3.5 Personal loop (V9, release 3)

- Tasting form: one extra question, "sourness compared with what you wanted": too mild / just right / too sour.
- Sour ratings become ordinal observations of acidity in the AMIS likelihood, with a per-taster threshold offset (a baker-level effect in the crossed hierarchy), so a batch calibrates without a pH meter.
- "Adjust next time": solve, on the batch's own posterior, for the stop time (then temperature) that moves the predicted acidity at stop to the taster's "just right" level. Shown on Repeat.
- Side-by-side jars (V13) and "restart from last batch's brine" (inoculum from the previous batch) land here.

### 3.6 Mixed types (V16, V19, release 6)

- **Koji lacto ferment (sequential):** a lacto profile with a koji enzyme dose (`koji_enzyme0`, already on miso and garum) from the koji's share of the mash, and `KOJI_CARRY` aroma carry-over extended to `lacto_ferment`. Koji amylase frees sugars from the rice; the lactic flora ferments them. Recipes: koji hot sauce (chili, garlic, koji, salt), koji kraut or kimchi. General sequential chaining reuses the bake.py phase runner (a finished state diluted into the next batch's y0).
- **Another type's culture in a jar (concurrent):** attaching an organism from another type (e.g. *S. cerevisiae* wine yeast in a hot sauce) through the existing batch-organism attachment, up to `MAX_MODELLED_ORGANISMS`.
- Cards carry "mixed ferment: model extrapolation" on top of "model estimate, not validated". Safety per V17.

## 4. Releases and exit criteria

| Release | Scope | Done when |
|---|---|---|
| 1 | Merge v1; character score (§ 3.1) and grid rebuild; pantry and type ranking (§ 3.2); golden set of ~15 queries with expected answers (drafted by Claude, reviewed by the owner) | Golden set passes; score IQR > 0.2 over every gated candidate of the golden target queries, and served cards separated by a median C gap > 0.01 (revised 2026-10-24, see below); v1 E1–E5 still pass; full suite green; local app run. **The owner pushes** (2026-10-24: the owner delegated the push for this release). |
| 2 | Lacto forecast checked against published sauerkraut and kimchi pH(t) curves (kimchi rate fixed here); lacto composer (§ 3.3); aromatic T3 rows from the lacto research round | 90 % band covers 85–95 % of the literature points; carrot + garlic returns brined carrots with garlic |
| 3 | Personal loop (§ 3.5), side-by-side jars, restart from last batch's brine | "Adjust next time" on a repeated batch; held-out tastings beat a per-type baseline (Brier) |
| 4 | Bakers' "ready by" (V10), after recalibrating the levain peak (the strict xfail passes) | Recommended ratio × temperature has a calibrated P(ready in the window) on published rise curves |
| 5 | Experimenters: upside ranking + EIG badge, friendly words, "avoid", beyond-documented amounts | Golden set extended to experimenter queries passes; every card passes the gate (E4) |
| 6 | Mixed types (§ 3.6) | Koji hot sauce and koji kraut served with the V17 lines; E4 over mixed cards: 0 violations |

**Release 1 criterion, revised 2026-10-24.** "Served-card score IQR > 0.2" measured the wrong thing: the served cards are each query's best three, so their spread says how good the top is, not whether the score saturates (a perfect recommender would have a *small* served-card IQR). Measured on the release-1 grid: E's IQR is 0.13 over the 23 served cards but **0.66 over all 180 gated candidates** (v1: ≈ 0); the ranking magnitude C separates consecutive served cards by a median of 0.027 (v1's order differed by float16 steps, 10⁻³). Both are now tests (`tests/test_recommender_golden.py`). Owner: revert to the original wording if you disagree; the numbers above are what it would measure.

## 5. Not doing (yet)

- Cross-user recalibration from tastings (v1 § 15.1 at population level): after the per-user loop has data.
- An emulator and Bayesian optimisation over proportions (v1 § 15.2): only once the score is meaningful and calibrated, otherwise it finds model errors faster.
- Mixed cultures beyond attaching one organism (true multi-profile physics in one jar).
