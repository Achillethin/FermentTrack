# Dependency Decisions

FermentTrack's original strategy docs (`STRATEGY.md`, `ARCHITECTURE.md`, written during the ideation sprint) assumed integrations with `fermentgraph` that turned out not to exist in its code. This doc replaces assumption with verified fact: each of the three sibling repos was independently audited on 2026-09-17 — code read, tests actually run, claims checked against implementation, not against the other repo's own README. Decisions below are binding until their trigger condition is met.

## Summary

| Repo | Verdict | What FermentTrack gets today | Integration pattern | Trigger to revisit |
|---|---|---|---|---|
| [`fermentation`](../../fermentation) (digital twin) | **Use now** | Monod twin + cited food-safety rule engine | Vendor ~450 lines + `risk_rules.yaml` | — already good |
| [`fermentgraph`](../../fermentgraph) | **Don't use yet** | Nothing safe to ship as a feature | — | Ranker beats popularity baseline by ≥+0.05 Recall@50 **and** a versioned, CI-tested package ships |
| [`fermentation-control-poc`](../../../Own%20Projects/fermentation-control-poc/fermentation-control-poc) | **Use later** (soft sensor only, never MPC) | Nothing today | pip dependency, once triggered | Soft sensor validated on a real fermentation-domain dataset (not penicillin/IndPenSim); MPC rebuilt on do-mpc/CasADi + validated closed-loop against data it wasn't fit to |

## 1. `fermentation` digital twin — USE NOW

**Reality.** `twin/baseline_model.py` (Monod kinetics + Ratkowsky temperature factor + linear salt inhibition, integrated via `scipy.solve_ivp`) and `safety/rule_engine.py` (AST-based rule evaluator — not `eval`, with a git history showing a deliberate security hardening pass and red-team tests) are both real, correct, and tested: 607/609 tests pass, rules are cited against EFSA 2005;3(4):199, ANSES 2014-SA-0174, and CDC guidance. Live smoke test confirmed a low-salt/high-temp lacto-ferment scenario correctly triggers a botulism hard-stop, matching the cited literature. Everything else in the repo (`foundation_model.py`, `flavor/tracker.py`, `graph_model.py`, `pinn_model.py`) is honestly self-labeled heuristic/untrained scaffold in its own docstrings — accurate, not aspirational, but not production material.

**Interface:**
```python
from fermentation.twin.baseline_model import BaselineMonodModel
from fermentation.twin.state import TwinState
from fermentation.safety.rule_engine import SafetyRuleEngine

state = TwinState(scheme="lactic", temperature_c=25, salt_pct=1.5, ph=6.5)
BaselineMonodModel().simulate(state, total_hours=48)
SafetyRuleEngine().evaluate(state.state_vars(), scheme="lactic")  # -> SafetyReport(.safe, .hard_stops, .warnings, .summary_en/.summary_fr)
```

**Integration pattern: vendor, don't pip-depend.** This repo is solo-maintained, pre-1.0, and carries a heavy unrelated dependency footprint (torch, torch-geometric, duckdb, networkx) for research directions FermentTrack doesn't need. Copy `twin/baseline_model.py`, `twin/state.py`, `safety/rule_engine.py`, `safety/rule_catalog.py`, `safety/ast_evaluator.py`, and `data/curated/risk_rules.yaml` into `src/fermenttrack/safety/`, mirroring the upstream red-team tests locally. This decouples FermentTrack's release train from the parent repo's research-scaffold churn while keeping the well-tested slice.

**Unlocks a real Phase 1 feature not in the original scope:** a **Safety Advisory** — flag risky batch conditions (e.g. low-salt lacto-ferment held too warm) using cited food-safety rules, computed from the same `Measurement` history the batch logger already stores. This is more concretely shippable than the FermentGraph "intelligence" pillar ever was.

**Explicitly excluded:** `foundation_model.py`, `flavor/tracker.py`, `graph_model.py`, `pinn_model.py` — no trained weights, no validation, don't surface as predictions.

**2026-09-24 note:** the fermentation forecast (`src/fermenttrack/prediction/`, spec `docs/superpowers/specs/2026-09-24-fermentation-prediction-design.md`) is built in this repo from cited literature kinetics, not vendored from the twin. It does not use the excluded GNN/PINN scaffolds (with zero training batches neither can be trained; the spec records the triggers). The vendored `BaselineMonodModel` stays as-is under `safety/`; the Safety Advisory still evaluates measured values only.

## 2. `fermentgraph` — DON'T USE YET

**2026-09-23 note:** this verdict is unchanged. A separate reference layer (organisms/enzymes/compounds keyed by fermentation type) was added sourced from KEGG instead of fermentgraph — see `docs/superpowers/specs/2026-09-23-fermentation-biochemistry-design.md`. KEGG supplies canonical enzyme and compound identity (EC-number validity and names, compound ids and names); the organism-enzyme, enzyme-reaction and fermentation-type-organism mappings are hand-curated domain knowledge pending owner review. That spec does not depend on this repo at all; it reverses only `STRATEGY.md` Direction 3's UI-deferral condition, not this dependency verdict.

**Reality.** `generate_suggestions(context)` and `query_analogs(...)` — the exact calls `ARCHITECTURE.md` documented — **do not exist anywhere in the codebase** (zero hits for "analog", "generate_suggestions", "query_analogs" in `src/`). They were invented during the strategy sprint, not verified. What's real: the package installs cleanly and 364 tests pass; the gold-tier knowledge graph is materialized and at 100% readiness. But the two things FermentTrack actually wanted are evaluated and found not to work: the LightGBM ranker *regresses* Recall@50 vs. a trivial popularity baseline (-0.001, needs +0.05 to promote), and the fermentation-specific knowledge prior produces **exactly 0.0000 delta** on every metric — the repo's own verdict is "the supervised re-ranking channel for this knowledge layer is null at the current scale." The one channel with any signal is self-labeled exploratory/hypothesis-generation, curated (not blind), and only 2 of 4 test foods survive multiple-comparison correction.

**The only real, deterministic building block:**
```python
from fermentgraph.knowledge.fermentation import FermentationPriors
priors = FermentationPriors.from_gold(gold_dir, run_id="curated-gold1")
priors.prior_for(canonical_food_id, canonical_compound_id)  # -> float, static heuristic weight, not a prediction
```
Not wired into FermentTrack today. If used at all before the trigger fires, it must sit behind a UI label reading "heuristic knowledge hint (unvalidated)" — never presented as a prediction or suggestion.

**Structural risk independent of the ranking result:** main has 19 uncommitted/untracked files including core modules, no CI, no versioning discipline (v0.1.0, no CHANGELOG, not on PyPI). Not stable enough to depend on even if the ranker worked.

**Action taken:** `generate_suggestions`/`query_analogs` struck from `ARCHITECTURE.md` and the "Knowledge Engine" pillar in `README.md`/`STRATEGY.md` reframed as future/exploratory rather than a differentiator that exists today.

## 3. `fermentation-control-poc` — USE LATER, soft sensor only

**Reality.** The headline claim (soft-sensor biomass estimation, R²=0.9835, nRMSE=0.0343, proper batch-level holdout, no leakage) reproduced exactly on a live re-run — this is a genuinely good, honestly-evaluated result. But it's validated on **IndPenSim — industrial penicillin fermentation (*Penicillium chrysogenum*), not wine or any beverage fermentation.** The project's own action plan admits no real wine fermentation dataset with published raw data exists yet. The README's "GO" framing reads as wine-relevant; it isn't yet.

MPC (`control/mpc.py`) self-labels "PAS un MPC de production" — a brute-force grid search over 6 temperature candidates, validated by simulating it against the *same* Monod model used to generate its training signal (self-consistency, not real closed-loop validation against independent data or disturbances). The near-perfect result (residual sugar → ~1e-6 g/L) is an artifact of that circularity, not evidence of a working controller.

**Structural mismatch beyond validation domain:** the soft sensor needs dense online sensor streams (substrate, DO₂, pH, temp, volume at short intervals); FermentTrack Phase 1 users log sparse manual measurements a handful of times per batch. Phase 2 "Industrial Control" needs a new dense sensor-ingestion path before this dependency is usable at all, independent of the domain-validation trigger.

**Verdict:** don't depend on MPC, full stop — a "control recommendation" UI backed by a self-validated grid search would actively mislead professional users. Depend on the soft sensor later, once triggered:
```python
from fermentation_poc.models.soft_sensor import SoftSensor  # .fit(X, y) / .predict(X) / .load(path)
```
via pip dependency (it's a clean `src/`-layout package, `fermentation-poc` v0.1.0) — no vendoring needed since it's a narrow, stable, independently-testable model class.

## Next steps

Per-repo evolution specs describing what would need to change for each trigger to fire: [`docs/specs/fermentgraph-evolution.md`](specs/fermentgraph-evolution.md), [`docs/specs/fermentation-twin-evolution.md`](specs/fermentation-twin-evolution.md), [`docs/specs/fermentation-control-poc-evolution.md`](specs/fermentation-control-poc-evolution.md).
