# Evolution Spec: fermentgraph → legitimate FermentTrack dependency

**For:** a Claude session working in `fermentgraph` directly.
**Origin:** an audit run from FermentTrack (2026-09-17) found FermentTrack's docs assumed a `generate_suggestions()`/`query_analogs()` API that doesn't exist in this codebase, and that the evaluated ranker doesn't beat a trivial baseline. Full audit text and FermentTrack's verdict: `FermentTrack/docs/DEPENDENCIES.md` (section 2) — read that first for the receipts behind every claim below.

**Status (2026-09-17): the hygiene work below is done** (CI, version 0.2.0, CHANGELOG, suggestion/analog claims struck from docs — verified, 364 tests pass).

## Requirement added 2026-09-18, then DEFERRED same day after review — do not start this yet

FermentTrack considered building ingredient/compound/microbe reference data (recipe logging + a batch preview UI) sourced from this repo. A 3-agent review of FermentTrack's design spec found that surfacing unvalidated compound/microbial data on FermentTrack's first-ever UI screen would repeat the exact overclaiming mistake `docs/DEPENDENCIES.md` already caught once (fictional `generate_suggestions`/`query_analogs`) — even with an "unvalidated" label, a panel a user notices is marketing it as a current feature. **This requirement is deferred until the same Direction 3 trigger as the rest of the Knowledge Engine: fermentgraph's ranker beats the popularity baseline by ≥+0.05 Recall@50.** Full context: `FermentTrack/docs/superpowers/specs/2026-09-18-experiment-logging-design.md` ("Deferred" section).

**When the trigger fires, the actual build is small — verified, not assumed:** `associated_microbes` requires zero new curation. It's pure composition of two methods that already exist: `FermentationPriors.systems_for_food()` (`fermentation.py:222`) and `system(name).microbes` (`:241`, populated from `fermentation_systems.yaml` at `:189` with real NCBI-taxon-ID-linked microbe data, not a stub). `associated_compounds` comes from `FermentationPriors.prior_for()`, also already exists. The eventual work is a thin serialization script, not a modeling task.

**What to build, when the trigger fires:** an export script producing a JSON artifact with `schema_version`, `run_id` (reuse the existing gold-data `run_id` concept, e.g. `curated-gold1`), and per-ingredient `canonical_id`, `name`, `foodon_id`, `fermentation_systems`, `associated_compounds`, `associated_microbes`. Full JSON shape is in the design doc referenced above.

**Non-negotiable:** every compound/microbe association is a heuristic prior, not a validated prediction — carry that framing into the export's own docs/README.

**Scope guardrail (learned from this repo's earlier scope-violation incident — restated here explicitly, not just inherited from the Path A/B section above):** this is an export/serialization task only. Do not touch `evaluation/`, `models/`, `bootstrap/`, or any ranker/training code. The export reads `FermentationPriors` and gold artifacts already on disk — it does not compute anything new.

**Definition of done, when the trigger fires and this is picked up:** export script exists, produces valid output matching the documented schema, has a test asserting the schema (required fields present, `schema_version` set), and is documented in this repo's README as "reference export for FermentTrack — heuristic priors, not validated predictions."

## Where things actually stand (verified, not asserted)

- Package installs cleanly, 364 tests pass, gold-tier KG materialized at 100% readiness.
- `generate_suggestions`, `query_analogs`, "analog" — zero occurrences in `src/`. These were never built.
- `docs/RANKER_EVALUATION_REPORT.md`: LightGBM ranker regresses Recall@50 vs. popularity baseline (-0.001; promotion bar is +0.05).
- `docs/FERMENTATION_SLICE_EVAL_REPORT.md`: fermentation-specific knowledge prior produces exactly 0.0000 delta on every metric. Repo's own verdict: "the supervised re-ranking channel for this knowledge layer is null at the current scale."
- `docs/FERMENTATION_SUGGESTIONS_REPORT.md`: the one channel with nonzero signal is self-labeled exploratory/hypothesis-generation, curated rather than blind, and only 2 of 4 test foods survive multiple-comparison correction.
- `FermentationPriors.prior_for()` (`src/fermentgraph/knowledge/fermentation.py:204`) is the one real, deterministic artifact — a static heuristic lookup, not a validated prediction.
- Main has uncommitted/untracked files touching core modules (`gold/service.py`, `evaluation/*`, `features/`, `models/`, `bootstrap/`, `ingestion/`, plus `knowledge/` and `scripts/analysis/` untracked) — 19 at first audit, 34 `git status --porcelain` entries at re-check a day later. The count drifts; the fact (main is dirty with in-flight core-module changes) doesn't. No CI, v0.1.0 with no versioning discipline or CHANGELOG.

**Loop-safety note (2026-09-17 review):** Path A below is *not* safe to hand to an unsupervised Ralph Loop as written — step 1 requires a judgment call about whether the null result is fixable, and step 4 explicitly requires negotiating a signature with whatever's consuming it. Only Path B (package hygiene + honest documentation) has a fully mechanically-checkable done-state. If setting up an autonomous loop against this spec, use Path B only.

## Two honest paths forward — pick one, don't straddle

### Path A: Make the suggestion/analog ambition real
Only worth it if you believe the null result is a data/feature/scale problem, not a ceiling.

1. Diagnose the 0.0000 delta before touching the model — is it a genuine null effect, or a plumbing bug (features not reaching the ranker, eval set degenerate, labels miscomputed)? A perfectly flat 0.0000 across every metric is unusual enough to warrant a leak/bug check before more modeling.
2. If it's genuinely null: more/better labeled data is probably the bottleneck, not model choice — a LightGBM ranker regressing vs. popularity on a small gold set is a classic small-n symptom.
3. Target: beat popularity baseline by ≥+0.05 Recall@50 on held-out splits, reproducibly, before building any `generate_suggestions`/`query_analogs` module.
4. Only then implement the API surface FermentTrack's `ARCHITECTURE.md` sketches — negotiate the exact signature with whatever's consuming it at the time; don't pre-build an API for a model that doesn't exist yet.

### Path B: Retire the "suggestions" framing, ship what's real
The lower-risk, faster option given the current evidence.

1. Stop describing `fermentgraph` as producing "suggestions" or "analogs" in any doc — it produces a static, curated knowledge prior today.
2. Document `FermentationPriors.prior_for()` as the actual product: a hand-curated enzyme/microbe → compound plausibility lookup. Give it a stable, versioned contract (input/output schema, what `run_id`s exist, deprecation policy).
3. Position it honestly: "unvalidated heuristic knowledge hint," not a prediction. Anyone consuming it (FermentTrack or otherwise) should be told this explicitly in their own UI.

## Non-negotiable regardless of path: package hygiene

FermentTrack (or anyone) can't depend on this repo safely today independent of the modeling question:

1. **Stabilize main** — commit or discard the 19 uncommitted files touching `gold/service.py` and `evaluation/*`. A dependency's main branch shouldn't have in-flight changes to core modules.
2. **Add CI** — pytest + lint on every push at minimum. Currently zero CI.
3. **Adopt versioning discipline** — semantic versioning, a CHANGELOG, and a decision on whether this goes on PyPI or stays a git dependency.
4. **Pin data-artifact versioning** — `FermentationPriors.from_gold(..., run_id=...)` takes a `run_id`; document what `run_id`s are stable/supported so consumers aren't silently broken when gold data regenerates.

## Definition of done (flips FermentTrack's verdict from "don't use yet")

Either:
- **Path A:** ranker beats popularity baseline by ≥+0.05 Recall@50 on held-out splits, reproducibly, **and** a versioned + CI-tested package ships, **or**
- **Path B:** `FermentationPriors` ships as a versioned, CI-tested package with an honest "heuristic, unvalidated" contract — FermentTrack can then decide whether a labeled hint is worth surfacing at all (likely still low priority vs. Direction 4's Safety Advisory).

Either way: package hygiene (CI, versioning, stable main) is required before FermentTrack revisits this, independent of which modeling path you take.
