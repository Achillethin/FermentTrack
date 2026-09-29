"""Proper scores and calibration checks for probabilistic forecasts given as (weighted)
ensembles: CRPS, PIT, central-interval coverage, skill. Pure functions; used by
scripts/validate_forecasts.py (leave-future-out validation, prediction spec § 5).

CRPS estimator. For a forecast F and outcome y (Gneiting & Raftery 2007, eq. 21)

    CRPS(F, y) = E|X - y| - 1/2 E|X - X'|,   X, X' ~ F independent.

With members x_i and normalised weights w_i, E|X - y| = sum_i w_i |x_i - y| and the spread
term uses the pairs i != j only, divided by 1 - sum_i w_i^2:

    E|X - X'| ~= sum_{i != j} w_i w_j |x_i - x_j| / (1 - sum_i w_i^2),

computed in O(n log n) from the sorted members (sum_{i,j} w_i w_j |x_i - x_j| =
2 sum_i w_i x_i (W_{<i} - W_{>i})). For equal weights this is the "fair" CRPS (Ferro 2014):
unbiased for the CRPS of the distribution the members are drawn from, so a 5-member
climatology and a 2000-draw model ensemble are compared without the finite-ensemble
penalty the plug-in (empirical-CDF) CRPS carries, E|X - X'|/(2n). For fixed importance
weights the same correction is exactly unbiased; for self-normalised ones it is consistent,
with bias O(1/ESS). `fair=False` gives the CRPS of the weighted empirical distribution.

PIT. F(y) of the ensemble, mid-point for ties (F(y-) + F(y))/2: uniform on [0, 1] for a
calibrated continuous forecast. The central (1 - a) interval covers y iff |PIT - 1/2| <= (1 - a)/2,
so coverage and the PIT histogram come from the same numbers.
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import ArrayLike

from fermenttrack.prediction.priors import FloatArray


def _weights(n: int, weights: ArrayLike | None) -> FloatArray:
    w = np.full(n, 1.0 / n) if weights is None else np.asarray(weights, dtype=float)
    if w.shape != (n,) or np.any(w < 0) or not w.sum() > 0:
        raise ValueError("weights must be non-negative, one per member, not all zero")
    return w / w.sum()


def crps_ensemble(
    members: ArrayLike, y: float, weights: ArrayLike | None = None, fair: bool = True
) -> float:
    """CRPS of the (weighted) ensemble `members` for the outcome y (energy form)."""
    x = np.asarray(members, dtype=float).ravel()
    w = _weights(len(x), weights)
    order = np.argsort(x)
    x, w = x[order], w[order]
    cw = np.cumsum(w)
    below = cw - w  # W_{<i}
    spread = 2.0 * float(np.sum(w * x * (below - (1.0 - cw))))  # sum_{i,j} w_i w_j |x_i - x_j|
    s2 = float(np.sum(w**2))
    if fair:
        spread = spread / (1.0 - s2) if s2 < 1.0 else 0.0
    return float(np.sum(w * np.abs(x - y))) - 0.5 * spread


def crps_normal(mu: float, sigma: float, y: float) -> float:
    """Closed-form CRPS of N(mu, sigma^2) (Gneiting et al. 2005)."""
    z = (y - mu) / sigma
    pdf = math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)
    cdf = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    return sigma * (z * (2.0 * cdf - 1.0) + 2.0 * pdf - 1.0 / math.sqrt(math.pi))


def pit(members: ArrayLike, y: float, weights: ArrayLike | None = None) -> float:
    """Probability integral transform F(y) of the ensemble (mid-point at ties)."""
    x = np.asarray(members, dtype=float).ravel()
    w = _weights(len(x), weights)
    return min(max(float(np.sum(w[x < y]) + 0.5 * np.sum(w[x == y])), 0.0), 1.0)  # float sums


def covered(pits: ArrayLike, level: float) -> FloatArray:
    """Whether the central `level` interval covers the outcome, from its PIT."""
    return np.asarray(np.abs(np.asarray(pits, dtype=float) - 0.5) <= level / 2.0)


def pit_histogram(pits: ArrayLike, bins: int = 10) -> list[int]:
    counts, _ = np.histogram(np.asarray(pits, dtype=float), bins=bins, range=(0.0, 1.0))
    return [int(c) for c in counts]


def skill(crps_forecast: ArrayLike, crps_reference: ArrayLike) -> float:
    """CRPS skill score 1 - mean CRPS / mean reference CRPS over the same cases (a ratio of
    means: an average of per-case ratios is dominated by near-zero reference scores)."""
    ref = float(np.mean(crps_reference))
    return 1.0 - float(np.mean(crps_forecast)) / ref if ref > 0 else float("nan")
