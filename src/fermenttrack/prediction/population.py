"""Empirical-Bayes plug-in pooling: a finished batch's converged AMIS posterior (per
organism, per kinetic parameter) updates a GLOBAL population-level prior, so the next
batch of the same organism starts closer to what has actually been observed instead of
always restarting from the fixed literature `Prior` in `organisms.py`.

Each finished batch contributes exactly one "observation" of the population parameter:
its own posterior's weighted mean (in the parameter's log/lin scale). The population
prior's median/lo/hi track a running mean and the *unbiased standard error of that mean*
(`s^2/n`, `s^2 = M2/(n-1)`; Welford's online algorithm) across batches — so the pooled
prior narrows as more batches agree, not just as individual batches get more readings.
This is posterior-mean plug-in, not a full joint hierarchical posterior: escalate to
SMC² (Chopin/Jacob/Papaspiliopoulos) if under-shrinking becomes visible once several
organisms have 10+ batches each. ponytail: that trigger isn't actually observable yet —
only the SEM is persisted, not the raw between-batch variance it's derived from, so
nothing here can currently distinguish "genuinely converged" from "SEM shrank because n
grew" (SEM shrinks like 1/n by construction regardless of real heterogeneity). Track raw
between-batch variance too before relying on the trigger.

Each finished batch is folded in only once ESS/ratio evidence exists that it actually
calibrated (routers/prediction.py gates on `status == "calibrated"`) — a `"prior_only"`
batch (no usable pH/gravity/Brix readings) contributes pure prior-sampling noise, not
information, and must not count as an observation.

Design note: docs/superpowers/specs/2026-09-28-population-pooling-design.md.
"""

from __future__ import annotations

import math
import uuid

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.models import PopulationPrior
from fermenttrack.prediction.priors import Z90, FloatArray, Prior

# Below this many pooled batches the population estimate is too noisy (dominated by one
# or two batches) to trust over the literature prior.
MIN_POOLED_OBS = 3

# v1 pools exactly the two params most identifiable from pH/gravity/Brix curves alone.
# ponytail: the other ~13 per-organism params (ks, yield_xs, maint, cardinals, mic_*,
# aw_min, ethanol_max, x_max, h0, k_death, ...) stay on the literature prior — pooling
# all of them is over-fit at n~1-20 batches per organism. Expand this tuple once there's
# enough data (and, likely, a real hierarchical model rather than this plug-in) to
# support it.
POOLED_PARAMS = ("mu_max", "t_opt")


def _transformed_mean(values: FloatArray, weights: FloatArray, scale: str) -> float:
    x = np.log(values) if scale == "log" else values
    w = weights / weights.sum()
    return float(np.sum(w * x))


def _row_mean_and_m2(row: PopulationPrior) -> tuple[float, float]:
    """Recover (mean, M2) of the running Welford update from a stored row.

    The row stores the unbiased SEM (`M2 / (n*(n-1))`) as its lo/hi spread (see module
    docstring), so `M2 = stored_var * n_obs * (n_obs - 1)`; at n_obs<2 that's always 0
    (no row is ever written with a non-degenerate n<2 spread, but the formula must not
    divide by zero when a caller recovers state from one).
    """
    mean = math.log(row.median) if row.scale == "log" else row.median
    sd = (
        math.log(row.median / row.lo) / Z90
        if row.scale == "log"
        else (row.median - row.lo) / Z90
    )
    m2 = (sd**2) * row.n_obs * (row.n_obs - 1) if row.n_obs >= 2 else 0.0
    return mean, m2


def _encode(mean: float, sem_var: float, scale: str) -> tuple[float, float, float]:
    sd = math.sqrt(max(sem_var, 0.0))
    if scale == "log":
        return math.exp(mean), math.exp(mean - Z90 * sd), math.exp(mean + Z90 * sd)
    return mean, mean - Z90 * sd, mean + Z90 * sd


async def population_prior_for(
    db: AsyncSession, organism_id: uuid.UUID, param_name: str, fallback: Prior
) -> Prior:
    """The pooled prior for (organism, param), or `fallback` below MIN_POOLED_OBS batches."""
    row = (
        await db.execute(
            select(PopulationPrior).where(
                PopulationPrior.organism_id == organism_id,
                PopulationPrior.param_name == param_name,
            )
        )
    ).scalar_one_or_none()
    if row is None or row.n_obs < MIN_POOLED_OBS:
        return fallback
    return Prior(row.median, row.lo, row.hi, row.scale)  # type: ignore[arg-type]


async def update_population_prior(
    db: AsyncSession,
    organism_id: uuid.UUID,
    param_name: str,
    samples: FloatArray,
    weights: FloatArray,
    scale: str,
) -> None:
    """Fold one finished batch's weighted posterior samples into the population prior."""
    mean_b = _transformed_mean(samples, weights, scale)
    # FOR UPDATE: two batches of the same organism can finish concurrently: without
    # locking this row, both read-modify-write cycles race and the second's update
    # silently overwrites the first's (a lost update, not a raised error). No-op on
    # SQLite (tests) — real locking only matters against concurrent requests, which
    # SQLite's own single-writer model already serializes.
    # ponytail: a never-before-seen (organism, param) row has nothing to lock, so two
    # batches finishing for the very first time for that pair can still race on the
    # INSERT and hit the UniqueConstraint — loud (IntegrityError), not silent, and rare
    # enough (first pool ever, for one specific organism+param) to leave as a follow-up.
    row = (
        await db.execute(
            select(PopulationPrior)
            .where(
                PopulationPrior.organism_id == organism_id,
                PopulationPrior.param_name == param_name,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()

    n_old = row.n_obs if row is not None else 0
    old_mean, m2_old = _row_mean_and_m2(row) if row is not None else (0.0, 0.0)
    n_new = n_old + 1
    delta = mean_b - old_mean
    new_mean = old_mean + delta / n_new
    m2_new = m2_old + delta * (mean_b - new_mean)
    # unbiased sample variance / n: the standard error of the pooled mean. Degenerate
    # (0) below n=2 — there's no spread in a single point — never read back below
    # MIN_POOLED_OBS anyway.
    sem_var = m2_new / (n_new * (n_new - 1)) if n_new >= 2 else 0.0
    median, lo, hi = _encode(new_mean, sem_var, scale)

    if row is None:
        db.add(
            PopulationPrior(
                organism_id=organism_id, param_name=param_name, n_obs=n_new,
                median=median, lo=lo, hi=hi, scale=scale,
            )
        )  # fmt: skip
    else:
        row.n_obs, row.median, row.lo, row.hi, row.scale = n_new, median, lo, hi, scale
    await db.flush()
