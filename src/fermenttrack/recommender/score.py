"""Recommendation scores (design § 5.3).

`L` is the engine's log10 odour activity summed over a series (aroma) or log10 activity ratio
(taste): members on axis 0, any trailing axes (times). `L > 0` means noticeable. Weights are
the ensemble's member weights; they are normalised here.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike

from fermenttrack.prediction.inference import weighted_quantiles
from fermenttrack.prediction.priors import FloatArray

TAU = 0.25  # log10 units: the width of the soft "noticeable" indicator
LAMBDA = 0.5  # the off-note penalty weight
OPTIMISTIC_Q = 0.9  # U is the weighted P90
CHARACTER_P = 0.5  # a parent series this likely noticeable at d_med is part of its character
LOW_MED = 0.33  # Low / Med / High until the calibration gate (design § 5.4)
MED_HIGH = 0.67
OFF_NOTES = frozenset({"solvent", "sulfurous", "fishy", "cheesy", "phenolic"})


def soft(L: ArrayLike, tau: float = TAU) -> FloatArray:
    """σ(L/τ), per member."""
    x = np.asarray(L, dtype=np.float64) / tau
    return 0.5 * (1.0 + np.tanh(0.5 * x))  # the logistic function, without exp overflow


def _weights(w: ArrayLike, values: FloatArray) -> FloatArray:
    weights = np.asarray(w, dtype=np.float64)
    if weights.shape != values.shape[:1]:
        raise ValueError("one weight per member (axis 0)")
    if not np.all(np.isfinite(weights)) or np.any(weights < 0) or weights.sum() <= 0:
        raise ValueError("weights must be finite, non-negative and not all zero")
    return weights / weights.sum()


def central(L: ArrayLike, w: ArrayLike) -> FloatArray:
    """E = Σ wₙ σ(Lₙ/τ): the ranking score for Proven and Community."""
    s = soft(L)
    return np.tensordot(_weights(w, s), s, axes=1)


def optimistic(L: ArrayLike, w: ArrayLike) -> FloatArray:
    """U = the weighted P90 of σ(Lₙ/τ), in the engine's weighted-quantile convention."""
    s = soft(L)
    return np.asarray(weighted_quantiles(s, _weights(w, s), (OPTIMISTIC_Q,))[0], dtype=np.float64)


def noticeable(L: ArrayLike, w: ArrayLike) -> FloatArray:
    """P = Σ wₙ 1[Lₙ > 0]."""
    hit = (np.asarray(L, dtype=np.float64) > 0).astype(np.float64)
    return np.tensordot(_weights(w, hit), hit, axes=1)


def target_average(per_series: Mapping[str, ArrayLike], targets: Iterable[str]) -> FloatArray:
    """The score over the targets: the mean of their per-series E (exact) or U (the documented
    optimistic approximation, design § 8.1)."""
    keys = list(dict.fromkeys(targets))
    if not keys:
        raise ValueError("no targets, no score: rank by the next keys (design § 5.4)")
    return np.mean([np.asarray(per_series[k], dtype=np.float64) for k in keys], axis=0)


def character_series(
    parent_reported: Iterable[str], parent_p_at_dmed: Mapping[str, float]
) -> frozenset[str]:
    """C: the parent's reported aromas plus every series with P ≥ 0.5 at its median duration."""
    likely = {s for s, p in parent_p_at_dmed.items() if p >= CHARACTER_P}
    return frozenset(parent_reported) | likely


def off_note_series(targets: Iterable[str], character: Iterable[str]) -> frozenset[str]:
    """O minus the user's targets minus the parent's character series."""
    return OFF_NOTES - frozenset(targets) - frozenset(character)


def off_note_penalty(
    var_p: Mapping[str, float],
    par_p: Mapping[str, float],
    targets: Iterable[str],
    character: Iterable[str],
    lam: float = LAMBDA,
) -> float:
    """λ Σ max(0, P_var − P_par) over the off-notes, at the peak time (Experimental only). A
    series the engine did not produce counts as P = 0."""
    rises = (
        max(0.0, var_p.get(o, 0.0) - par_p.get(o, 0.0))
        for o in sorted(off_note_series(targets, character))
    )
    return lam * sum(rises)


def low_med_high(e: float) -> Literal["Low", "Med", "High"]:
    if not math.isfinite(e):
        raise ValueError(f"E must be a finite probability, got {e}")
    if e < LOW_MED:
        return "Low"
    return "Med" if e < MED_HIGH else "High"
