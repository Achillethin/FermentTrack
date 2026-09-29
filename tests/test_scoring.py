"""Forecast scores (prediction/scoring.py): CRPS against the Gaussian closed form, the fair
estimator's unbiasedness, coverage and PIT on calibrated vs overconfident forecasts."""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy.stats import chisquare

from fermenttrack.prediction import scoring


def test_ensemble_crps_matches_the_gaussian_closed_form() -> None:
    rng = np.random.default_rng(0)
    x = rng.normal(1.0, 2.0, 40000)
    for y in (-3.0, 0.3, 1.0, 6.0):
        exact = scoring.crps_normal(1.0, 2.0, y)
        assert scoring.crps_ensemble(x, y) == pytest.approx(exact, rel=0.01)
    # the closed form at the mean: sigma (sqrt(2) - 1) / sqrt(pi)
    assert scoring.crps_normal(0.0, 1.0, 0.0) == pytest.approx(
        (math.sqrt(2) - 1) / math.sqrt(math.pi)
    )


def test_fair_crps_is_unbiased_for_small_ensembles_and_the_plug_in_is_not() -> None:
    rng = np.random.default_rng(1)
    n, reps, y, sigma = 5, 8000, 0.7, 1.0
    ens = rng.normal(0.0, sigma, (reps, n))
    fair = np.array([scoring.crps_ensemble(e, y) for e in ens])
    plug = np.array([scoring.crps_ensemble(e, y, fair=False) for e in ens])
    exact = scoring.crps_normal(0.0, sigma, y)
    se = fair.std() / math.sqrt(reps)
    assert abs(fair.mean() - exact) < 4 * se
    # the empirical-CDF CRPS pays E|X - X'| / (2n) = sigma / (n sqrt(pi)) for a finite ensemble
    assert plug.mean() - fair.mean() == pytest.approx(sigma / (n * math.sqrt(math.pi)), rel=0.05)


def test_weights_act_like_duplicated_members() -> None:
    x, w = np.array([0.1, 0.5, 2.0]), np.array([2.0, 1.0, 1.0])
    dup = np.array([0.1, 0.1, 0.5, 2.0])
    for y in (-1.0, 0.3, 3.0):
        assert scoring.crps_ensemble(x, y, w, fair=False) == pytest.approx(
            scoring.crps_ensemble(dup, y, fair=False)
        )
        assert scoring.pit(x, y, w) == pytest.approx(scoring.pit(dup, y))
    assert scoring.pit([1.0, 2.0, 3.0], 2.0) == pytest.approx(0.5)  # mid-point at a tie


def _pits_and_crps(rng: np.random.Generator, spread: float, cases: int = 2000):
    y = rng.normal(0.0, 1.0, cases)
    ens = rng.normal(0.0, spread, (cases, 400))
    pits = np.array([scoring.pit(e, v) for e, v in zip(ens, y, strict=True)])
    crps = np.array([scoring.crps_ensemble(e, v) for e, v in zip(ens, y, strict=True)])
    return pits, crps


def test_coverage_and_pit_separate_calibrated_from_overconfident_forecasts() -> None:
    rng = np.random.default_rng(2)
    pits, crps_ok = _pits_and_crps(rng, 1.0)
    assert float(np.mean(scoring.covered(pits, 0.9))) == pytest.approx(0.9, abs=0.025)
    assert float(np.mean(scoring.covered(pits, 0.5))) == pytest.approx(0.5, abs=0.04)
    hist = scoring.pit_histogram(pits)
    assert sum(hist) == 2000 and chisquare(hist).pvalue > 0.001

    pits, crps_narrow = _pits_and_crps(rng, 0.5)  # overconfident: bands half as wide
    # true coverage of its 90 % band: P(|Z| < 1.645 * 0.5) = 0.59
    assert float(np.mean(scoring.covered(pits, 0.9))) == pytest.approx(0.59, abs=0.04)
    hist = scoring.pit_histogram(pits)
    assert hist[0] > 2 * hist[5] and hist[-1] > 2 * hist[4]  # U-shaped
    # propriety: the calibrated forecast scores better, and the skill score says so
    assert scoring.skill(crps_ok, crps_narrow) > 0.05
    assert scoring.skill(crps_ok, crps_ok) == pytest.approx(0.0)
