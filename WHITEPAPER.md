# FermentTrack's Forecasting Model: A Mechanistic-Bayesian View

**Scope:** the science behind `prediction/`, current through Stage A (population-level
prior pooling, 2026-09-28). Engineering detail lives in `docs/superpowers/specs/`; this
is the model, written up as a model.

## 1. The generative model

A batch is a partially observed multi-species chemostat-free fermentation. The state is
a vector of pool concentrations (sugars, acids, ethanol, CO₂, enzyme activities) and, per
organism, log-biomass and a Baranyi–Roberts lag state. The forward map is a fixed,
non-stiff ODE system (`engine.py`, `scipy.solve_ivp`, RK23) — mechanistic, not learned:
Monod growth gated by CTMI temperature and CPM pH cardinal functions (Rosso et al.
1993/1995), Luedeking–Piret product flux, undissociated-acid and water-activity
inhibition, a charge-balance pH solve. Every organism's kinetic parameters (`mu_max`,
`Ks`, cardinal temperatures, MICs, ...) are literature priors: a median and a ~90 %
interval, encoded as a split-normal in log or linear space (`priors.Prior`) so the
ensemble samples in a common standard-normal z-space regardless of each parameter's own
units and skew.

This is a deliberately un-fancy choice — no PINN, no GNN, no learned residual — and the
design doc for it (`2026-09-24-...`) makes the argument on its own terms (a non-stiff
ODE the forward solver handles in milliseconds; an inverse problem so information-poor at
0–10 logged readings that a PINN would at best recover the same NLS estimate a classical
solver gets directly, per Grossmann et al. 2024 and Wang 2026). It is worth restating
because Stage A extends this same posture rather than reaching for a bigger model: the
information budget per batch hasn't changed, so the escalation is in *pooling*, not model
capacity.

## 2. Per-batch inference: AMIS as an ad hoc sequential importance sampler

Given a batch's readings, the posterior over kinetic parameters is approximated by
adaptive multiple importance sampling (Cornuet, Marin, Mira & Robert 2012): draw from the
prior, weight by a Student-t (ν=4) likelihood, refit a Gaussian proposal to the weighted
draws, resample, and reweight *all* draws against the deterministic mixture of every
proposal used so far — the mixture weighting is what keeps the estimator unbiased across
rounds rather than accumulating the usual multiple-importance-sampling degeneracy. ESS
gates both the adaptation loop (stop once ≥30 % of N is effective) and a likelihood
tempering fallback (shrink the exponent until ESS clears a floor) when the readings sit
at the edge of what the mechanistic model can explain at all. This is a reasonable
minimum-viable choice for the constraint that actually binds here — a few solves per
request on a 0.1 CPU instance — over the tempered-SMC alternative the original research
pass costed out (§5 of the prediction design: AMIS reached comparable coverage at ~4
solves vs. SMC's ~9).

What AMIS explicitly does *not* do: carry anything from one batch to the next. Each
batch's posterior is computed, used to render a forecast, and discarded. That is the gap
Stage A closes.

## 3. Stage A: empirical-Bayes plug-in pooling across batches

### 3.1 The estimand

For each (organism, parameter) pair in `POOLED_PARAMS = (mu_max, t_opt)`, there is
latent, unobserved population-level distribution of the "true" kinetic value — real
strain variation, real kitchen conditions, real reading noise all folding into it. Each
finished batch's AMIS posterior is noisy evidence about *its own* batch, not directly
about the population; the population value is what should inform the *next* batch's
prior. This is the textbook empirical-Bayes setup (Robbins 1956; in the food-microbiology
literature specifically, Pouillot, Albert, Cornu & Denis 2003 pool growth-parameter
posteriors across independent studies exactly this way).

### 3.2 What's implemented: posterior-mean plug-in, not the full hierarchical model

The honest description is a **plug-in EB estimator with one summary statistic per
batch**: each finished batch contributes exactly one number per (organism, param) — its
own posterior's weighted mean in the parameter's native (log or linear) scale — and the
population prior tracks a running mean and the *standard error of that mean* across
batches via Welford's (1962) online algorithm, re-derived each update from the stored
`(median, lo, hi, n_obs)` rather than a persisted raw sufficient statistic (no extra
columns; the split-normal encoding of `Prior` is exactly `mean ± Z90·SE`, so it doubles as
the accumulator's serialization).

This is a genuine simplification along two axes, both named explicitly rather than
smuggled in:

1. **One point per batch, not the batch's full posterior.** A batch with a beautifully
   identified `mu_max` (tight AMIS posterior, high ESS) and a batch with a nearly
   uninformative one (readings the model can barely explain, tempered likelihood, ESS
   near the floor) currently contribute *equally* to the population update — the pooling
   step is blind to each batch's own posterior precision. A full hierarchical treatment
   would weight each batch's contribution by its own posterior precision (inverse-variance
   weighting, or better, a proper joint model). This is the sharpest limitation of the
   current implementation and the first thing to fix if a handful of low-information
   batches are seen to drag a population prior somewhere the evidence doesn't support.
2. **A running mean/SE, not a distribution over per-batch effects.** The served spread is
   the *unbiased standard error of the pooled mean* (`s²/n`, `s² = M2/(n-1)`), which is a
   statement about how confident the estimate of the population mean is, not the
   population's own heterogeneity. This is a deliberate choice (organisms genuinely
   differ batch to batch — different starter viability, different kitchens — and that
   spread should inform the *next* batch's AMIS prior width, not vanish as an artifact of
   averaging many summaries together). It also means: if real between-batch heterogeneity
   is large, this estimator will still report a narrowing interval as `n_obs` grows,
   understating how much any one future batch could plausibly differ. That is the
   textbook failure mode of plug-in EB under-representing hyperparameter uncertainty
   (Morris 1983) and the reason the design doc sets an explicit trigger for escalation —
   *with one honestly-flagged catch*: nothing currently persists the raw between-batch
   variance that trigger would need to fire on, only the SEM derived from it, so the
   trigger cannot yet observe itself. Tracking that raw variance is queued as a fast
   follow, not treated as already handled.

Neither of these is a bug; both are the price of shipping something now instead of a
rewrite of `inference.py` into a single cross-batch sampler, at n≈1–20 batches per
organism where a fuller model has little data to be fuller *with*. `population.py` names
the ceiling directly (`ponytail:` comment) and the design doc's Decisions table gives the
reasoning a reviewer would want to check before agreeing with it.

**On review** (an independent `ds-reviewer` pass before this was called done), two
*other* issues turned out not to be documented simplifications but real bugs, and were
fixed rather than merely noted: a finished batch with no usable readings (`status:
"prior_only"`) was being pooled as if its AMIS "posterior" — literally just the prior
plus finite-ensemble Monte Carlo noise, since there was no likelihood to reweight against
— were real evidence; and the idempotency check (`population_pooled_at is None`) had no
atomicity, so two concurrent requests (double-click, two tabs) for the same finished
batch, or two different batches of the same organism finishing at once, could
double-count an observation or silently lose one to a lost-update race. Both are now
closed (gate on `status == "calibrated"`; atomic claim + row lock) — see the design doc's
Decisions table for the exact mechanism. The two numbered limitations above were reviewed
and *not* flagged as bugs: they're the stated cost of plug-in EB, not oversights.

### 3.3 The threshold as a minimum-information gate

`MIN_POOLED_OBS = 3` is not a magic number so much as the smallest `n_obs` at which the
served spread reflects more than a single realization — at `n_obs=1` the "pooled prior"
degenerates to one batch's own posterior mean with recorded zero spread, which is not a
prior, it's an anecdote. Below three, every batch still falls back to the literature
default untouched.

### 3.4 Scope: a shared, cross-user statistic, not personalization

Pooling is global across all users of an organism, not per-owner (`docs/STRATEGY.md`'s
aggregate-kinetics flywheel) — deliberately, since most individual owners will never log
three finished batches of the same organism, and per-owner pooling would sit dormant for
nearly everyone. Only the two numeric posterior summaries move; no batch content, notes,
or ownership information crosses the boundary.

## 4. Where this sits in the model's own roadmap

The original prediction design (§9, "Later path") already named the trigger this closes:
*"Hierarchical priors — trigger: ~20–30 batches of a type with ≥3 readings. Fit a
population distribution over per-batch posterior shifts... it becomes the next batch's
prior."* Stage A pulls that forward to n≈1–20 at plug-in scope rather than waiting for
20–30 batches to justify a full hierarchical fit with covariates — a reasonable trade
given the app currently has **zero** real finished batches of any kind (`model.validated:
false` everywhere), so there is no evidence yet to distinguish "plug-in is fine" from
"plug-in under-shrinks." The escalation trigger for the next step is explicit and
falsifiable: once an organism has 10+ real finished batches, check whether the served
spread is visibly narrower than the actual spread of those batches' own posterior means —
if so, move to SMC² (Chopin, Jacob & Papaspiliopoulos 2013) or a proper partial-pooling
fit with covariates (temperature, salt, starter fraction), which is what §9 originally
specified.

## 5. What would make this stronger evidence, not just a mechanism

Everything above describes a mechanism that is statistically sound *given* its stated
simplifications — it has not yet pooled a single real batch. The same validation posture
the base forecast model already carries (`model.validated: false`, a leave-future-out
coverage check gating that flag) should extend here: once real batches accumulate, the
thing to check is not "does the code run" but "does a pooled prior actually improve
held-out calibration of the *next* batch of that organism" versus always starting from
literature. That comparison — pooled vs. literature-only AMIS, scored by interval
coverage and CRPS on a held-out batch — is the natural first empirical test, and doesn't
exist yet.

## References

Rosso et al. 1993 *J Theor Biol* 162:447 · Rosso et al. 1995 *AEM* 61:610 · Cornuet,
Marin, Mira & Robert 2012 *Scand J Stat* 39:798 (AMIS) · Grossmann et al. 2024 *IMA J Appl
Math* 89:143 · Robbins 1956 *Proc 3rd Berkeley Symp* (empirical Bayes) · Pouillot,
Albert, Cornu & Denis 2003 *Int J Food Microbiol* 81:87 (EB pooling of microbial growth
parameters across studies) · Morris 1983 *JASA* 78:47 (parametric empirical Bayes:
confidence intervals) · Welford 1962 *Technometrics* 4:419 · Chopin, Jacob &
Papaspiliopoulos 2013 *J R Stat Soc B* 75:397 (SMC²).
