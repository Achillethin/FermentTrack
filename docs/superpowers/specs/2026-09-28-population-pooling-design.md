# Population-Level Prior Pooling (Stage A) — Design

**Date:** 2026-09-28
**Status:** Implemented on branch `research/stage-a-pooling`
**Builds on:** `2026-09-24-fermentation-prediction-design.md` (`inference.py`'s AMIS,
`organisms.py`'s literature priors, `service.py`'s pure prediction flow) §9's "Later path"
trigger: *"Hierarchical priors — trigger: ~20-30 batches of a type with ≥3 readings. Fit a
population distribution over per-batch posterior shifts... it becomes the next batch's
prior."* This is that trigger pulled forward to n~1-20, at plug-in-EB scope rather than a
full joint hierarchical fit — see Decisions below for why.

## Problem and goals

Every batch's AMIS run (`inference.py`) starts from the same fixed literature `Prior` in
`organisms.py` and throws its posterior away once the forecast is served. Nothing learned
from one batch of an organism informs the next batch of the same organism — the app has
no memory across batches, even though `mu_max` and `t_opt` are exactly the kind of thing
real fermentations should let it learn (a user's actual starter culture, actual kitchen
temperature variance, etc., pull these away from the literature median).

Goal: a finished batch's converged posterior updates a **population-level** prior per
(organism, parameter), global across all users (the data flywheel, `docs/STRATEGY.md`),
so a later batch of the same organism starts closer to what has actually been observed.

Non-goals (this pass): a full joint hierarchical posterior over all batches at once; more
than two pooled parameters; covariates (temperature, salt, starter share) on the pooled
estimate; per-owner scoping. These are the natural next escalations, not this task — see
Later path.

## Decisions

| Question | Decision | Rejected, and why |
|---|---|---|
| Update rule | **Empirical-Bayes plug-in**: each finished batch's own posterior weighted mean (in the parameter's log/lin scale) is treated as one point observation of the population parameter; the population prior's median/lo/hi track a running mean and the *standard error of that mean* (Welford's online algorithm) across batches | **Full joint hierarchical model** (batch-level and population-level parameters fit together, e.g. by SMC²): correct, but a rewrite of `inference.py`'s per-batch AMIS into a single cross-batch sampler — disproportionate at n~1-20 batches per organism, and the literature (Pouillot et al. 2003) already treats plug-in EB as the reasonable first rung. Escalate per the ponytail note in `population.py` once under-shrinking is visible at 10+ batches/organism |
| What "spread" means | The row's lo/hi encode uncertainty **in the pooled mean itself** — the unbiased SEM, `s²/n` with `s² = M2/(n-1)` — not the spread of individual batches' estimates (s²) — so the prior legitimately narrows as more batches agree, which is what a later batch's AMIS should see: a tighter, more confident starting point | Storing raw between-batch variance: two organisms with a genuinely long-run non-degenerate spread (real strain variance, real kitchen variance) would never narrow past that spread, which reads as "pooling isn't working" even though it is. **Known gap** (flagged by review, not yet fixed): because only the SEM is persisted, the design's own escalation trigger below ("under-shrinking becomes visible") has nothing to compare against — SEM shrinks like 1/n by construction regardless of real heterogeneity. Tracking raw between-batch variance alongside SEM is the natural fast-follow |
| Which batches count | Only a batch whose forecast reached `status == "calibrated"` (it had usable pH/gravity/Brix readings and AMIS actually reweighted the ensemble) is pooled; `"prior_only"` batches are skipped even if finished | Pooling every finished batch regardless of status: a batch with zero usable readings has an AMIS "posterior" identical to the prior plus finite-ensemble Monte Carlo noise (160 draws) — pure noise, not information, that would still narrow the population SEM as if real evidence had arrived. Caught in review (see below) |
| Concurrent finishes | The idempotency claim (`batches.population_pooled_at`) is an atomic compare-and-swap `UPDATE ... WHERE population_pooled_at IS NULL`, and the `PopulationPrior` row's read-modify-write is done under `SELECT ... FOR UPDATE` | An ORM-object flag check-then-set (`if batch.population_pooled_at is None: ... batch.population_pooled_at = now()`) with a plain `SELECT`, no locking: two concurrent requests for the *same* finished batch would both pass the check and both pool it (double-counting `n_obs`); two *different* batches of the *same* organism finishing concurrently would race on the same `PopulationPrior` row and lose one update silently. Both are real under Postgres READ COMMITTED, not just a theoretical concern — caught in review |
| Which params | Exactly `mu_max` (log-scale) and `t_opt` (lin-scale) — `POOLED_PARAMS` in `population.py` | All ~15 per-organism params: over-fit at n~1-20 batches; most (Ks, yields, cardinals other than t_opt, MICs, aw_min, ...) are barely identifiable from the 0-10 sparse pH/gravity/Brix points a batch typically logs, so their "posteriors" are close to their priors anyway and pooling them would mostly pool noise |
| Threshold | `MIN_POOLED_OBS = 3`: `population_prior_for` returns the unmodified literature `Prior` below 3 pooled batches, the pooled prior at/above it | n_obs ≥ 1: at n=1 the pooled "prior" **is** exactly one batch's posterior mean with zero recorded spread — a single anecdote masquerading as informed; 3 is the smallest n where the running SEM reflects more than one data point |
| Scope | **Global** across all users' batches of an organism, matching `docs/STRATEGY.md`'s aggregate-kinetics flywheel — only numeric (mu_max, t_opt) posterior summaries are pooled, never notes, text, or anything batch- or owner-identifying | Per-owner pooling: most owners will never accumulate 3+ batches of the same organism themselves, so a per-owner pool would rarely clear the threshold and the whole feature would sit dormant for nearly everyone |
| Where the DB lives | **`routers/prediction.py`** reads/writes `population_priors`, not `service.py` | `service.py`'s own docstring: *"Pure (no DB): the router builds PredictionInputs."* Threading an `AsyncSession` into `predict()` (a plain sync function run in a threadpool, cached by LRU) would break that invariant for every caller, sync test included. `service.py` instead exposes: (a) `ModelSpec.population_priors` / `PredictionInputs.population_priors`, a plain `dict[organism name, dict[param name, Prior]]` the router pre-resolves and passes in, and (b) `population_samples(inputs)`, a pure accessor onto a small in-process cache (`_POOL_SAMPLES`, keyed like the existing posterior cache) populated at the moment AMIS converges for a finished batch. The router calls `population.population_prior_for`/`update_population_prior` (the only `async def`s that touch the DB) before and after `predict()` |
| Idempotency | New `batches.population_pooled_at` (nullable timestamp); the router only pools when `finished and batch.population_pooled_at is None`, and sets it in the same commit as the pooling writes | Relying on the in-process `_POOL_SAMPLES`/`_POSTERIORS` LRU caches alone: they're per-process and evict, so a second request after a restart or eviction would re-run inference and (without the DB flag) re-pool the same batch, double-counting it in `n_obs` |
| Fingerprint | `population_priors` is a field on `PredictionInputs` (so a pooled-prior change invalidates the forecast cache — a changed prior is a changed model) but is dropped from the fingerprint blob when empty, so every non-pooling call (today's tests, any organism/param below threshold) hashes byte-identical to before this feature existed | Always including it: even an empty `{}` changes the JSON blob and therefore the `predict()` seed derived from it, silently reseeding AMIS for every existing caller and shifting borderline-tolerance test assertions (caught by the full suite — `test_readings_pull_the_forecast_and_narrow_it` moved from 4.3 ± 0.35 to 4.78 before this fix) |

## 1. Data model

`PopulationPrior` (migration `0015_population_priors.py`): `organism_id` (FK →
`organisms.id`), `param_name` (`"mu_max"` | `"t_opt"`), `n_obs`, `median`/`lo`/`hi` (the
pooled `Prior`'s fields, same log/lin `scale` as the literature prior it can override),
`updated_at`. Unique on `(organism_id, param_name)`. `batches.population_pooled_at`
(nullable timestamp) guards idempotency (§ Decisions).

## 2. Update rule, precisely (`prediction/population.py`)

For a finished batch's weighted posterior samples `(values, weights)` of one pooled
param, transform to the prior's own scale (`log(values)` or `values`), take the weighted
mean `mean_b`. Recover `(mean, M2)` of a Welford accumulator from the stored row (its
lo/hi is `Z90 * sqrt(M2 / n_obs²)` around `mean` — the row *is* the accumulator's encoded
state, so no extra columns are needed), fold in `mean_b` as observation `n_obs+1`, and
re-encode. At `n_obs=1` this reduces to exactly the batch's own posterior mean with zero
spread (unused below the threshold; see Decisions). The transform back to the parameter's
native units uses the same split-normal encoding as `priors.Prior` itself, so a pooled
`Prior` is usable everywhere a literature one is.

`population_prior_for(db, organism_id, param_name, fallback)` reads the row and applies
the `MIN_POOLED_OBS` gate; `update_population_prior(db, organism_id, param_name, samples,
weights, scale)` performs one Welford step and upserts the row.

## 3. Wiring

- `model.ModelSpec` gains `population_priors: dict[organism name, dict[param name,
  Prior]]`, consulted alongside the existing `x_max_override` pattern when building each
  organism's `ParamSpec`s — `mu_max`/`t_opt` use the pooled `Prior` when present, every
  other param is untouched.
- `service.PredictionInputs` gains the same shape; `service._spec` threads it into
  `ModelSpec`. `routers/prediction.py` resolves it per organism (only for organisms with
  a literature `OrganismKinetics` entry) via `population.population_prior_for` before
  building `PredictionInputs`.
- `service._forecast`, right where a finished batch's AMIS posterior is computed (the
  existing `if lite is None:` branch, mirroring how `_POSTERIORS` is populated), also
  captures physical-space `(values, weights)` for `population.POOLED_PARAMS` per modelled
  organism into `_POOL_SAMPLES` — a small LRU keyed by the same fingerprint. `service.
  population_samples(inputs)` is the pure read of that cache.
- `routers/prediction.py`, after `predict()` returns, pools when `finished`, the batch
  isn't pooled yet, and `body["status"] == "calibrated"`. It first claims the batch with
  an atomic `UPDATE batches SET population_pooled_at = now() WHERE id = :id AND
  population_pooled_at IS NULL` (only one of any concurrent requests wins the claim);
  only the winner reads `population_samples(inputs)` (`None` if inference didn't run this
  call, e.g. an already-cached output — the claim is then rolled back so a later call can
  retry rather than marking the batch pooled for nothing) and calls
  `update_population_prior` per organism × pooled param under a row lock, then commits.

`predict()`'s public response schema, and every existing `test_prediction_*.py`, are
unchanged — pooling is entirely a side channel around the same pure forecast.

## 4. Self-check

`tests/test_population_pooling.py`, assert-based, deterministic (samples are constructed
with an exact known weighted mean — no RNG-driven flakiness in the statistical
assertions):

1. A single finished batch's `update_population_prior` moves the stored row's median away
   from (and, at `n_obs=1`, exactly onto) that batch's own posterior mean.
2. `population_prior_for` returns the unmodified literature prior below `MIN_POOLED_OBS`
   pooled batches, and the pooled one at/above it.
3. Pooled spread (`hi - lo`) strictly narrows as more agreeing batches accumulate
   (`n_obs` 2→5) — the SEM-shrinkage claim, not just "it runs".
4. `GET /batches/{id}/prediction`, called twice on the same finished batch end-to-end,
   pools exactly once (`population_pooled_at` set once, `n_obs == 1` not `2`).
5. `_transformed_mean` actually uses the importance weights (a 99:1-skewed two-point
   case) — guards against a silent fallback to an unweighted mean, which the
   deterministic identical-sample construction in 1-4 can't itself catch.

This feature went through one independent statistical review pass (`ds-reviewer`,
2026-09-28) before being called done; two of its findings were real, not just
theoretical, and are now fixed (see the Decisions table rows above and the diffs they
describe): pooling gated on `status == "calibrated"`, and the concurrent-finish races
closed with an atomic claim + row lock. The SEM-vs-raw-variance instrumentation gap
(Decisions, "What spread means") is real and intentionally left open — noted there and
in `population.py`'s module docstring rather than fixed, since it only affects the later
escalation trigger, not correctness of what's served today.

## Later path

- **Track raw between-batch variance alongside SEM** — trigger: none needed, this is a
  known gap in what's already shipped (see Decisions), not a future capability. Small
  addition once it's worth the schema churn: store `s²` (or just `M2`) next to the SEM
  the row already carries, so the hierarchical-priors trigger below is actually
  observable instead of structurally unable to fire.
- **Hierarchical priors with covariates** — trigger: an organism with 10+ batches (the
  ponytail ceiling noted in `population.py`) shows *less* variance reduction than this
  plug-in predicts, i.e. real batch-to-batch heterogeneity the running-mean/SEM model
  can't represent (only checkable once the item above exists). Escalate to SMC² (Chopin,
  Jacob & Papaspiliopoulos) or a proper partial-pooling fit (temperature, salt, starter
  share as covariates on the per-batch shift), per §9 of the prediction design.
- **Per-batch precision weighting** — trigger: a well-identified batch (tight AMIS
  posterior, high ESS) and a barely-identified one (near the tempering floor) are
  currently folded into the population prior as equally-weighted single points. Weighting
  each batch's contribution by its own posterior precision (e.g. inverse-variance
  weighting) is the natural next refinement short of a full hierarchical rewrite.
- **More pooled params** — trigger: enough batches per organism that `Ks`, yields, or the
  other cardinals stop looking like pure noise when pooled (their per-batch posteriors
  visibly separate from the prior, not just resample it).
- **Per-type / cross-organism transfer** — out of scope entirely for now; would need a
  guild-level model (§9's GNN escalation), not this plug-in.

## References

Pouillot, Albert, Cornu & Denis 2003 Int J Food Microbiol 81:87 (Bayesian pooling of
microbial growth parameters across studies) · Cornuet, Marin, Mira & Robert 2012 Scand J
Stat 39:798 (AMIS, unchanged here — pooling only changes the prior it starts from) ·
Chopin, Jacob & Papaspiliopoulos 2013 J R Stat Soc B 75:397 (SMC², the escalation path) ·
Welford 1962 Technometrics 4:419 (the online mean/variance update this reuses).
