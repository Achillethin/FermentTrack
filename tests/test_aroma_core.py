"""Aroma core: exact linear integrator, neutral fraction, draws, odour activity."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from fermenttrack.prediction import aroma
from fermenttrack.prediction import aroma_data as A


def test_constant_source_and_loss_is_exact() -> None:
    t = np.linspace(0.0, 100.0, 11)
    s, k, c0 = 3.0, 0.05, 10.0
    c = aroma.integrate(t, np.full((1, 11), s), np.full((1, 11), k), np.array([c0]))
    exact = s / k + (c0 - s / k) * np.exp(-k * t)
    assert np.allclose(c[0], exact, rtol=1e-12)


def test_no_loss_integrates_the_source() -> None:
    t = np.linspace(0.0, 10.0, 6)
    c = aroma.integrate(t, (2.0 * t)[None, :], np.zeros((1, 6)), np.array([0.0]))
    assert np.allclose(c[0], t**2)  # ∫ 2τ dτ: a linear source is exact


def test_time_varying_matches_solve_ivp() -> None:
    t = np.linspace(0.0, 48.0, 161)
    src = 5.0 + 4.0 * np.sin(t / 6.0)
    k = 0.02 + 0.01 * np.cos(t / 9.0)
    c = aroma.integrate(t, src[None, :], k[None, :], np.array([1.0]))
    ref = solve_ivp(
        lambda tt, y: np.interp(tt, t, src) - np.interp(tt, t, k) * y,
        (0.0, 48.0), [1.0], t_eval=t, rtol=1e-10, atol=1e-12,
    ).y[0]  # fmt: skip
    assert np.allclose(c[0], ref, rtol=2e-3)


def test_step_halving() -> None:
    fine = np.linspace(0.0, 270 * 24.0, 321)  # a 9-month sauerkraut
    src = 1.0 + np.exp(-fine / 50.0)
    k = 0.01 + 0.002 * fine / fine[-1]
    a = aroma.integrate(fine, src[None, :], k[None, :], np.array([0.0]))[0, ::2]
    b = aroma.integrate(fine[::2], src[None, ::2], k[None, ::2], np.array([0.0]))[0]
    assert np.max(np.abs(a - b) / np.maximum(a, 1e-9)) < 0.10


def test_neutral_fraction() -> None:
    assert aroma.neutral_fraction(np.array([4.76]), "acid", 4.76)[0] == pytest.approx(0.5)
    assert aroma.neutral_fraction(np.array([9.8]), "base", 9.8)[0] == pytest.approx(0.5)
    assert aroma.neutral_fraction(np.array([5.0]), "", None)[0] == 1.0


def test_draws_stay_physical() -> None:
    d = aroma.draws(4000, 0)
    assert all(np.all(v >= 0.0) for v in d.values())
    fractions = ("share_", "excr_", "itc_fraction")  # a fraction above 1 makes a negative branch
    assert all(np.all(v <= 1.0) for k, v in d.items() if k.startswith(fractions))
    assert d["matrix"].shape == (4000, 1) and "ing:Cabbage:@sinigrin" in d


def test_trimethylamine_effective_threshold_at_ph_6_9() -> None:
    """Curation spec § 7 invariant: the free-base threshold, corrected to pH 6.9 by the
    neutral fraction, lands within the prior's own x/÷3 of the measured 440 µg/kg."""
    thr = A.COMPOUNDS["trimethylamine"].threshold
    assert thr is not None
    f = aroma.neutral_fraction(np.array([6.9]), "base", 9.8)[0]
    assert 440.0 / 3 <= thr.median / f <= 440.0 * 3


def test_odour_activity_divides_by_threshold_and_matrix() -> None:
    d = aroma.draws(5, 1)
    conc = np.full((5, 3), 100.0)
    oav = aroma.odour_activity(conc, "hexanal", np.ones((5, 3)), d)
    assert np.allclose(oav, 100.0 / (d["thr:hexanal"] * d["matrix"]))
