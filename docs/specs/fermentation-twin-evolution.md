# Evolution Spec: `fermentation` digital twin → cleaner dependency surface

**For:** a Claude session working in `fermentation` directly.
**Origin:** an audit run from FermentTrack (2026-09-17) verified `twin.baseline_model` and `safety.rule_engine` are real, correct, tested (607/609 passing), and cited against food-safety literature (EFSA 2005;3(4):199, ANSES 2014-SA-0174, CDC). Full audit: `FermentTrack/docs/DEPENDENCIES.md` (section 1). **This repo is already a "use now" verdict** — this spec is about making that dependency cheaper and safer to consume, not about fixing correctness.

## Where things actually stand (verified, not asserted)

- `twin/baseline_model.py` (Monod kinetics + Ratkowsky temperature factor + salt inhibition, `scipy.solve_ivp`) and `safety/rule_engine.py` (AST-based evaluator, not `eval` — git history shows a deliberate hardening pass `1073e910`, plus red-team tests in `tests/safety/redteam/`) are both real, working, and correctly scoped.
- **Correction (2026-09-17 re-check):** 651 passed, 2 failed (full suite, 16m19s) — the earlier 607/609 count was from a partial run. The 2 failures are still unrelated to twin/safety: a pydantic literal-enum mismatch in the gold data pipeline, and an env-var propagation test artifact. **Root cause correction:** the `kegg_koji` literal-enum failure's raise site is `src/fermentation/transform/gold.py:236`, but the actual fix belongs upstream in `src/fermentation/transform/validators.py:311-327` — the `SourceName` Literal there omits `"kegg_koji"` while `gold.py:45`'s `_REACTION_PRIORITY` includes it. Add `"kegg_koji"` to the `SourceName` Literal, don't edit `gold.py:236` directly.
- `foundation_model.py`, `flavor/tracker.py`, `graph_model.py`, `pinn_model.py` are honestly self-labeled heuristic/untrained scaffold in their own docstrings — accurate, not a problem, just not consumable as predictions by anyone.
- `.wave2-f0/` is untracked (`git ls-files .wave2-f0` → 0 results) and contains a **pre-AST-evaluator** version of the safety engine (regex-gated `eval`) — an old local snapshot, not a newer iteration.
- FermentTrack currently plans to **vendor** (copy) `twin/baseline_model.py`, `twin/state.py`, `safety/rule_engine.py`, `safety/rule_catalog.py`, `safety/ast_evaluator.py`, and `data/curated/risk_rules.yaml` into its own repo rather than pip-depend, specifically because this repo pulls torch, torch-geometric, duckdb, and networkx for research directions unrelated to the safety/twin slice.

## Action items

1. **Fix the 2 known test failures** — cosmetic before anyone downstream trusts the suite blindly. The `kegg_koji` literal-enum mismatch in `transform/gold.py:236` looks like a one-line fix (add the literal to the allowed set or fix the source tag upstream).
2. **Carve out a minimal-dependency subpackage — locally, not published.** Split `twin.baseline_model` + `twin.state` + `safety.*` (+ `risk_rules.yaml`) into an isolated subpackage directory under `src/` (e.g. `src/fermentation_safety_core/`) with its own minimal `pyproject.toml` declaring only `scipy`, `pyyaml`, `pydantic`. This part is mechanical and loop-safe. **Publishing it as a separate PyPI package, naming it permanently, or splitting it into its own git repo is a product/ownership decision — that needs Achille, don't do it autonomously.**
3. **Delete or gitignore `.wave2-f0/`.** It's an untracked stale snapshot carrying the pre-hardening, regex-`eval` version of the safety engine — a real foot-gun if anyone ever imports from it by accident given the security-sensitive nature of that code path.
4. **Already done — no action needed.** `pyproject.toml:23-27` already gates `torch`/`torch-geometric` behind `[project.optional-dependencies] ml` (not `research`, but functionally equivalent). Confirmed 2026-09-17; renaming the extra is cosmetic and not worth an iteration.
5. **Add CI running the safety red-team tests on every push**, given the AST evaluator is a security-sensitive parser. A regression there is exactly the kind of thing that should never land silently.
6. **Keep the "not a validated model" self-labeling** in `foundation_model.py`/`flavor/tracker.py`/GNN/PINN docstrings exactly as strict as it is now — it's accurate and it's doing real work protecting downstream consumers from over-trusting heuristic output. Don't soften it even if training work starts; wait for an actual validation report before changing the claim.

## Definition of done

Not gated — FermentTrack already depends on (vendors) this today. Completing items 1-3 above lets FermentTrack switch from a vendored copy to a real `pip install fermentation-safety-core` dependency without churn, and removes a live security foot-gun (`.wave2-f0`). Item 4-5 make the repo cleaner for any other downstream consumer, present or future.
