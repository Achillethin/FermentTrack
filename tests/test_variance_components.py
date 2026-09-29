"""REML variance components of the population hierarchy (prediction/variance_components.py):
exactness on a balanced design, recovery and interval coverage on simulated crossed designs,
calibration of population.predictive with the estimates plugged in, identifiability refusals.
"""

from __future__ import annotations

import numpy as np
import pytest

from fermenttrack.prediction import variance_components as vc
from fermenttrack.prediction.population import VARIANCES, Row, predictive

TRUE = {"global": 0.30, "style": 0.35, "baker": 0.15, "starter": 0.25, "batch": 0.15}
REPS = 100


def _design(
    rng: np.random.Generator, styles: int = 8, bakers: int = 10
) -> list[tuple[str, str, str]]:
    """Styles crossed with bakers, starters nested in bakers (2-3 each, one style each),
    2-6 batches per starter."""
    out = []
    for j in range(bakers):
        for s in range(int(rng.integers(2, 4))):
            k = int(rng.integers(styles))
            out += [(f"k{k}", f"j{j}", f"j{j}s{s}")] * int(rng.integers(2, 7))
    return out


def _effects(rng: np.random.Generator) -> dict:
    return {"global": rng.normal(0.0, np.sqrt(TRUE["global"]))}


def _theta(rng: np.random.Generator, eff: dict, k: str, j: str, s: str) -> float:
    """A batch's parameter; a level's effect is drawn when the level is first seen."""
    for lab, c in ((k, "style"), (j, "baker"), (s, "starter")):
        if lab not in eff:
            eff[lab] = rng.normal(0.0, np.sqrt(TRUE[c]))
    return float(eff["global"] + eff[k] + eff[j] + eff[s] + rng.normal(0.0, np.sqrt(TRUE["batch"])))


def _rows(rng: np.random.Generator, labels: list[tuple[str, str, str]], eff: dict) -> list[Row]:
    rows = []
    for k, j, s in labels:
        lam = rng.gamma(3.0, 2.0)  # likelihood precision: posterior var ~0.15-0.5 of a prior 1
        rows.append(Row(k, j, s, _theta(rng, eff, k, j, s) + rng.normal(0.0, lam**-0.5), lam))
    return rows


@pytest.fixture(scope="module")
def simulation() -> dict:
    """REPS simulated designs: each fitted once, with held-out batches of seen starters and
    of new starters (seen bakers and styles) scored against population.predictive."""
    rng = np.random.default_rng(20260929)
    est: dict[str, list[float]] = {c: [] for c in TRUE}
    covered: dict[str, list[bool]] = {c: [] for c in TRUE}
    zs: dict[str, list[float]] = {"plugin": [], "oracle": []}
    for _ in range(REPS):
        labels = _design(rng)
        eff = _effects(rng)
        rows = _rows(rng, labels, eff)
        fit = vc.estimate(rows)
        for c, comp in fit.components.items():
            if comp.identifiable:
                est[c].append(comp.estimate)
                covered[c].append(comp.ci95 is not None and comp.ci95[0] <= TRUE[c] <= comp.ci95[1])
        v = fit.proposed()
        seen = sorted(set(labels))[:8]
        new = [(k, j, f"{j}s-new") for k, j, _ in seen[:4]]
        for k, j, s in seen + new:
            theta = _theta(rng, eff, k, j, s)
            for name, variances in (("plugin", v), ("oracle", TRUE)):
                m, var = predictive(rows, k, j, s, variances)
                zs[name].append((theta - m) / np.sqrt(var))
    return {"est": est, "covered": covered, "z": {k: np.array(z) for k, z in zs.items()}}


def test_reml_recovers_the_components(simulation: dict) -> None:
    est = simulation["est"]
    assert all(len(est[c]) == REPS for c in ("style", "baker", "starter", "batch"))
    assert est["global"] == []  # one realisation per group: never estimated per group
    # median relative error: few-level factors are hard (10 bakers at 0.15), but not noise
    tol = {"style": 0.7, "baker": 0.9, "starter": 0.55, "batch": 0.3}
    for c, t in tol.items():
        e = np.array(est[c])
        assert np.median(np.abs(e / TRUE[c] - 1.0)) < t, c
        assert 0.6 < np.median(e) / TRUE[c] < 1.4, c  # no gross bias


def test_reml_intervals_cover_near_nominal(simulation: dict) -> None:
    cov = {c: float(np.mean(v)) for c, v in simulation["covered"].items() if v}
    # 95 % intervals over 100 reps: MC sd ~0.022. Many-level components near nominal; the
    # log-Wald interval with ~8-10 levels (and one-sided at the boundary) may fall short.
    assert cov["starter"] >= 0.88 and cov["batch"] >= 0.88, cov
    assert cov["style"] >= 0.8 and cov["baker"] >= 0.8, cov


def test_plugged_in_estimates_give_calibrated_predictive_intervals(simulation: dict) -> None:
    # 1200 held-out batches in 100 correlated clusters. With the true variances the
    # conditioning is exact (checks the harness); the plug-in ignores the estimates' own
    # uncertainty, so a slight under-coverage is expected.
    oracle, z = simulation["z"]["oracle"], simulation["z"]["plugin"]
    assert 0.87 <= float(np.mean(np.abs(oracle) <= 1.6448536)) <= 0.93
    cover90 = float(np.mean(np.abs(z) <= 1.6448536))
    assert 0.85 <= cover90 <= 0.95, cover90
    assert abs(float(np.mean(z))) < 0.15 and 0.85 < float(np.std(z)) < 1.2


def test_balanced_one_way_design_matches_the_anova_closed_form() -> None:
    # one style, one baker: only starter and batch vary. For a balanced one-way design REML
    # is the ANOVA estimator, with the known noise d taken off the within mean square.
    rng = np.random.default_rng(3)
    m, r, d = 12, 5, 0.2
    a = rng.normal(0.0, 0.6, m)
    y = a[:, None] + rng.normal(0.0, np.sqrt(0.3 + d), (m, r))
    rows = [Row("k", "j", f"s{i}", float(y[i, t]), 1.0 / d) for i in range(m) for t in range(r)]
    fit = vc.estimate(rows)
    msw = float(np.sum((y - y.mean(1, keepdims=True)) ** 2) / (m * (r - 1)))
    msb = float(r * np.sum((y.mean(1) - y.mean()) ** 2) / (m - 1))
    s, b = fit.components["starter"], fit.components["batch"]
    assert b.estimate == pytest.approx(msw - d, rel=1e-4)
    assert s.estimate == pytest.approx((msb - msw) / r, rel=1e-4)
    # observed information at the optimum = the exact chi2 variances of the mean squares
    assert b.se == pytest.approx(np.sqrt(2 * msw**2 / (m * (r - 1))), rel=1e-3)
    var_s = 2.0 / r**2 * (msb**2 / (m - 1) + msw**2 / (m * (r - 1)))
    assert s.se == pytest.approx(np.sqrt(var_s), rel=1e-3)
    assert fit.intercept is not None and fit.intercept[0] == pytest.approx(y.mean(), rel=1e-6)
    assert not fit.components["style"].identifiable and not fit.components["baker"].identifiable


def _fixed_design_rows(labels: list[tuple[str, str, str]], seed: int = 0) -> list[Row]:
    rng = np.random.default_rng(seed)
    return _rows(rng, labels, _effects(rng))


def test_too_few_levels_are_refused_and_keep_their_default() -> None:
    labels = [(f"k{i % 2}", f"j{i % 6}", f"s{i}") for i in range(12) for _ in range(4)]
    fit = vc.estimate(_fixed_design_rows(labels))
    style = fit.components["style"]
    assert not style.identifiable and style.estimate == VARIANCES["style"]
    assert "2 distinct style" in style.note
    assert fit.components["starter"].identifiable and fit.components["batch"].identifiable
    assert fit.proposed()["style"] == VARIANCES["style"]


def test_one_batch_per_starter_refuses_starter_and_batch() -> None:
    labels = [(f"k{i % 5}", f"j{i % 7}", f"s{i}") for i in range(40)]
    fit = vc.estimate(_fixed_design_rows(labels))
    for c in ("starter", "batch"):
        assert not fit.components[c].identifiable, c
    assert "within-starter" in fit.components["batch"].note
    assert "batch" in fit.components["starter"].note  # confounded with the batch term
    assert fit.components["style"].identifiable and fit.components["baker"].identifiable


def test_one_starter_per_baker_confounds_baker_and_starter() -> None:
    labels = [(f"k{i % 4}", f"j{i}", f"s{i}") for i in range(10) for _ in range(4)]
    fit = vc.estimate(_fixed_design_rows(labels))
    for c in ("baker", "starter"):
        assert not fit.components[c].identifiable and "confounded" in fit.components[c].note
    assert fit.components["batch"].identifiable


def test_no_data_returns_the_defaults() -> None:
    fit = vc.estimate([Row("k", "j", "s", 0.3, 0.0)])  # lam <= 0 is not evidence
    assert fit.n == 0 and fit.proposed() == VARIANCES
    assert not any(c.identifiable for c in fit.components.values())


def test_pooled_fit_shares_components_and_identifies_the_global_class() -> None:
    rng = np.random.default_rng(11)
    groups = {}
    labels = _design(np.random.default_rng(100), bakers=8)
    for gi in range(6):  # six organism x parameter groups on the same bakers and starters
        groups[gi] = _rows(rng, labels, _effects(rng))
    fit = vc.estimate_pooled(groups)
    assert fit.levels["global"] == 6 and fit.components["global"].identifiable
    for c in ("starter", "batch"):
        comp = fit.components[c]
        assert comp.ci95 is not None and comp.ci95[0] <= TRUE[c] <= comp.ci95[1], c
    two = vc.estimate_pooled({0: groups[0], 1: groups[1]})
    assert (
        not two.components["global"].identifiable and "2 organism" in two.components["global"].note
    )
