"""What the app learns across batches: a crossed Gaussian hierarchy over kinetic
parameters, per ferment type, organism and pooled parameter, in the literature prior's
z-units u (the literature prior is exactly N(0, 1) there):

    theta_batch = g + d_style + a_baker + e_starter + eps
    variances     0.30  0.20    0.10     0.30      0.10   (sum 1)

"Achille's classic levain" inherits the classic-levain class and Achille; "Aymard's rye
levain" the rye class and Aymard. With no data a batch's prior is exactly the literature
prior (the general default inherits the global class). The global class and the baker
effect are per ferment type (kraut L. plantarum does not teach sourdough L. plantarum).

Each finished, well-calibrated batch adds evidence: its joint **likelihood summary**
over the pooled parameters (AMIS posterior with the prior it ran under divided out),
stored per parameter as a conservative marginal and only where it beats the Monte Carlo
noise of the ensemble. The prior for a new batch is exact Gaussian conditioning on all
evidence rows of its ferment type. Design: docs/superpowers/specs/
2026-09-28-sourdough-engine-design.md § 6 (supersedes the plug-in pooling of
2026-09-28-population-pooling-design.md; its table is left unused).
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from fermenttrack.models import BatchEvidence
from fermenttrack.prediction.organisms import BAKERS_YEAST, ORGANISM_KINETICS
from fermenttrack.prediction.priors import Z90, FloatArray, LiftedPrior, Prior
from fermenttrack.prediction.sourdough import EXTRA_PARAMS, RISE_MODEL

# Organism parameters most identifiable from pH / rise / gravity curves, plus the
# sourdough rise sub-model (stored under the pseudo-organism RISE_MODEL): without them the
# rise model's own error would be absorbed into mu_max. ponytail: other kinetic
# parameters stay on literature priors until evidence shows them moving.
POOLED_PARAMS = ("mu_max", "t_opt")
RISE_PARAMS = dict(EXTRA_PARAMS)
NOT_POOLED = {BAKERS_YEAST}  # commercial yeast is not a property of the starter

# Variance components in literature z-units, summing to 1 (est.). ponytail: fixed until
# scripts/estimate_variance_components.py (REML) has enough starters to re-estimate them.
VARIANCES = {"global": 0.30, "style": 0.20, "baker": 0.10, "starter": 0.30, "batch": 0.10}
MIN_LEARN_ESS = 50.0  # below this the posterior moments are mostly Monte Carlo noise
MIN_T_SPAN_C = 4.0  # t_opt is only identifiable from a batch that spans temperatures
MAX_ROWS = 2000  # ponytail: O(n^3) conditioning; switch to group sufficient statistics beyond


def literature(organism: str, param: str) -> Prior | None:
    if organism == RISE_MODEL:
        return RISE_PARAMS.get(param)
    kin = ORGANISM_KINETICS.get(organism)
    if kin is None or organism in NOT_POOLED or param not in POOLED_PARAMS:
        return None
    return getattr(kin, param)  # type: ignore[no-any-return]


# ── u-space: the literature prior's own z-units ─────────────────────────


def to_u(lit: Prior, x: FloatArray | float) -> FloatArray:
    """Inverse of Prior.value: the literature z-score of a parameter value (split normal)."""
    x = np.asarray(x, dtype=float)
    if lit.scale == "log":
        y = np.log(np.maximum(x, 1e-300) / lit.median)
        s_lo, s_hi = math.log(lit.median / lit.lo) / Z90, math.log(lit.hi / lit.median) / Z90
    else:
        y = x - lit.median
        s_lo, s_hi = (lit.median - lit.lo) / Z90, (lit.hi - lit.median) / Z90
    s_lo, s_hi = max(s_lo, 1e-12), max(s_hi, 1e-12)
    return np.asarray(np.where(y < 0, y / s_lo, y / s_hi))


def from_u(lit: Prior, mean: float, var: float) -> Prior:
    """N(mean, var) in u-space -> a prior in the parameter's own units, exactly Gaussian in
    u (so a batch that ran under it can divide it out exactly)."""
    return LiftedPrior.of(lit, mean, math.sqrt(max(var, 1e-9)))


def prior_moments_u(lit: Prior, prior: Prior) -> tuple[float, float]:
    """(mean, variance) in u-space of the prior a batch actually ran with."""
    if isinstance(prior, LiftedPrior) and prior.base == lit:
        return prior.m, prior.sd**2
    if prior == lit:
        return 0.0, 1.0
    lo, med, hi = to_u(lit, np.array([prior.lo, prior.median, prior.hi]))  # approximate
    sd = max((hi - lo) / (2 * Z90), 1e-6)
    return float(med), float(sd**2)


# ── evidence from one batch ─────────────────────────────────────────────


@dataclass(frozen=True)
class Evidence:
    organism: str
    param: str
    ell: float  # likelihood mean, u-space
    lam: float  # likelihood precision (conservative marginal, Monte Carlo noise added)


def likelihood_summaries(
    specs: Sequence[Any],
    organisms: Sequence[Any],
    z: FloatArray,
    weights: FloatArray,
    *,
    tempered: float = 1.0,
    temp_span_c: float = math.inf,
) -> list[Evidence]:
    """What this batch's readings said about the pooled parameters, jointly, with the
    prior it ran under divided out (Gaussian division of the weighted posterior).

    Stored per parameter as the conservative marginal precision 1/(Lambda^-1)_jj (the
    information about that parameter with the others unknown: a ridge between mu_max and
    t_opt is not counted twice), with the Monte Carlo variance of ell added to 1/lambda,
    and only where the narrowing beats the ensemble's noise (3 sd of the sampling error
    of a variance ratio, sqrt(2/ESS)). Nothing is learned from a tempered posterior."""
    w = weights / weights.sum()
    ess = 1.0 / float(np.sum(w**2))
    if tempered < 1.0 or ess < MIN_LEARN_ESS:
        return []
    cols: list[tuple[int, str, str, Prior, Prior]] = []  # col, organism, param, lit, used
    for col, s in enumerate(specs):
        org = RISE_MODEL if s.organism is None else organisms[s.organism].name
        lit = literature(org, s.name)
        if lit is None or (s.name == "t_opt" and temp_span_c < MIN_T_SPAN_C):
            continue
        cols.append((col, org, s.name, lit, s.prior))
    if not cols:
        return []
    u = np.column_stack([to_u(lit, used.value(z[:, c])) for c, _, _, lit, used in cols])
    m_post = w @ u
    d = u - m_post
    c_post = (d * w[:, None]).T @ d / (1.0 - float(np.sum(w**2)))  # debiased weighted cov
    pr = np.array([prior_moments_u(lit, used) for _, _, _, lit, used in cols])
    m_pr, v_pr = pr[:, 0], pr[:, 1]
    try:
        p_post = np.linalg.inv(c_post)
    except np.linalg.LinAlgError:
        return []
    lam = p_post - np.diag(1.0 / v_pr)
    # directions the readings did not inform come out non-positive: clip them to (almost)
    # no information rather than inventing precision
    ev, vec = np.linalg.eigh(0.5 * (lam + lam.T))
    lam_inv = (vec / np.maximum(ev, 1e-6)) @ vec.T
    ell = lam_inv @ (p_post @ m_post - m_pr / v_pr)
    noise = 3.0 * math.sqrt(2.0 / ess)  # sd of a variance ratio's sampling error, x3
    if noise >= 1.0:
        return []
    mc_var = np.diag(lam_inv @ p_post @ lam_inv) / ess  # Monte Carlo variance of ell
    out = []
    for j, (_, org, param, _, _) in enumerate(cols):
        lam_j = 1.0 / lam_inv[j, j]
        # narrowing of the prior this information alone would give: lam v / (1 + lam v)
        if lam_j * v_pr[j] <= noise / (1.0 - noise):
            continue
        lam_eff = 1.0 / (lam_inv[j, j] + mc_var[j])
        if math.isfinite(ell[j]) and lam_eff > 0:
            out.append(Evidence(org, param, float(ell[j]), float(lam_eff)))
    return out


# ── conditioning ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Row:
    style: str | None
    baker: str | None
    starter: str | None
    ell: float
    lam: float


def _labels(rows: Sequence[Row], attr: str, target: str | None) -> tuple[list[str], str]:
    """Group labels; a missing label is a group of its own (it still has an effect, it
    just shares it with nobody)."""
    labels = [getattr(r, attr) or f"\0row{i}" for i, r in enumerate(rows)]
    return labels, target or "\0target"


def predictive(rows: Sequence[Row], style: str | None, baker: str | None,
               starter: str | None, v: dict[str, float] = VARIANCES) -> tuple[float, float]:  # fmt: skip
    """Mean and variance (u-space) of a new batch's parameter for this starter, style and
    baker, given every evidence row of the same ferment type: exact Gaussian conditioning."""
    total = sum(v.values())
    if not rows:
        return 0.0, total
    rows = list(rows)[-MAX_ROWS:]
    n = len(rows)
    sig = np.full((n, n), v["global"])
    c = np.full(n, v["global"])
    for attr, key, target in (("style", "style", style), ("baker", "baker", baker),
                              ("starter", "starter", starter)):  # fmt: skip
        labels, t = _labels(rows, attr, target)
        lab = np.array(labels, dtype=object)
        sig += v[key] * (lab[:, None] == lab[None, :])
        c += v[key] * (lab == t)
    sig[np.diag_indices(n)] += v["batch"] + 1.0 / np.maximum([r.lam for r in rows], 1e-9)
    y = np.array([r.ell for r in rows])
    sol = np.linalg.solve(sig, np.column_stack([y, c]))
    return float(c @ sol[:, 0]), float(max(total - c @ sol[:, 1], 1e-6))


def learned_prior(lit: Prior, rows: Sequence[Row], style: str | None, baker: str | None,
                  starter: str | None) -> Prior:  # fmt: skip
    if not rows:
        return lit
    m, var = predictive(rows, style, baker, starter)
    return from_u(lit, m, var)


# ── database ────────────────────────────────────────────────────────────


async def learned_priors(
    db: AsyncSession,
    organisms: Sequence[str],
    *,
    ferment_type: str,
    style: str | None,
    baker: str | None,
    starter: uuid.UUID | None,
    exclude_batch: uuid.UUID | None = None,
) -> dict[str, dict[str, Prior]]:
    """organism -> {param -> Prior} for a new batch; only entries with evidence (the rest
    stay on the literature). `exclude_batch`: a finished batch's own evidence must not
    feed its own forecast. Only successful batches of the same ferment type count."""
    names = [o for o in organisms if o in ORGANISM_KINETICS and o not in NOT_POOLED]
    if ferment_type == "sourdough":
        names.append(RISE_MODEL)
    if not names:
        return {}
    q = (
        select(BatchEvidence)
        .where(
            BatchEvidence.organism.in_(names),
            BatchEvidence.ferment_type == ferment_type,
            BatchEvidence.outcome == "success",
        )
        .order_by(BatchEvidence.created_at)  # MAX_ROWS keeps the most recent
    )
    if exclude_batch is not None:
        q = q.where(BatchEvidence.batch_id != exclude_batch)
    by: dict[tuple[str, str], list[Row]] = {}
    for e in (await db.execute(q)).scalars():
        by.setdefault((e.organism, e.param), []).append(
            Row(e.style, e.owner_id, str(e.culture_id), e.ell, e.lam)
        )
    # the dense solve is CPU: off the event loop, like the forecasts themselves
    return await run_in_threadpool(_condition_all, by, style, baker, str(starter) if starter else None)


def _condition_all(
    by: dict[tuple[str, str], list[Row]], style: str | None, baker: str | None, starter: str | None
) -> dict[str, dict[str, Prior]]:
    out: dict[str, dict[str, Prior]] = {}
    for (org, param), rows in by.items():
        lit = literature(org, param)
        if lit is not None:
            out.setdefault(org, {})[param] = learned_prior(lit, rows, style, baker, starter)
    return out


async def record_evidence(
    db: AsyncSession,
    *,
    batch_id: uuid.UUID,
    culture_id: uuid.UUID,
    owner_id: str | None,
    ferment_type: str,
    style: str | None,
    outcome: str,
    evidence: Sequence[Evidence],
) -> int:
    """Store a finished batch's evidence once (unique per batch x organism x param)."""
    existing = {
        (e.organism, e.param)
        for e in (
            await db.execute(select(BatchEvidence).where(BatchEvidence.batch_id == batch_id))
        ).scalars()
    }
    added = 0
    for ev in evidence:
        if (ev.organism, ev.param) in existing or not (math.isfinite(ev.ell) and ev.lam > 0):
            continue
        db.add(
            BatchEvidence(
                batch_id=batch_id, culture_id=culture_id, owner_id=owner_id,
                ferment_type=ferment_type, style=style, outcome=outcome,
                organism=ev.organism, param=ev.param, ell=ev.ell, lam=ev.lam,
            )
        )  # fmt: skip
        added += 1
    await db.flush()
    return added
