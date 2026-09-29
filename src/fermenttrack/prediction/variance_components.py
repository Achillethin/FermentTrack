"""REML estimates of the variance components of the population hierarchy (population.py).

Model, per organism x pooled parameter, for its n evidence rows b (likelihood summaries in
the literature prior's z-units u):

    ell_b = mu + d_k(b) + a_j(b) + e_s(b) + eps_b + eta_b
    d ~ N(0, v_style)   a ~ N(0, v_baker)   e ~ N(0, v_starter)   eps ~ N(0, omega = v_batch)
    eta_b ~ N(0, 1/lambda_b), KNOWN

i.e. y = X beta + sum_c Z_c u_c + e with e ~ N(0, diag(omega + 1/lambda_b)), and
V(theta) = sum_c theta_c Z_c Z_c' + omega I + Lambda^-1. The eta term is exact for a
Gaussian likelihood summary: the batch's likelihood in theta_b is proportional to
N(ell_b; theta_b, 1/lambda_b), so ell_b is a noisy observation of theta_b with known variance
(population.predictive conditions on it the same way). A row with an unknown label (None) is
a level of its own: a distinct, unshared effect.

Global class: fixed intercept, REML. population.py draws g ~ N(0, v_global) once per
organism x parameter. Within one organism x parameter that is ONE realisation: v_global has
no replication and cannot be estimated. So mu is a fixed effect and the fit is REML
(Patterson & Thompson 1971): the likelihood of error contrasts K'y with K'1 = 0. Since
K'(v_global 11')K = 0, the other four estimates are identical whether g is random or fixed
(nothing is lost), and a literature median that is off for this organism (mu != 0) cannot
leak into the style / starter components, as it would with the mean pinned at 0.
v_global keeps its default; it is identifiable only across groups (`estimate_pooled`).

With A_c = Z_c Z_c' (A_batch = I) and P = V^-1 - V^-1 X (X' V^-1 X)^-1 X' V^-1:

    l_R(theta) = -1/2 [log|V| + log|X' V^-1 X| + y' P y]                  (+ const)
    dl_R/dtheta_c = 1/2 [y' P A_c P y - tr(P A_c)]
    J_cd = y' P A_c P A_d P y - 1/2 tr(P A_c P A_d)       observed information
    F_cd = 1/2 tr(P A_c P A_d)                            expected information

maximised over phi = log theta (L-BFGS-B, analytic gradient theta_c dl_R/dtheta_c). The traces
use tr(P A_c P A_d) = ||Z_c' P Z_d||_F^2 and y' P A_c P A_d P y = r_c' (Z_c' P Z_d) r_d with
r_c = Z_c' P y. ponytail: dense O(n^3) per evaluation, fine to a few hundred rows per group;
Henderson's mixed-model equations (O(n q^2), q = number of levels) beyond.

Uncertainty: se(phi) from the observed information in phi (J_phi = D J D - diag(theta * dl_R),
D = diag(theta)); 95 % interval exp(phi +- 1.96 se): a log-scale Wald interval, positive and
closer to the skewed, scaled-chi2-like sampling distribution of a variance than the natural-
scale Wald; with few levels (df ~ levels - 1) it is approximate (tests/test_variance_
components.py measures its coverage). Boundary: theta_c < BOUNDARY means the data prefer no
variance at that level. Wald theory fails there (the LRT is a 1/2 chi2_0 : 1/2 chi2_1 mixture,
Self & Liang 1987), so the interval is one-sided, [0, theta + 1.645 se], with se from the
expected information on the natural scale. The same holds near it: an estimate whose log-scale
se exceeds MAX_LOG_SE (the likelihood cannot tell it from 0) is flagged and bounded alike.

Identifiability. A component that fails is REFUSED: held at its default, with the reason,
while the others are estimated conditionally on it (no identifiable component: the defaults).
  * a factor needs >= MIN_LEVELS distinct levels (a variance from one or two draws is noise);
    the batch component needs >= MIN_WITHIN_DF within-starter replicates (n - #starters);
  * the REML-projected matrices Q A_c Q (Q = I - X (X'X)^-1 X') must be linearly
    independent: a component whose matrix lies in the span of the others is identified only
    jointly with them (one batch per starter: A_starter = I = A_batch; one starter per baker:
    A_baker = A_starter; one starter per style ...) and every member of the set is refused.
"""

from __future__ import annotations

import math
from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from scipy.linalg import cho_factor, cho_solve
from scipy.optimize import minimize

from fermenttrack.prediction.population import VARIANCES, Row
from fermenttrack.prediction.priors import FloatArray

FACTORS = ("style", "baker", "starter")
MIN_LEVELS = 3
MIN_WITHIN_DF = 3
BOUNDARY = 1e-4  # u-units^2; the defaults are 0.1-0.3
MAX_LOG_SE = 1.5  # beyond, the log-Wald interval spans > x19 each way: treat as boundary
_LOG_BOUNDS = (math.log(1e-7), math.log(25.0))
_Z95 = 1.959963984540054
_Z95_ONE_SIDED = 1.6448536269514722


@dataclass(frozen=True)
class Component:
    estimate: float  # the REML estimate, or the default when refused
    identifiable: bool
    se: float | None = None  # natural scale
    ci95: tuple[float, float] | None = None
    boundary: bool = False
    note: str = ""


@dataclass(frozen=True)
class Fit:
    n: int
    levels: dict[str, int]  # distinct levels per factor; global: groups; batch: within df
    components: dict[str, Component]  # in VARIANCES order
    intercept: tuple[float, float] | None = None  # GLS mean of the group and its se
    loglik: float | None = None  # restricted log-likelihood at the estimate (no constant)
    converged: bool = False

    def proposed(self, defaults: Mapping[str, float] = VARIANCES) -> dict[str, float]:
        """Values for population.VARIANCES: the estimate where it is identifiable and
        interior, the default otherwise (a boundary zero from few levels is usually a
        small-sample artefact, and 0 would switch that level of learning off for good)."""
        return {
            k: c.estimate if c.identifiable and not c.boundary else defaults[k]
            for k, c in self.components.items()
        }


@dataclass(frozen=True)
class _Block:
    """One group's rows. `z[c]` is the (n, levels) indicator matrix of component c, None for
    the batch component (Z = I); `zz[c]` = Z_c Z_c' for the factors."""

    y: FloatArray
    noise: FloatArray  # known 1/lambda
    z: dict[str, FloatArray | None]
    zz: dict[str, FloatArray]
    x: FloatArray  # (n, p) fixed effects: an intercept, or nothing


def _indicator(labels: Sequence[Hashable | None]) -> FloatArray:
    keys = [lab if lab is not None else ("<unknown>", i) for i, lab in enumerate(labels)]
    index = {k: i for i, k in enumerate(dict.fromkeys(keys))}
    z = np.zeros((len(keys), len(index)))
    z[np.arange(len(keys)), [index[k] for k in keys]] = 1.0
    return z


def _clean(rows: Sequence[Row]) -> list[Row]:
    return [r for r in rows if math.isfinite(r.ell) and math.isfinite(r.lam) and r.lam > 0]


def _levels(rows: Sequence[Row], c: str) -> int:
    labels = [getattr(r, c) for r in rows]
    return len({lab for lab in labels if lab is not None}) + labels.count(None)


def _block(rows: Sequence[Row], random_global: bool) -> _Block:
    n = len(rows)
    z: dict[str, FloatArray | None] = {
        c: _indicator([getattr(r, c) for r in rows]) for c in FACTORS
    }
    if random_global:
        z["global"] = np.ones((n, 1))
    zz = {c: m @ m.T for c, m in z.items() if m is not None}
    z["batch"] = None
    x = np.zeros((n, 0)) if random_global else np.ones((n, 1))
    return _Block(np.array([r.ell for r in rows]), np.array([1.0 / r.lam for r in rows]), z, zz, x)


def _zt(z: FloatArray | None, m: FloatArray) -> FloatArray:
    """Z' m (Z = I when None)."""
    return m if z is None else z.T @ m


def _pmatrix(b: _Block, theta: Mapping[str, float]) -> tuple[FloatArray, float, FloatArray]:
    """(P, log|V| + log|X'V^-1X|, V^-1)."""
    n = len(b.y)
    v = np.diag(b.noise + theta["batch"]) + sum(theta[c] * m for c, m in b.zz.items())
    cf = cho_factor(v, lower=True)
    vi = cho_solve(cf, np.eye(n))
    logdet = 2.0 * float(np.sum(np.log(np.diag(cf[0]))))
    if not b.x.shape[1]:
        return vi, logdet, vi
    vix = vi @ b.x
    xvx = b.x.T @ vix
    logdet += float(np.linalg.slogdet(xvx)[1])
    return vi - vix @ np.linalg.solve(xvx, vix.T), logdet, vi


def _terms(
    blocks: Sequence[_Block], theta: Mapping[str, float], free: Sequence[str]
) -> tuple[float, FloatArray, FloatArray, FloatArray]:
    """Restricted log-likelihood, its gradient in theta[free], observed and expected info."""
    k = len(free)
    ll, grad = 0.0, np.zeros(k)
    obs, fisher = np.zeros((k, k)), np.zeros((k, k))
    for b in blocks:
        p, logdet, _ = _pmatrix(b, theta)
        py = p @ b.y
        ll -= 0.5 * (logdet + float(b.y @ py))
        pz = [p if b.z[c] is None else p @ b.z[c] for c in free]  # P Z_c
        r = [_zt(b.z[c], py) for c in free]  # Z_c' P y
        for i, c in enumerate(free):
            zi = b.z[c]
            trace = np.trace(pz[i]) if zi is None else np.sum(zi * pz[i])  # tr(P A_c)
            grad[i] += 0.5 * (r[i] @ r[i] - trace)
            for j in range(i, k):
                m = _zt(zi, pz[j])  # Z_c' P Z_d
                t = float(np.sum(m * m))  # tr(P A_c P A_d)
                q = float(r[i] @ m @ r[j])  # y' P A_c P A_d P y
                obs[i, j] += q - 0.5 * t
                fisher[i, j] += 0.5 * t
    lower = np.tril_indices(k, -1)
    obs[lower] = obs.T[lower]
    fisher[lower] = fisher.T[lower]
    return ll, grad, obs, fisher


def _refusals(
    blocks: Sequence[_Block], names: Sequence[str], levels: Mapping[str, int]
) -> dict[str, str]:
    why: dict[str, str] = {}
    for c in names:
        if c == "batch":
            if levels[c] < MIN_WITHIN_DF:
                why[c] = (
                    f"{levels[c]} within-starter replicate(s), needs >= {MIN_WITHIN_DF}: "
                    "starters with repeat batches separate batch from starter variance"
                )
        elif levels[c] < MIN_LEVELS:
            what = "organism x parameter group(s)" if c == "global" else f"distinct {c}(s)"
            why[c] = f"{levels[c]} {what}, needs >= {MIN_LEVELS}"
    # confounding: Gram matrix of the projected covariance matrices, <QA_cQ, QA_dQ>_F
    k = len(names)
    gram = np.zeros((k, k))
    for b in blocks:
        n = len(b.y)
        q = np.eye(n) - b.x @ np.linalg.pinv(b.x) if b.x.shape[1] else np.eye(n)
        qz = [q if b.z[c] is None else q @ b.z[c] for c in names]
        for i in range(k):
            for j in range(i, k):
                gram[i, j] += float(np.sum(_zt(b.z[names[i]], qz[j]) ** 2))
                gram[j, i] = gram[i, j]
    for i, c in enumerate(names):
        if gram[i, i] <= 1e-12:
            why.setdefault(c, "no variation left once the intercept is removed")
            continue
        others = [j for j in range(k) if j != i]
        coef = np.linalg.pinv(gram[np.ix_(others, others)], rcond=1e-10) @ gram[i, others]
        if gram[i, i] - gram[i, others] @ coef <= 1e-8 * gram[i, i]:
            partners = [names[others[j]] for j in range(len(others)) if abs(coef[j]) > 1e-6]
            why.setdefault(
                c, f"confounded with {', '.join(partners)}: only a combination is identified"
            )
    return why


def _fit(
    blocks: Sequence[_Block],
    names: Sequence[str],
    levels: dict[str, int],
    defaults: Mapping[str, float],
    comps: dict[str, Component],
) -> Fit:
    n = sum(len(b.y) for b in blocks)
    why = _refusals(blocks, names, levels) if blocks else dict.fromkeys(names, "no evidence rows")
    for c, reason in why.items():
        comps[c] = Component(defaults[c], False, note=reason)
    free = [c for c in names if c not in why]
    if not free:
        return Fit(n, levels, {k: comps[k] for k in VARIANCES})
    fixed = {c: defaults[c] for c in VARIANCES if c not in free}

    def objective(phi: FloatArray) -> tuple[float, FloatArray]:
        th = np.exp(phi)
        ll, g, _, _ = _terms(blocks, {**fixed, **dict(zip(free, th, strict=True))}, free)
        return -ll, -(th * g)

    res = minimize(
        objective, np.log([defaults[c] for c in free]), jac=True, method="L-BFGS-B",
        bounds=[_LOG_BOUNDS] * len(free), options={"maxiter": 200, "ftol": 1e-11, "gtol": 1e-7},
    )  # fmt: skip
    th = np.exp(res.x)
    theta = {**fixed, **dict(zip(free, th, strict=True))}
    ll, g, obs, fisher = _terms(blocks, theta, free)
    interior = [i for i in range(len(free)) if th[i] >= BOUNDARY]
    j_phi = th[:, None] * obs * th[None, :] - np.diag(th * g)
    se_phi = np.full(len(free), np.nan)
    sub = j_phi[np.ix_(interior, interior)]
    if interior and np.all(np.linalg.eigvalsh(sub) > 0):
        se_phi[interior] = np.sqrt(np.diag(np.linalg.inv(sub)))
    interior = [i for i in interior if not se_phi[i] > MAX_LOG_SE]
    for i, c in enumerate(free):
        est = float(th[i])
        if i in interior:
            s = float(se_phi[i])
            if not math.isfinite(s):
                comps[c] = Component(est, True, note="information not positive definite")
                continue
            ci = (est * math.exp(-_Z95 * s), est * math.exp(_Z95 * s))
            comps[c] = Component(est, True, se=est * s, ci95=ci)
            continue
        idx = [*interior, i]
        f_sub = fisher[np.ix_(idx, idx)]
        se = float(np.sqrt(np.linalg.inv(f_sub)[-1, -1])) if np.linalg.det(f_sub) > 0 else None
        comps[c] = Component(
            est, True, se=se, boundary=True,
            ci95=(0.0, est + _Z95_ONE_SIDED * se) if se is not None else None,
            note="at or near the boundary (~0): one-sided 95 % bound",
        )  # fmt: skip
    intercept = None
    if len(blocks) == 1 and blocks[0].x.shape[1]:
        _, _, vi = _pmatrix(blocks[0], theta)
        info = float(np.sum(vi))  # 1' V^-1 1
        intercept = (float(np.sum(vi @ blocks[0].y)) / info, 1.0 / math.sqrt(info))
    return Fit(n, levels, {k: comps[k] for k in VARIANCES}, intercept, ll, bool(res.success))


def estimate(rows: Sequence[Row], defaults: Mapping[str, float] = VARIANCES) -> Fit:
    """REML fit for one organism x parameter (fixed intercept; v_global keeps its default)."""
    rows = _clean(rows)
    levels = {c: _levels(rows, c) for c in FACTORS}
    levels["batch"] = len(rows) - levels["starter"]
    comps = {
        "global": Component(
            defaults["global"], False,
            note="one realisation per organism x parameter (REML integrates the intercept "
            "out): pool groups to estimate it",
        )
    }  # fmt: skip
    blocks = [_block(rows, random_global=False)] if rows else []
    return _fit(blocks, ("style", "baker", "starter", "batch"), levels, defaults, comps)


def estimate_pooled(
    groups: Mapping[Hashable, Sequence[Row]], defaults: Mapping[str, float] = VARIANCES
) -> Fit:
    """One set of five variances shared by every organism x parameter group, for thin data.

    Assumptions: (i) the components are equal across groups in u-space (u is standardised by
    each literature range, so this says the literature ranges are equally (mis)calibrated);
    (ii) the effects of different groups are independent draws (a starter fast in its LAB
    mu_max is not assumed fast in its yeast t_opt), so V is block-diagonal by group.
    Here g is random, N(0, v_global) per group with mean 0 (the literature median): exactly the
    population.py model. No fixed effect remains, so REML coincides with ML, and v_global is
    identifiable from >= MIN_LEVELS groups; it absorbs a literature bias shared by the groups,
    which is what that prior variance is for. Level counts use distinct labels over all
    groups (conservative: the same two styles in ten groups are still two styles)."""
    cleaned = [r for r in (_clean(rs) for rs in groups.values()) if r]
    everything = [r for rs in cleaned for r in rs]
    levels = {c: _levels(everything, c) for c in FACTORS}
    levels["global"] = len(cleaned)
    levels["batch"] = sum(len(rs) - _levels(rs, "starter") for rs in cleaned)
    blocks = [_block(rs, random_global=True) for rs in cleaned]
    return _fit(blocks, ("global", "style", "baker", "starter", "batch"), levels, defaults, {})
